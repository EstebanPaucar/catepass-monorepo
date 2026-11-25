from datetime import date
from typing import Literal, Optional
from pydantic import BaseModel, Field


class EventoCreateRequest(BaseModel):
    nombre_evento: str = Field(..., min_length=3, max_length=150)
    fecha_programada: date
    tipo: Literal["regular", "admin"] = "regular"
    nivel_id: Optional[str] = Field(
        default=None,
        description="UUID del nivel o NULL si es un evento masivo global (ej. Misa Dominical)",
    )


class BitacoraCreateRequest(BaseModel):
    descripcion_actividad: str = Field(
        ...,
        min_length=5,
        description="Descripción única requerida para desbloquear el escáner en eventos admin",
    )


class QRScanRequest(BaseModel):
    estudiante_id: str = Field(..., description="UUID leído desde el código QR del estudiante")
    evento_id: str = Field(..., description="UUID del evento activo")