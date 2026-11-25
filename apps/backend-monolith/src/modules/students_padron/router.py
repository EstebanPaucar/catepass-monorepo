from typing import Optional
from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from src.core.security import AuthenticatedStaff, get_active_staff, require_admin
from src.modules.students_padron.schemas import (
    EstudianteCreateRequest,
    NivelCreateRequest,
)
from src.modules.students_padron.service import StudentsPadronService

router = APIRouter(prefix="/students", tags=["Módulo 2: Padrón, Niveles y QRs"])


@router.get("/niveles", summary="Listar niveles y paralelos activos")
def get_niveles(
    solo_activos: bool = True,
    _staff: AuthenticatedStaff = Depends(get_active_staff),
):
    return StudentsPadronService.list_niveles(solo_activos)


@router.post("/niveles", summary="Crear nuevo nivel o paralelo A/B (Solo Admin)")
def create_nivel(
    payload: NivelCreateRequest,
    _admin: AuthenticatedStaff = Depends(require_admin),
):
    return StudentsPadronService.create_nivel(payload)


@router.get("/", summary="Listar estudiantes del padrón (filtrable por nivel)")
def get_estudiantes(
    nivel_id: Optional[str] = None,
    _staff: AuthenticatedStaff = Depends(get_active_staff),
):
    return StudentsPadronService.list_estudiantes(nivel_id)


@router.post("/", summary="Registrar un estudiante individualmente (Solo Admin)")
def create_estudiante(
    payload: EstudianteCreateRequest,
    _admin: AuthenticatedStaff = Depends(require_admin),
):
    return StudentsPadronService.create_estudiante(payload)


@router.post("/upload-excel", summary="Importar padrón masivo desde archivo Excel .xlsx (Solo Admin)")
async def upload_excel(
    file: UploadFile = File(...),
    _admin: AuthenticatedStaff = Depends(require_admin),
):
    return await StudentsPadronService.import_excel_padron(file)


@router.get("/niveles/{nivel_id}/qr-pdf", summary="Descargar lote PDF de tarjetas QR por nivel")
def download_qr_pdf(
    nivel_id: str,
    current_user: AuthenticatedStaff = Depends(get_active_staff),
):
    pdf_buffer = StudentsPadronService.generate_level_qr_cards_pdf(nivel_id, current_user)
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="credenciales_qr_nivel_{nivel_id[:8]}.pdf"'
        },
    )