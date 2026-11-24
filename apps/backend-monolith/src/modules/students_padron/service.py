from io import BytesIO
from typing import Optional
import openpyxl
import qrcode
from fastapi import HTTPException, UploadFile, status
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from src.core.config import settings
from src.core.database import get_supabase_admin
from src.core.security import AuthenticatedStaff
from src.modules.students_padron.schemas import (
    EstudianteCreateRequest,
    NivelCreateRequest,
)


def _normalize_pase(val: Optional[str]) -> str:
    if not val:
        return "no_requiere"
    clean = str(val).strip().lower()
    if "entregado" in clean:
        return "entregado"
    if "faltante" in clean or "pendiente" in clean:
        return "faltante"
    return "no_requiere"


def _normalize_bautizo(val: Optional[str]) -> str:
    if not val:
        return "faltante"
    clean = str(val).strip().lower()
    if "entregado" in clean or "si" in clean or "sí" in clean:
        return "entregado"
    return "faltante"


class StudentsPadronService:
    @staticmethod
    def list_niveles(solo_activos: bool = True) -> list:
        admin_db = get_supabase_admin()
        query = admin_db.table("niveles").select("*").order("created_at")
        if solo_activos:
            query = query.eq("estado_activo", True)
        return query.execute().data or []

    @staticmethod
    def create_nivel(payload: NivelCreateRequest) -> dict:
        admin_db = get_supabase_admin()
        res = (
            admin_db.table("niveles")
            .insert(
                {
                    "nombre_nivel": payload.nombre_nivel.strip(),
                    "paralelo": payload.paralelo.strip(),
                    "horario": payload.horario.strip(),
                    "estado_activo": True,
                }
            )
            .execute()
        )
        return res.data[0]

    @staticmethod
    def list_estudiantes(nivel_id: Optional[str] = None) -> list:
        admin_db = get_supabase_admin()
        query = (
            admin_db.table("estudiantes")
            .select("*, niveles(nombre_nivel, paralelo, horario)")
            .eq("estado_activo", True)
            .order("apellidos")
        )
        if nivel_id:
            query = query.eq("nivel_id", nivel_id)
        return query.execute().data or []

    @staticmethod
    def create_estudiante(payload: EstudianteCreateRequest) -> dict:
        admin_db = get_supabase_admin()
        data = payload.model_dump()
        if data.get("fecha_nacimiento"):
            data["fecha_nacimiento"] = data["fecha_nacimiento"].isoformat()
        res = admin_db.table("estudiantes").insert(data).execute()
        return res.data[0]

    @staticmethod
    async def import_excel_padron(file: UploadFile) -> dict:
        """
        Procesa el Excel general con las columnas:
        Id, Nombres, Apellidos, Nivel de Catequesis, Edad, Nombre del Representante,
        Número del Representante, Pase de Nivel, Fe de Bautizo, Observaciones (y Paralelo opcional).
        """
        content = await file.read()
        try:
            wb = openpyxl.load_workbook(BytesIO(content), data_only=True)
            sheet = wb.active
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El archivo subido no es un Excel (.xlsx) válido: {exc}",
            ) from exc

        admin_db = get_supabase_admin()
        niveles_db = admin_db.table("niveles").select("*").eq("estado_activo", True).execute().data or []
        mapa_niveles = {
            (n["nombre_nivel"].strip().lower(), n["paralelo"].strip().lower()): n["id_nivel"]
            for n in niveles_db
        }

        rows = list(sheet.iter_rows(values_only=True))
        if len(rows) < 2:
            raise HTTPException(status_code=400, detail="El archivo Excel está vacío.")

        headers = [str(col).strip().lower() if col else "" for col in rows[0]]

        def get_col(row_vals, possible_names, default=None):
            for name in possible_names:
                if name in headers:
                    idx = headers.index(name)
                    if idx < len(row_vals) and row_vals[idx] is not None:
                        return row_vals[idx]
            return default

        registros_a_insertar = []
        errores = []

        for idx_fila, row in enumerate(rows[1:], start=2):
            nombres = get_col(row, ["nombres", "nombre"])
            apellidos = get_col(row, ["apellidos", "apellido"])
            nivel_txt = get_col(row, ["nivel de catequesis", "nivel"])
            if not nombres or not apellidos or not nivel_txt:
                continue

            paralelo_txt = str(get_col(row, ["paralelo"], "Único")).strip().lower()
            clave_nivel = (str(nivel_txt).strip().lower(), paralelo_txt)
            nivel_id = mapa_niveles.get(clave_nivel) or mapa_niveles.get(
                (str(nivel_txt).strip().lower(), "único")
            )

            if not nivel_id:
                errores.append(f"Fila {idx_fila}: Nivel '{nivel_txt}' (Paralelo '{paralelo_txt}') no existe.")
                continue

            edad_val = get_col(row, ["edad"])
            try:
                edad_int = int(edad_val) if edad_val is not None else None
            except ValueError:
                edad_int = None

            registros_a_insertar.append(
                {
                    "codigo_referencia": str(get_col(row, ["id", "codigo"], "")).strip() or None,
                    "nombres": str(nombres).strip(),
                    "apellidos": str(apellidos).strip(),
                    "nivel_id": nivel_id,
                    "edad_registrada": edad_int,
                    "nombre_representante": str(
                        get_col(row, ["nombre del representante", "representante"], "Sin especificar")
                    ).strip(),
                    "numero_representante": str(
                        get_col(row, ["número del representante", "numero del representante", "telefono"], "S/N")
                    ).strip(),
                    "pase_nivel": _normalize_pase(get_col(row, ["pase de nivel", "pase"])),
                    "fe_bautizo": _normalize_bautizo(get_col(row, ["fe de bautizo", "bautizo"])),
                    "observaciones": str(get_col(row, ["observaciones", "observacion"], "")).strip() or None,
                    "estado_activo": True,
                }
            )

        insertados = 0
        if registros_a_insertar:
            res = admin_db.table("estudiantes").insert(registros_a_insertar).execute()
            insertados = len(res.data) if res.data else 0

        return {
            "mensaje": f"Proceso completado. {insertados} estudiantes cargados.",
            "total_insertados": insertados,
            "errores": errores,
        }

    @staticmethod
    def generate_level_qr_cards_pdf(nivel_id: str, current_user: AuthenticatedStaff) -> BytesIO:
        """
        Genera el lote PDF listo para impresión con las tarjetas QR de un nivel.
        El QR principal contiene EXCLUSIVAMENTE el UUID del estudiante (Sección 8).
        """
        if current_user.rol_enum == "catequista" and current_user.nivel_id != nivel_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Un catequista solo puede generar credenciales QR de su propio nivel asignado.",
            )

        admin_db = get_supabase_admin()
        nivel_res = admin_db.table("niveles").select("*").eq("id_nivel", nivel_id).maybe_single().execute()
        if not nivel_res or not nivel_res.data:
            raise HTTPException(status_code=404, detail="Nivel no encontrado.")
        nivel = nivel_res.data

        estudiantes = (
            admin_db.table("estudiantes")
            .select("*")
            .eq("nivel_id", nivel_id)
            .eq("estado_activo", True)
            .order("apellidos")
            .execute()
            .data
            or []
        )
        if not estudiantes:
            raise HTTPException(status_code=404, detail="No hay estudiantes activos en este nivel.")

        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        # Diseño en cuadrícula: 2 columnas x 4 filas (8 credenciales por página A4)
        card_w = 90 * mm
        card_h = 62 * mm
        margin_x = 12 * mm
        margin_y = 18 * mm
        gap_x = 6 * mm
        gap_y = 5 * mm

        for idx, est in enumerate(estudiantes):
            pos_in_page = idx % 8
            if idx > 0 and pos_in_page == 0:
                pdf.showPage()

            col = pos_in_page % 2
            row = pos_in_page // 2

            x = margin_x + col * (card_w + gap_x)
            y = height - margin_y - (row + 1) * card_h - row * gap_y

            # Marco de la tarjeta
            pdf.setStrokeColor(colors.HexColor("#1E3A8A"))
            pdf.setLineWidth(1.2)
            pdf.roundRect(x, y, card_w, card_h, 4 * mm, stroke=1, fill=0)

            # Encabezado azul institucional
            pdf.setFillColor(colors.HexColor("#1E3A8A"))
            pdf.roundRect(x, y + card_h - 12 * mm, card_w, 12 * mm, 4 * mm, stroke=0, fill=1)
            pdf.setFillColor(colors.white)
            pdf.setFont("Helvetica-Bold", 8.5)
            titulo_nivel = f"{nivel['nombre_nivel']} ({nivel['paralelo']})"
            pdf.drawString(x + 4 * mm, y + card_h - 7.5 * mm, f"CATEPASS | {titulo_nivel[:32]}")

            # QR Principal Opaco (SOLO UUID v4 para protección de menores - Sección 8)
            qr_img = qrcode.make(est["id_estudiante"])
            qr_buf = BytesIO()
            qr_img.save(qr_buf, format="PNG")
            qr_buf.seek(0)
            pdf.drawImage(ImageReader(qr_buf), x + 3 * mm, y + 10 * mm, width=36 * mm, height=36 * mm)

            # Datos impresos del estudiante y colilla de Telegram
            pdf.setFillColor(colors.HexColor("#1F2937"))
            pdf.setFont("Helvetica-Bold", 9)
            pdf.drawString(x + 41 * mm, y + 38 * mm, est["apellidos"][:22])
            pdf.setFont("Helvetica", 8.5)
            pdf.drawString(x + 41 * mm, y + 33 * mm, est["nombres"][:24])

            pdf.setFont("Helvetica", 7)
            pdf.setFillColor(colors.HexColor("#4B5563"))
            pdf.drawString(x + 41 * mm, y + 25 * mm, f"Rep: {est['nombre_representante'][:22]}")
            pdf.drawString(x + 41 * mm, y + 20 * mm, "Escaneo exclusivo de asistencia")

            # Enlace Deep Link para Bot de Telegram (Sección 7)
            bot_link = f"t.me/{settings.TELEGRAM_BOT_USERNAME}?start={est['id_estudiante'][:8]}"
            pdf.setFillColor(colors.HexColor("#0F766E"))
            pdf.setFont("Helvetica-Bold", 6.2)
            pdf.drawString(x + 4 * mm, y + 4 * mm, f"Bot Telegram Padres: /start {est['id_estudiante']}")

        pdf.save()
        buffer.seek(0)
        return buffer