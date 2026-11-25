from supabase import Client, create_client
from src.core.config import settings


def get_supabase_admin() -> Client:
    """
    Cliente con Service Role Key para operaciones administrativas del monolito
    (aprovisionamiento de cuentas, carga masiva de Excel y cierres de eventos).
    """
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)


def get_supabase_anon() -> Client:
    """
    Cliente efímero con Anon Key para autenticar credenciales de usuario
    sin contaminar los encabezados del cliente administrativo.
    """
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)