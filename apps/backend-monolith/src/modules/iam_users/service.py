from fastapi import HTTPException, status
from src.core.config import settings
from src.core.database import get_supabase_admin, get_supabase_anon
from src.modules.iam_users.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    ProvisionStaffRequest,
)


class IAMUsersService:
    @staticmethod
    def login_staff(payload: LoginRequest) -> dict:
        admin_db = get_supabase_admin()
        identificador = payload.identificador.strip().lower()

        # 1. Buscar al integrante por username o por correo en la vista con edad calculada
        if "@" in identificador:
            res = admin_db.table("vw_users_staff").select("*").eq("correo", identificador).maybe_single().execute()
        else:
            res = admin_db.table("vw_users_staff").select("*").eq("username", identificador).maybe_single().execute()

        if not res or not res.data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales incorrectas o usuario no encontrado.",
            )

        user_profile = res.data
        if not user_profile.get("estado_activo", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="La cuenta del usuario está desactivada.",
            )

        # 2. Determinar el correo de autenticación en Supabase Auth (real o sintético)
        auth_email = (
            user_profile["correo"]
            if user_profile.get("correo")
            else settings.build_synthetic_email(user_profile["username"])
        )

        # 3. Autenticar contra Supabase Auth usando un cliente anónimo limpio
        anon_client = get_supabase_anon()
        try:
            auth_res = anon_client.auth.sign_in_with_password(
                {"email": auth_email, "password": payload.password}
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Contraseña incorrecta.",
            ) from exc

        return {
            "access_token": auth_res.session.access_token,
            "refresh_token": auth_res.session.refresh_token,
            "token_type": "bearer",
            "requiere_cambio_clave": user_profile["requiere_cambio_clave"],
            "user": user_profile,
        }

    @staticmethod
    def provision_staff_member(payload: ProvisionStaffRequest) -> dict:
        admin_db = get_supabase_admin()
        clean_username = payload.username.strip().lower()

        # Verificar que el username sea único
        existing = admin_db.table("users").select("id").eq("username", clean_username).execute()
        if existing.data:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"El username '{clean_username}' ya está en uso.",
            )

        # Opción A: Invitación automática por correo electrónico
        if payload.metodo_entrega == "invitacion_correo":
            if not payload.correo:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Para enviar invitación por correo debe proporcionar un correo válido.",
                )
            try:
                invite_res = admin_db.auth.admin.invite_user_by_email(
                    payload.correo,
                    options={"data": {"username": clean_username, "rol": payload.rol_enum}},
                )
                new_user_id = invite_res.user.id
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Error al enviar invitación en Supabase Auth: {exc}",
                ) from exc
            requiere_cambio = False

        # Opción B: Credenciales manuales (con o sin correo real)
        else:
            if not payload.password_temporal:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Debe asignar una contraseña temporal para la entrega manual.",
                )
            auth_email = (
                str(payload.correo).lower()
                if payload.correo
                else settings.build_synthetic_email(clean_username)
            )
            try:
                create_res = admin_db.auth.admin.create_user(
                    {
                        "email": auth_email,
                        "password": payload.password_temporal,
                        "email_confirm": True,
                        "user_metadata": {"username": clean_username, "rol": payload.rol_enum},
                    }
                )
                new_user_id = create_res.user.id
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Error creando identidad en Supabase Auth: {exc}",
                ) from exc
            requiere_cambio = True

        # Insertar registro en public.users
        row_data = {
            "id": new_user_id,
            "username": clean_username,
            "correo": str(payload.correo).lower() if payload.correo else None,
            "requiere_cambio_clave": requiere_cambio,
            "nombres": payload.nombres.strip(),
            "apellidos": payload.apellidos.strip(),
            "rol_enum": payload.rol_enum,
            "nivel_id": payload.nivel_id,
            "fecha_nacimiento": payload.fecha_nacimiento.isoformat(),
            "numero_telefono": payload.numero_telefono,
            "observaciones": payload.observaciones,
            "estado_activo": True,
        }

        inserted = admin_db.table("users").insert(row_data).execute()
        return {
            "mensaje": "Usuario aprovisionado exitosamente.",
            "metodo_entrega": payload.metodo_entrega,
            "usuario": inserted.data[0] if inserted.data else row_data,
        }

    @staticmethod
    def change_mandatory_password(user_id: str, payload: ChangePasswordRequest) -> dict:
        admin_db = get_supabase_admin()
        try:
            admin_db.auth.admin.update_user_by_id(
                user_id, {"password": payload.nueva_password}
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No se pudo actualizar la contraseña: {exc}",
            ) from exc

        admin_db.table("users").update({"requiere_cambio_clave": False}).eq("id", user_id).execute()
        return {"mensaje": "Contraseña actualizada correctamente. Módulos desbloqueados."}

    @staticmethod
    def list_all_staff() -> list:
        admin_db = get_supabase_admin()
        res = admin_db.table("vw_users_staff").select("*").order("apellidos").execute()
        return res.data or []