-- ============================================================================
-- CATEPASS MONOREPO - MIGRACIÓN 001: ESQUEMA RELACIONAL Y LÓGICA TRANSACCIONAL
-- Arquitectura v7.0: Modelo de 2 Roles Interactivos y Entidades Pasivas
-- ============================================================================

-- 1. Extensiones necesarias para UUIDs y criptografía (Seeding Admin Cero)
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 2. Definición de Tipos ENUM de Negocio (Sección 5)
DO $$ BEGIN
    CREATE TYPE public.rol_usuario_enum AS ENUM ('admin', 'catequista');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE public.pase_nivel_enum AS ENUM ('no_requiere', 'faltante', 'entregado');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE public.fe_bautizo_enum AS ENUM ('faltante', 'entregado');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE public.tipo_evento_enum AS ENUM ('regular', 'admin');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE public.estado_evento_enum AS ENUM ('abierto', 'cerrado');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE public.estado_asistencia_enum AS ENUM ('presente', 'falta', 'justificado');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ============================================================================
-- 3. TABLA: niveles (Agrupaciones académicas y pastorales)
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.niveles (
    id_nivel UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre_nivel VARCHAR(100) NOT NULL UNIQUE,
    horario VARCHAR(120) NOT NULL,
    estado_activo BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- 4. TABLA: users (IAM / Staff - Administradores y Catequistas)
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    username VARCHAR(60) NOT NULL UNIQUE,
    correo VARCHAR(150) UNIQUE NULL,
    requiere_cambio_clave BOOLEAN NOT NULL DEFAULT true,
    nombres VARCHAR(100) NOT NULL,
    apellidos VARCHAR(100) NOT NULL,
    rol_enum public.rol_usuario_enum NOT NULL,
    nivel_id UUID NULL REFERENCES public.niveles(id_nivel) ON DELETE SET NULL,
    fecha_nacimiento DATE NOT NULL,
    numero_telefono VARCHAR(30) NULL,
    observaciones TEXT NULL,
    estado_activo BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Vista con edad calculada dinámicamente (Corrección D - Sección 5)
CREATE OR REPLACE VIEW public.vw_users_staff AS
SELECT 
    u.*,
    EXTRACT(YEAR FROM AGE(CURRENT_DATE, u.fecha_nacimiento))::INT AS edad_calculada,
    n.nombre_nivel,
    n.horario AS horario_nivel
FROM public.users u
LEFT JOIN public.niveles n ON u.nivel_id = n.id_nivel;

-- ============================================================================
-- 5. TABLA: estudiantes (Entidades Pasivas, Requisitos y Vínculo Telegram)
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.estudiantes (
    id_estudiante UUID PRIMARY KEY DEFAULT gen_random_uuid(), -- Incrustado en el QR
    codigo_referencia VARCHAR(50) NULL,                       -- ID original del Excel
    nombres VARCHAR(100) NOT NULL,
    apellidos VARCHAR(100) NOT NULL,
    nivel_id UUID NOT NULL REFERENCES public.niveles(id_nivel) ON DELETE RESTRICT,
    fecha_nacimiento DATE NULL,
    edad_registrada SMALLINT NULL CHECK (edad_registrada IS NULL OR (edad_registrada >= 3 AND edad_registrada <= 25)),
    nombre_representante VARCHAR(150) NOT NULL,
    numero_representante VARCHAR(30) NOT NULL,
    telegram_chat_id VARCHAR(60) NULL,                        -- Vínculo para Bot Fase 2
    pase_nivel public.pase_nivel_enum NOT NULL DEFAULT 'no_requiere',
    fe_bautizo public.fe_bautizo_enum NOT NULL DEFAULT 'faltante',
    observaciones TEXT NULL,
    estado_activo BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_estudiantes_nivel_id ON public.estudiantes(nivel_id);
CREATE INDEX IF NOT EXISTS idx_estudiantes_telegram_chat ON public.estudiantes(telegram_chat_id);

-- ============================================================================
-- 6. TABLA: eventos (Clases regulares, misas y eventos especiales)
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.eventos (
    id_evento UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre_evento VARCHAR(150) NOT NULL,
    fecha_programada DATE NOT NULL DEFAULT CURRENT_DATE,
    tipo public.tipo_evento_enum NOT NULL DEFAULT 'regular',
    estado_evento public.estado_evento_enum NOT NULL DEFAULT 'abierto',
    nivel_id UUID NULL REFERENCES public.niveles(id_nivel) ON DELETE CASCADE, -- NULL = Evento Global
    creado_por UUID NULL REFERENCES public.users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_eventos_fecha ON public.eventos(fecha_programada);

-- ============================================================================
-- 7. TABLA: bitacora_eventos (Descripción requerida en eventos de admin)
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.bitacora_eventos (
    id_bitacora UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evento_id UUID NOT NULL REFERENCES public.eventos(id_evento) ON DELETE CASCADE,
    catequista_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    descripcion_actividad TEXT NOT NULL,
    fecha_registro TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_bitacora_evento_catequista UNIQUE (evento_id, catequista_id)
);

-- ============================================================================
-- 8. TABLA: asistencia (Logs de escaneo QR idempotentes y justificaciones)
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.asistencia (
    id_asistencia UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    estudiante_id UUID NOT NULL REFERENCES public.estudiantes(id_estudiante) ON DELETE CASCADE,
    evento_id UUID NOT NULL REFERENCES public.eventos(id_evento) ON DELETE CASCADE,
    estado public.estado_asistencia_enum NOT NULL DEFAULT 'presente',
    url_evidencia TEXT NULL, -- Ruta en bucket privado de Supabase Storage
    catequista_registro_id UUID NULL REFERENCES public.users(id) ON DELETE SET NULL,
    fecha_hora_log TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_asistencia_estudiante_evento UNIQUE (estudiante_id, evento_id)
);

CREATE INDEX IF NOT EXISTS idx_asistencia_evento_estado ON public.asistencia(evento_id, estado);

-- ============================================================================
-- 9. PROCEDIMIENTO ALMACENADO: Cierre de Evento y Generación de Faltas (Flujo 4)
-- Inserta automáticamente estado = 'falta' para todos los niños activos del
-- nivel convocado (o de toda la catequesis si nivel_id es NULL) que no fueron
-- escaneados, y cambia el evento a 'cerrado'. Devuelve el total de faltas creadas.
-- ============================================================================
CREATE OR REPLACE FUNCTION public.fn_cerrar_evento_asistencia(p_evento_id UUID)
RETURNS INT
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_nivel_evento UUID;
    v_faltas_generadas INT := 0;
BEGIN
    -- 1. Obtener el nivel del evento y verificar que exista
    SELECT nivel_id INTO v_nivel_evento
    FROM public.eventos
    WHERE id_evento = p_evento_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'El evento especificado (%) no existe.', p_evento_id;
    END IF;

    -- 2. Insertar registros en estado 'falta' para los estudiantes no escaneados
    INSERT INTO public.asistencia (estudiante_id, evento_id, estado, fecha_hora_log)
    SELECT 
        e.id_estudiante,
        p_evento_id,
        'falta'::public.estado_asistencia_enum,
        NOW()
    FROM public.estudiantes e
    WHERE e.estado_activo = true
      AND (v_nivel_evento IS NULL OR e.nivel_id = v_nivel_evento)
      AND NOT EXISTS (
          SELECT 1 
          FROM public.asistencia a 
          WHERE a.estudiante_id = e.id_estudiante 
            AND a.evento_id = p_evento_id
      )
    ON CONFLICT ON CONSTRAINT uq_asistencia_estudiante_evento DO NOTHING;

    GET DIAGNOSTICS v_faltas_generadas = ROW_COUNT;

    -- 3. Marcar el evento como cerrado
    UPDATE public.eventos
    SET estado_evento = 'cerrado'
    WHERE id_evento = p_evento_id;

    RETURN v_faltas_generadas;
END;
$$;