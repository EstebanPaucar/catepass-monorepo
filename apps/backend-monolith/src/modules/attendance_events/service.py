from datetime import datetime, timezone
from typing import Optional
import uuid
from fastapi import HTTPException, UploadFile, status
from src.core.config import settings
from src.core.database import get_supabase_admin
from src.core.security import AuthenticatedStaff
from src.modules.attendance_events.schemas import (
    BitacoraCreateRequest,
    EventoCreateRequest,
    QRScanRequest,
)
from src.shared.event_bus import event_bus


class AttendanceEventsService:
    @staticmethod
    def list_eventos(estado_evento: Optional[str] = None) -> list:
        admin_db = get_supabase_admin()
        query = (
            admin_db.table("eventos")
            .select("*, niveles(nombre_nivel, paralelo)")
            .order("fecha_programada", desc=True)
        )
        if estado_evento:
            query = query.eq("estado_evento", estado_evento)
        return query.execute().data or []

    @staticmethod
    def create_evento(payload: EventoCreateRequest, admin_user: AuthenticatedStaff) -> dict:
        admin_db = get_supabase_admin()
        res = (
            admin_db.table("eventos")
            .insert(
                {
                    "nombre_evento": payload.nombre_evento.strip(),
                    "fecha_programada": payload.fecha_programada.isoformat(),
                    "tipo": payload.tipo,
                    "estado_evento": "abierto",
                    "nivel_id": payload.nivel_id,
                    "creado_por": admin_user.id,
                }
            )
            .execute()
        )
        return res.data[0]

    @staticmethod
    def register_bitacora(
        evento_id: str,
        payload: BitacoraCreateRequest,
        current_user: AuthenticatedStaff,
    ) -> dict:
        admin_db = get_supabase_admin()
        res = (
            admin_db.table("bitacora_eventos")
            .upsert(
                {
                    "evento_id": evento_id,
                    "catequista_id": current_user.id,
                    "descripcion_actividad": payload.descripcion_actividad.strip(),
                },
                on_conflict="evento_id,catequista_id",
            )
            .execute()
        )
        return {
            "mensaje": "Bitácora registrada. Escáner QR desbloqueado para este evento.",
            "bitacora": res.data[0] if res.data else None,
        }

    @staticmethod
    def scan_student_qr(payload: QRScanRequest, current_user: AuthenticatedStaff) -> dict:
        """
        Flujo 3: Escaneo QR continuo con validación de Bitácora y control de idempotencia (UPSERT).
        """
        admin_db = get_supabase_admin()

        # 1. Verificar que el evento exista y esté abierto
        evento_res = (
            admin_db.table("eventos")
            .select("*")
            .eq("id_evento", payload.evento_id)
            .maybe_single()
            .execute()
        )
        if not evento_res or not evento_res.data:
            raise HTTPException(status_code=404, detail="El evento no existe.")
        evento = evento_res.data

        if evento["estado_evento"] != "abierto":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Este evento ya se encuentra cerrado y no admite nuevos escaneos.",
            )

        # 2. Si es un evento administrativo, verificar que el catequista haya llenado su bitácora
        if evento["tipo"] == "admin" and current_user.rol_enum == "catequista":
            bitacora_res = (
                admin_db.table("bitacora_eventos")
                .select("id_bitacora")
                .eq("evento_id", payload.evento_id)
                .eq("catequista_id", current_user.id)
                .execute()
            )
            if not bitacora_res.data:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="BITACORA_REQUERIDA: Debe ingresar la descripción de la actividad antes de escanear QRs.",
                )

        # 3. Verificar que el estudiante exista
        est_res = (
            admin_db.table("estudiantes")
            .select("id_estudiante, nombres, apellidos, nivel_id, niveles(nombre_nivel, paralelo)")
            .eq("id_estudiante", payload.estudiante_id)
            .maybe_single()
            .execute()
        )
        if not est_res or not est_res.data:
            raise HTTPException(status_code=404, detail="Código QR no corresponde a ningún estudiante.")
        estudiante = est_res.data

        # 4. Verificar si ya fue escaneado previamente en este evento (Idempotencia - Corrección E)
        prev_scan = (
            admin_db.table("asistencia")
            .select("*")
            .eq("estudiante_id", payload.estudiante_id)
            .eq("evento_id", payload.evento_id)
            .maybe_single()
            .execute()
        )

        if prev_scan and prev_scan.data and prev_scan.data.get("estado") == "presente":
            return {
                "duplicado": True,
                "mensaje": "Asistencia ya registrada previamente en este evento.",
                "estudiante": estudiante,
                "asistencia": prev_scan.data,
            }

        # 5. Ejecutar UPSERT a estado = 'presente'
        upsert_res = (
            admin_db.table("asistencia")
            .upsert(
                {
                    "estudiante_id": payload.estudiante_id,
                    "evento_id": payload.evento_id,
                    "estado": "presente",
                    "catequista_registro_id": current_user.id,
                    "fecha_hora_log": datetime.now(timezone.utc).isoformat(),
                },
                on_conflict="estudiante_id,evento_id",
            )
            .execute()
        )

        return {
            "duplicado": False,
            "mensaje": "Asistencia registrada exitosamente.",
            "estudiante": estudiante,
            "asistencia": upsert_res.data[0] if upsert_res.data else None,
        }

    @staticmethod
    def close_event_and_generate_absences(evento_id: str) -> dict:
        """
        Flujo 4 (Opción 1): Ejecuta la función SQL fn_cerrar_evento_asistencia
        para insertar automáticamente 'falta' en los niños no escaneados y emite el evento al Bus.
        """
        admin_db = get_supabase_admin()
        rpc_res = admin_db.rpc(
            "fn_cerrar_evento_asistencia", {"p_evento_id": evento_id}
        ).execute()

        faltas_generadas = rpc_res.data if isinstance(rpc_res.data, int) else 0

        # Emitir evento interno para el módulo de Bot de Telegram (Fase 2 de expansión)
        event_bus.publish(
            "CierreAsistenciaEjecutado",
            {"evento_id": evento_id, "faltas_generadas": faltas_generadas},
        )

        return {
            "mensaje": "Evento cerrado correctamente. Inasistencias generadas.",
            "evento_id": evento_id,
            "faltas_generadas": faltas_generadas,
        }

    @staticmethod
    async def justify_absence_with_photo(
        asistencia_id: str,
        evidencia: UploadFile,
        current_user: AuthenticatedStaff,
    ) -> dict:
        """
        Actualiza una inasistencia ('falta') a 'justificado' subiendo la evidencia fotográfica
        al bucket privado de Supabase Storage. Restringido al nivel del catequista.
        """
        admin_db = get_supabase_admin()
        asist_res = (
            admin_db.table("asistencia")
            .select("*, estudiantes(id_estudiante, nombres, apellidos, nivel_id)")
            .eq("id_asistencia", asistencia_id)
            .maybe_single()
            .execute()
        )
        if not asist_res or not asist_res.data:
            raise HTTPException(status_code=404, detail="Registro de asistencia no encontrado.")

        registro = asist_res.data
        estudiante_nivel_id = registro["estudiantes"]["nivel_id"]

        if current_user.rol_enum == "catequista" and current_user.nivel_id != estudiante_nivel_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo puede justificar inasistencias de estudiantes de su propio nivel asignado.",
            )

        file_bytes = await evidencia.read()
        ext = (evidencia.filename or "foto.jpg").split(".")[-1].lower()
        if ext not in ("jpg", "jpeg", "png", "webp"):
            ext = "jpg"

        storage_path = f"evento_{registro['evento_id']}/{asistencia_id}_{uuid.uuid4().hex[:6]}.{ext}"
        bucket_name = settings.SUPABASE_STORAGE_BUCKET_EVIDENCIAS

        admin_db.storage.from_(bucket_name).upload(
            path=storage_path,
            file=file_bytes,
            file_options={"content-type": evidencia.content_type or "image/jpeg"},
        )

        updated = (
            admin_db.table("asistencia")
            .update(
                {
                    "estado": "justificado",
                    "url_evidencia": storage_path,
                    "catequista_registro_id": current_user.id,
                }
            )
            .eq("id_asistencia", asistencia_id)
            .execute()
        )

        return {
            "mensaje": "Inasistencia actualizada a 'justificado' con evidencia almacenada.",
            "asistencia": updated.data[0] if updated.data else None,
        }

    @staticmethod
    def list_asistencia_evento(
        evento_id: str,
        current_user: AuthenticatedStaff,
        estado: Optional[str] = None,
    ) -> list:
        admin_db = get_supabase_admin()
        query = (
            admin_db.table("asistencia")
            .select("*, estudiantes!inner(id_estudiante, nombres, apellidos, nivel_id, niveles(nombre_nivel, paralelo))")
            .eq("evento_id", evento_id)
        )
        if current_user.rol_enum == "catequista" and current_user.nivel_id:
            query = query.eq("estudiantes.nivel_id", current_user.nivel_id)
        if estado:
            query = query.eq("estado", estado)

        return query.execute().data or []