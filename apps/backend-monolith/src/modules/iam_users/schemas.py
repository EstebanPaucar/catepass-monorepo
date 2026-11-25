from datetime import date
from typing import Literal, Optional
from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    identificador: str = Field(..., description="Username (ej. admin.cero) o correo electrónico")
    password: str = Field(..., min_length=6)


class ChangePasswordRequest(BaseModel):
    nueva_password: str = Field(..., min_length=8, description="Nueva contraseña personal segura")


class ProvisionStaffRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=60)
    correo: Optional[EmailStr] = None
    nombres: str = Field(..., min_length=2, max_length=100)
    apellidos: str = Field(..., min_length=2, max_length=100)
    rol_enum: Literal["admin", "catequista"]
    nivel_id: Optional[str] = None
    fecha_nacimiento: date
    numero_telefono: Optional[str] = None
    observaciones: Optional[str] = None
    metodo_entrega: Literal["invitacion_correo", "credenciales_manuales"]
    password_temporal: Optional[str] = Field(default=None, min_length=6)