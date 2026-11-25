from datetime import date
from typing import Literal, Optional
from pydantic import BaseModel, Field


class NivelCreateRequest(BaseModel):
    nombre_nivel: str = Field(..., min_length=2, max_length=100)
    paralelo: str = Field(default="Único", max_length=20, description="Ej: Único, A, B")
    horario: str = Field(
        default="Sábados 14:00 - 16:00 | Misa Domingos 10:00 - 11:00",
        max_length=120,
    )


class EstudianteCreateRequest(BaseModel):
    codigo_referencia: Optional[str] = None
    nombres: str = Field(..., min_length=2, max_length=100)
    apellidos: str = Field(..., min_length=2, max_length=100)
    nivel_id: str
    fecha_nacimiento: Optional[date] = None
    edad_registrada: Optional[int] = Field(default=None, ge=3, le=25)
    nombre_representante: str = Field(..., min_length=2, max_length=150)
    numero_representante: str = Field(..., min_length=7, max_length=30)
    pase_nivel: Literal["no_requiere", "faltante", "entregado"] = "no_requiere"
    fe_bautizo: Literal["faltante", "entregado"] = "faltante"
    observaciones: Optional[str] = None