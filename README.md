# CatePass — Sistema Multiplataforma de Asistencia QR y Gestión para Catequesis

Arquitectura de **Monolito Modular** y clientes desacoplados (**Web + Móvil**) en **Monorepo**, diseñada bajo el principio *Secure by Design* para la protección de datos de menores de edad.

## Arquitectura del Sistema (v7.0)

* **Modelo de 2 Roles Interactivos (RBAC):** `Administrador` y `Catequista`. Los estudiantes operan como **Entidades Pasivas** representadas por credenciales físicas con códigos QR opacos (`UUID v4` sin datos personales en texto plano).
* **1 Backend Único (`apps/backend-monolith`):** Monolito Modular con dominios desacoplados (`iam_users`, `students_padron`, `attendance_events`, `enrollments`, `telegram_bot`).
* **2 Frontends Especializados con UI Híbrida (Atomic UI Kit + Feature-Sliced):**
  * `apps/web-client` (**React + Vite**): Consola administrativa de escritorio para carga masiva de Excel, generación de lotes PDF de tarjetas QR, cierre de eventos, reportes e inscripciones.
  * `apps/mobile-client` (**React Native + Expo**): Aplicación nativa de campo para escaneo QR continuo e idempotente (`UPSERT`), registro de bitácora y captura fotográfica de justificaciones.
* **Diccionario Compartido (`packages/shared`):** Design Tokens, interfaces TypeScript de dominio y reglas de negocio compartidas entre Web y Móvil.
* **Infraestructura de Datos (`supabase/`):** PostgreSQL con *Row Level Security (RLS)*, autenticación híbrida (correo real o `username` con correo sintético transparente `@catequesis.local`) y almacenamiento privado de evidencias.

## Estructura del Monorepo

```text
catepass-monorepo/
├── apps/
│   ├── web-client/          # Frontend 1: Portal Web (React + Vite)
│   ├── mobile-client/       # Frontend 2: App Móvil de Campo (React Native + Expo)
│   └── backend-monolith/    # Backend Único: Monolito Modular (FastAPI)
├── packages/
│   └── shared/              # Design Tokens, Tipos TypeScript y Constantes
└── supabase/                # Migraciones SQL, Políticas RLS y Seeding (Admin Cero)