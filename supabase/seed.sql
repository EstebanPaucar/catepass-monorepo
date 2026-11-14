-- ============================================================================
-- CATEPASS MONOREPO - SEEDING INICIAL (Sección 3.1: Administrador Cero y Niveles)
-- ============================================================================

-- 1. Inyección de los 6 Niveles Oficiales de Catequesis y Horarios Reales
INSERT INTO public.niveles (id_nivel, nombre_nivel, paralelo, horario, estado_activo)
VALUES
    ('11111111-1111-4111-8111-111111111101', 'Inicial', 'Único', 'Sábados 14:00 - 16:00 | Misa Domingos 10:00 - 11:00', true),
    ('11111111-1111-4111-8111-111111111102', 'Primero de Comunión', 'Único', 'Sábados 14:00 - 16:00 | Misa Domingos 10:00 - 11:00', true),
    ('11111111-1111-4111-8111-111111111103', 'Segundo de Comunión', 'Único', 'Sábados 14:00 - 16:00 | Misa Domingos 10:00 - 11:00', true),
    ('11111111-1111-4111-8111-111111111104', 'Año Bíblico', 'Único', 'Sábados 14:00 - 16:00 | Misa Domingos 10:00 - 11:00', true),
    ('11111111-1111-4111-8111-111111111105', 'Primero de Confirmación', 'Único', 'Sábados 14:00 - 16:00 | Misa Domingos 10:00 - 11:00', true),
    ('11111111-1111-4111-8111-111111111106', 'Segundo de Confirmación', 'Único', 'Sábados 14:00 - 16:00 | Misa Domingos 10:00 - 11:00', true)
ON CONFLICT ON CONSTRAINT uq_nivel_nombre_paralelo DO UPDATE
SET horario = EXCLUDED.horario,
    estado_activo = EXCLUDED.estado_activo;

-- 2. Inyección Segura del "Administrador Cero" (Sección 3.1)
-- Credenciales iniciales de acceso:
--   Username: admin.cero
--   Correo sintético/real: admin.cero@catequesis.local
--   Contraseña inicial: AdminCatePass2026!
DO $$
DECLARE
    v_admin_id UUID := '00000000-0000-4000-a000-000000000001';
    v_admin_email TEXT := 'admin.cero@catequesis.local';
    v_admin_pass TEXT := 'AdminCatePass2026!';
BEGIN
    -- Insertar en auth.users si no existe
    IF NOT EXISTS (SELECT 1 FROM auth.users WHERE id = v_admin_id) THEN
        INSERT INTO auth.users (
            instance_id,
            id,
            aud,
            role,
            email,
            encrypted_password,
            email_confirmed_at,
            raw_app_meta_data,
            raw_user_meta_data,
            created_at,
            updated_at,
            confirmation_token,
            email_change,
            email_change_token_new,
            recovery_token
        ) VALUES (
            '00000000-0000-0000-0000-000000000000',
            v_admin_id,
            'authenticated',
            'authenticated',
            v_admin_email,
            crypt(v_admin_pass, gen_salt('bf')),
            NOW(),
            '{"provider": "email", "providers": ["email"]}',
            '{"username": "admin.cero", "rol": "admin"}',
            NOW(),
            NOW(),
            '',
            '',
            '',
            ''
        );

        -- Insertar identidad asociada en auth.identities para login con contraseña
        INSERT INTO auth.identities (
            id,
            user_id,
            identity_data,
            provider,
            provider_id,
            last_sign_in_at,
            created_at,
            updated_at
        ) VALUES (
            gen_random_uuid(),
            v_admin_id,
            format('{"sub": "%s", "email": "%s"}', v_admin_id::text, v_admin_email)::jsonb,
            'email',
            v_admin_id::text,
            NOW(),
            NOW(),
            NOW()
        );
    END IF;

    -- Insertar perfil en public.users
    INSERT INTO public.users (
        id,
        username,
        correo,
        requiere_cambio_clave,
        nombres,
        apellidos,
        rol_enum,
        nivel_id,
        fecha_nacimiento,
        numero_telefono,
        observaciones,
        estado_activo
    ) VALUES (
        v_admin_id,
        'admin.cero',
        v_admin_email,
        false, -- El Administrador Cero ya entra directo al panel
        'Coordinador',
        'Administrador Cero',
        'admin',
        NULL,
        '2002-08-15',
        '0999999999',
        'Cuenta maestra inyectada por Seeding Inicial (Sección 3.1)',
        true
    )
    ON CONFLICT (id) DO NOTHING;
END $$;