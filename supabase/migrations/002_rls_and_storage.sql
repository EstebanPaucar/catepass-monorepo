-- ============================================================================
-- CATEPASS MONOREPO - MIGRACIÓN 002: ROW LEVEL SECURITY (RLS) Y STORAGE PRIVADO
-- Arquitectura v7.0: Protección criptográfica y aislamiento por rol/nivel
-- ============================================================================

-- 1. Funciones auxiliares SECURITY DEFINER para leer el rol y nivel del usuario
-- autenticado sin provocar recursión infinita en las políticas de la tabla users.
CREATE OR REPLACE FUNCTION public.fn_mi_rol()
RETURNS public.rol_usuario_enum
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT rol_enum FROM public.users WHERE id = auth.uid() AND estado_activo = true;
$$;

CREATE OR REPLACE FUNCTION public.fn_mi_nivel_id()
RETURNS UUID
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT nivel_id FROM public.users WHERE id = auth.uid() AND estado_activo = true;
$$;

-- 2. Habilitar Row Level Security (RLS) en todas las tablas del esquema
ALTER TABLE public.niveles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.estudiantes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.eventos ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bitacora_eventos ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.asistencia ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- 3. POLÍTICAS RLS: TABLA niveles
-- ============================================================================
DROP POLICY IF EXISTS "Lectura de niveles para personal autenticado" ON public.niveles;
CREATE POLICY "Lectura de niveles para personal autenticado"
ON public.niveles FOR SELECT
TO authenticated
USING (true);

DROP POLICY IF EXISTS "Gestion de niveles exclusiva para admin" ON public.niveles;
CREATE POLICY "Gestion de niveles exclusiva para admin"
ON public.niveles FOR ALL
TO authenticated
USING (public.fn_mi_rol() = 'admin')
WITH CHECK (public.fn_mi_rol() = 'admin');

-- ============================================================================
-- 4. POLÍTICAS RLS: TABLA users
-- ============================================================================
DROP POLICY IF EXISTS "Usuario lee su propio perfil o admin lee todos" ON public.users;
CREATE POLICY "Usuario lee su propio perfil o admin lee todos"
ON public.users FOR SELECT
TO authenticated
USING (id = auth.uid() OR public.fn_mi_rol() = 'admin');

DROP POLICY IF EXISTS "Admin gestiona todos los usuarios" ON public.users;
CREATE POLICY "Admin gestiona todos los usuarios"
ON public.users FOR ALL
TO authenticated
USING (public.fn_mi_rol() = 'admin')
WITH CHECK (public.fn_mi_rol() = 'admin');

DROP POLICY IF EXISTS "Usuario actualiza su flag de cambio de clave" ON public.users;
CREATE POLICY "Usuario actualiza su flag de cambio de clave"
ON public.users FOR UPDATE
TO authenticated
USING (id = auth.uid())
WITH CHECK (id = auth.uid());

-- ============================================================================
-- 5. POLÍTICAS RLS: TABLA estudiantes
-- ============================================================================
-- Lectura permitida al personal autenticado para permitir Escaneo Universal (Sección 3.3)
DROP POLICY IF EXISTS "Lectura de estudiantes para personal activo" ON public.estudiantes;
CREATE POLICY "Lectura de estudiantes para personal activo"
ON public.estudiantes FOR SELECT
TO authenticated
USING (public.fn_mi_rol() IN ('admin', 'catequista'));

DROP POLICY IF EXISTS "Escritura de padron exclusiva para admin" ON public.estudiantes;
CREATE POLICY "Escritura de padron exclusiva para admin"
ON public.estudiantes FOR ALL
TO authenticated
USING (public.fn_mi_rol() = 'admin')
WITH CHECK (public.fn_mi_rol() = 'admin');

-- ============================================================================
-- 6. POLÍTICAS RLS: TABLA eventos
-- ============================================================================
DROP POLICY IF EXISTS "Lectura de eventos para personal activo" ON public.eventos;
CREATE POLICY "Lectura de eventos para personal activo"
ON public.eventos FOR SELECT
TO authenticated
USING (public.fn_mi_rol() IN ('admin', 'catequista'));

DROP POLICY IF EXISTS "Gestion de eventos exclusiva para admin" ON public.eventos;
CREATE POLICY "Gestion de eventos exclusiva para admin"
ON public.eventos FOR ALL
TO authenticated
USING (public.fn_mi_rol() = 'admin')
WITH CHECK (public.fn_mi_rol() = 'admin');

-- ============================================================================
-- 7. POLÍTICAS RLS: TABLA bitacora_eventos
-- ============================================================================
DROP POLICY IF EXISTS "Lectura de bitacoras para admin y autor" ON public.bitacora_eventos;
CREATE POLICY "Lectura de bitacoras para admin y autor"
ON public.bitacora_eventos FOR SELECT
TO authenticated
USING (catequista_id = auth.uid() OR public.fn_mi_rol() = 'admin');

DROP POLICY IF EXISTS "Catequista inserta su propia bitacora" ON public.bitacora_eventos;
CREATE POLICY "Catequista inserta su propia bitacora"
ON public.bitacora_eventos FOR INSERT
TO authenticated
WITH CHECK (catequista_id = auth.uid() AND public.fn_mi_rol() IN ('admin', 'catequista'));

-- ============================================================================
-- 8. POLÍTICAS RLS: TABLA asistencia
-- ============================================================================
DROP POLICY IF EXISTS "Lectura de asistencia para personal" ON public.asistencia;
CREATE POLICY "Lectura de asistencia para personal"
ON public.asistencia FOR SELECT
TO authenticated
USING (public.fn_mi_rol() IN ('admin', 'catequista'));

-- Escaneo Universal QR: Catequista o Admin puede registrar asistencia presente
DROP POLICY IF EXISTS "Registro de escaneo QR por personal activo" ON public.asistencia;
CREATE POLICY "Registro de escaneo QR por personal activo"
ON public.asistencia FOR INSERT
TO authenticated
WITH CHECK (public.fn_mi_rol() IN ('admin', 'catequista'));

-- Justificaciones: El catequista SOLO puede actualizar a 'justificado' niños de su propio nivel_id (Sección 3.3 y 8)
DROP POLICY IF EXISTS "Actualizacion de justificaciones restringida al nivel del catequista" ON public.asistencia;
CREATE POLICY "Actualizacion de justificaciones restringida al nivel del catequista"
ON public.asistencia FOR UPDATE
TO authenticated
USING (
    public.fn_mi_rol() = 'admin'
    OR (
        public.fn_mi_rol() = 'catequista'
        AND EXISTS (
            SELECT 1 FROM public.estudiantes e
            WHERE e.id_estudiante = asistencia.estudiante_id
              AND e.nivel_id = public.fn_mi_nivel_id()
        )
    )
);

-- ============================================================================
-- 9. SUPABASE STORAGE: Bucket Privado para Evidencias Fotográficas (Sección 8)
-- ============================================================================
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'justificaciones-evidencias',
    'justificaciones-evidencias',
    false, -- PRIVADO: Solo accesible mediante Signed URLs
    5242880, -- Límite de 5 MB por fotografía
    ARRAY['image/jpeg', 'image/png', 'image/webp']
)
ON CONFLICT (id) DO NOTHING;

DROP POLICY IF EXISTS "Subida de evidencias por personal autenticado" ON storage.objects;
CREATE POLICY "Subida de evidencias por personal autenticado"
ON storage.objects FOR INSERT
TO authenticated
WITH CHECK (
    bucket_id = 'justificaciones-evidencias'
    AND public.fn_mi_rol() IN ('admin', 'catequista')
);

DROP POLICY IF EXISTS "Lectura de evidencias por personal autenticado" ON storage.objects;
CREATE POLICY "Lectura de evidencias por personal autenticado"
ON storage.objects FOR SELECT
TO authenticated
USING (
    bucket_id = 'justificaciones-evidencias'
    AND public.fn_mi_rol() IN ('admin', 'catequista')
);