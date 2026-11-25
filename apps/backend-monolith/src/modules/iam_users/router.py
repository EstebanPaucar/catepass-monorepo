from fastapi import APIRouter, Depends
from src.core.security import AuthenticatedStaff, get_current_user, require_admin
from src.modules.iam_users.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    ProvisionStaffRequest,
)
from src.modules.iam_users.service import IAMUsersService

router = APIRouter(prefix="/iam", tags=["Módulo 1: IAM y Usuarios"])


@router.post("/login", summary="Iniciar sesión con Username o Correo")
def login(payload: LoginRequest):
    return IAMUsersService.login_staff(payload)


@router.get("/me", summary="Obtener perfil de la sesión actual")
def get_me(current_user: AuthenticatedStaff = Depends(get_current_user)):
    return current_user


@router.post("/change-password", summary="Cambio obligatorio de contraseña temporal")
def change_password(
    payload: ChangePasswordRequest,
    current_user: AuthenticatedStaff = Depends(get_current_user),
):
    return IAMUsersService.change_mandatory_password(current_user.id, payload)


@router.get("/users", summary="Listar todo el personal con edad calculada y paralelo (Solo Admin)")
def list_staff(_admin: AuthenticatedStaff = Depends(require_admin)):
    return IAMUsersService.list_all_staff()


@router.post("/users", summary="Aprovisionar nuevo Administrador o Catequista (Solo Admin)")
def create_staff(
    payload: ProvisionStaffRequest,
    _admin: AuthenticatedStaff = Depends(require_admin),
):
    return IAMUsersService.provision_staff_member(payload)