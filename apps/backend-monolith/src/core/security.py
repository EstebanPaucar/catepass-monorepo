from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from src.core.database import get_supabase_admin

security_scheme = HTTPBearer()


class AuthenticatedStaff(BaseModel):
    id: str
    username: str
    correo: Optional[str] = None
    requiere_cambio_clave: bool
    nombres: str
    apellidos: str
    rol_enum: str  # 'admin' | 'catequista'
    nivel_id: Optional[str] = None
    estado_activo: bool


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> AuthenticatedStaff:
    """
    Verifica el token JWT contra Supabase Auth y recupera el perfil y rol
    desde la tabla public.users.
    """
    token = credentials.credentials
    admin_client = get_supabase_admin()

    try:
        auth_response = admin_client.auth.get_user(token)
        if not auth_response or not auth_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token JWT inválido o expirado.",
            )
        user_id = auth_response.user.id
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se pudo verificar la sesión del usuario.",
        ) from exc

    db_res = (
        admin_client.table("users")
        .select("*")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )

    if not db_res or not db_res.data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El usuario no posee un perfil registrado en el sistema.",
        )

    staff = AuthenticatedStaff(**db_res.data)
    if not staff.estado_activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta cuenta de personal se encuentra desactivada.",
        )

    return staff


def get_active_staff(
    current_user: AuthenticatedStaff = Depends(get_current_user),
) -> AuthenticatedStaff:
    """
    Bloquea el acceso a cualquier endpoint operativo si el usuario tiene pendiente
    el cambio obligatorio de su contraseña temporal (Sección 3.2 - Opción B).
    """
    if current_user.requiere_cambio_clave:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CAMBIO_CLAVE_REQUERIDO: Debe actualizar su contraseña temporal antes de operar el sistema.",
        )
    return current_user


def require_admin(
    current_user: AuthenticatedStaff = Depends(get_active_staff),
) -> AuthenticatedStaff:
    """Restringe el endpoint exclusivamente al rol 'admin'."""
    if current_user.rol_enum != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: Se requieren privilegios de Administrador.",
        )
    return current_user