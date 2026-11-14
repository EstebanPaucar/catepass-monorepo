import {
  AttendanceStatus,
  EventStatus,
  EventType,
  FeBautizoStatus,
  PaseNivelStatus,
  UserRole,
} from '../schemas/constants';

/**
 * Tabla 1: Users (IAM / Staff)
 * Modelo unificado para Administradores y Catequistas.
 */
export interface UserStaff {
  id: string; // UUID vinculado a auth.users
  username: string; // Único, obligatorio para login sin correo
  correo: string | null; // Nullable para usuarios con credenciales manuales
  requiere_cambio_clave: boolean; // Flag para forzar cambio de clave en 1er login
  nombres: string;
  apellidos: string;
  rol_enum: UserRole;
  nivel_id: string | null; // FK -> Niveles (nullable para administradores)
  fecha_nacimiento: string; // ISO Date (YYYY-MM-DD)
  edad_calculada?: number; // Calculada dinámicamente vía AGE(fecha_nacimiento)
  numero_telefono: string | null;
  observaciones: string | null;
  estado_activo: boolean;
}

/**
 * Tabla 2: Niveles
 * Agrupaciones académicas y pastorales de la catequesis con soporte de paralelos ('Único', 'A', 'B').
 */
export interface NivelCatequesis {
  id_nivel: string; // UUID PK
  nombre_nivel: string;
  paralelo: string; // 'Único' | 'A' | 'B'
  horario: string;
  estado_activo: boolean;
}

/**
 * Tabla 3: Estudiantes (Entidades Pasivas)
 * Registros para seguimiento de asistencia, requisitos sacramentales y vínculo con Telegram.
 */
export interface Estudiante {
  id_estudiante: string; // UUID v4 incrustado exclusivamente en el código QR
  codigo_referencia: string | null; // ID original proveniente del archivo Excel
  nombres: string;
  apellidos: string;
  nivel_id: string; // FK -> Niveles
  fecha_nacimiento: string | null; // ISO Date (nullable si viene solo edad del Excel)
  edad_registrada: number | null; // Respaldo de edad estática del Excel
  nombre_representante: string;
  numero_representante: string;
  telegram_chat_id: string | null; // Vínculo para notificaciones automáticas del Bot
  pase_nivel: PaseNivelStatus;
  fe_bautizo: FeBautizoStatus;
  observaciones: string | null;
  estado_activo: boolean;
}

/**
 * Tabla 4: Eventos
 * Gestión de sesiones regulares de catequesis, misas y eventos administrativos.
 */
export interface EventoAsistencia {
  id_evento: string; // UUID PK
  nombre_evento: string;
  fecha_programada: string; // ISO Date (YYYY-MM-DD)
  tipo: EventType; // 'regular' | 'admin'
  estado_evento: EventStatus; // 'abierto' | 'cerrado'
  nivel_id: string | null; // Nullable cuando es un evento masivo global
}

/**
 * Tabla 5: Bitacora_Eventos
 * Descripción de actividad obligatoria por catequista en eventos administrativos.
 * Restricción UNIQUE (evento_id, catequista_id).
 */
export interface BitacoraEvento {
  id_bitacora: string; // UUID PK
  evento_id: string; // FK -> Eventos
  catequista_id: string; // FK -> Users
  descripcion_actividad: string;
  fecha_registro: string; // TIMESTAMPTZ
}

/**
 * Tabla 6: Asistencia
 * Registros transaccionales de escaneo QR, cierres de inasistencia y justificaciones.
 * Restricción UNIQUE (estudiante_id, evento_id) para garantizar idempotencia.
 */
export interface RegistroAsistencia {
  id_asistencia: string; // UUID PK
  estudiante_id: string; // FK -> Estudiantes
  evento_id: string; // FK -> Eventos
  estado: AttendanceStatus; // 'presente' | 'falta' | 'justificado'
  url_evidencia: string | null; // Ruta privada en Supabase Storage
  catequista_registro_id: string | null; // FK -> Users
  fecha_hora_log: string; // TIMESTAMPTZ
}