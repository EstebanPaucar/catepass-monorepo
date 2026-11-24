from typing import Optional
from fastapi import APIRouter, Depends, File, UploadFile
from src.core.security import AuthenticatedStaff, get_active_staff, require_admin
from src.modules.attendance_events.schemas import (
    BitacoraCreateRequest,
    EventoCreateRequest,
    QRScanRequest,
)
from src.modules.attendance_events.service import AttendanceEventsService

router = APIRouter(prefix="/attendance", tags=["Módulo 3: Asistencia, Eventos y Justificaciones"])


@router.get("/eventos", summary="Listar eventos programados")
def get_eventos(
    estado_evento: Optional[str] = None,
    _staff: AuthenticatedStaff = Depends(get_active_staff),
):
    return AttendanceEventsService.list_eventos(estado_evento)


@router.post("/eventos", summary="Crear nuevo evento regular o administrativo (Solo Admin)")
def create_evento(
    payload: EventoCreateRequest,
    admin_user: AuthenticatedStaff = Depends(require_admin),
):
    return AttendanceEventsService.create_evento(payload, admin_user)


@router.post("/eventos/{evento_id}/bitacora", summary="Registrar bitácora de actividad del catequista")
def register_bitacora(
    evento_id: str,
    payload: BitacoraCreateRequest,
    current_user: AuthenticatedStaff = Depends(get_active_staff),
):
    return AttendanceEventsService.register_bitacora(evento_id, payload, current_user)


@router.post("/scan", summary="Registrar escaneo QR de asistencia con control idempotente (UPSERT)")
def scan_qr(
    payload: QRScanRequest,
    current_user: AuthenticatedStaff = Depends(get_active_staff),
):
    return AttendanceEventsService.scan_student_qr(payload, current_user)


@router.post("/eventos/{evento_id}/cerrar", summary="Cerrar evento y generar inasistencias automáticas (Solo Admin)")
def close_evento(
    evento_id: str,
    _admin: AuthenticatedStaff = Depends(require_admin),
):
    return AttendanceEventsService.close_event_and_generate_absences(evento_id)


@router.get("/eventos/{evento_id}/registros", summary="Listar asistencias/faltas de un evento")
def list_registros(
    evento_id: str,
    estado: Optional[str] = None,
    current_user: AuthenticatedStaff = Depends(get_active_staff),
):
    return AttendanceEventsService.list_asistencia_evento(evento_id, current_user, estado)


@router.post("/asistencia/{asistencia_id}/justificar", summary="Subir foto de evidencia y pasar falta a justificado")
async def justify_absence(
    asistencia_id: str,
    evidencia: UploadFile = File(...),
    current_user: AuthenticatedStaff = Depends(get_active_staff),
):
    return await AttendanceEventsService.justify_absence_with_photo(
        asistencia_id, evidencia, current_user
    )