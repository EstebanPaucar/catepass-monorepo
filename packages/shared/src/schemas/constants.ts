/**
 * Constantes globales y enumeraciones de negocio para CatePass.
 * Sincronizado con los tipos ENUM de PostgreSQL en Supabase (Sección 5).
 */

export const SYNTHETIC_EMAIL_DOMAIN = 'catequesis.local' as const;

export const USER_ROLES = {
  ADMIN: 'admin',
  CATEQUISTA: 'catequista',
} as const;

export type UserRole = (typeof USER_ROLES)[keyof typeof USER_ROLES];

export const PASE_NIVEL_STATUS = {
  NO_REQUIERE: 'no_requiere',
  FALTANTE: 'faltante',
  ENTREGADO: 'entregado',
} as const;

export type PaseNivelStatus = (typeof PASE_NIVEL_STATUS)[keyof typeof PASE_NIVEL_STATUS];

export const FE_BAUTIZO_STATUS = {
  FALTANTE: 'faltante',
  ENTREGADO: 'entregado',
} as const;

export type FeBautizoStatus = (typeof FE_BAUTIZO_STATUS)[keyof typeof FE_BAUTIZO_STATUS];

export const EVENT_TYPES = {
  REGULAR: 'regular',
  ADMIN: 'admin',
} as const;

export type EventType = (typeof EVENT_TYPES)[keyof typeof EVENT_TYPES];

export const EVENT_STATUS = {
  ABIERTO: 'abierto',
  CERRADO: 'cerrado',
} as const;

export type EventStatus = (typeof EVENT_STATUS)[keyof typeof EVENT_STATUS];

export const ATTENDANCE_STATUS = {
  PRESENTE: 'presente',
  FALTA: 'falta',
  JUSTIFICADO: 'justificado',
} as const;

export type AttendanceStatus = (typeof ATTENDANCE_STATUS)[keyof typeof ATTENDANCE_STATUS];

/**
 * Convierte un username sin correo electrónico en un correo sintético
 * compatible con Supabase Auth (Sección 3.2 - Opción B).
 */
export function buildSyntheticEmail(username: string): string {
  const cleanUsername = username.trim().toLowerCase().replace(/[^a-z0-9._-]/g, '');
  return `${cleanUsername}@${SYNTHETIC_EMAIL_DOMAIN}`;
}