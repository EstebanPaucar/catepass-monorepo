/**
 * Nivel 1 — Design Tokens Compartidos (Sección 6.2 - ADR-04)
 * Garantiza consistencia visual entre el Portal Web (React) y la App Móvil (Expo).
 */

export const COLORS = {
  brand: {
    primary: '#1E3A8A', // Azul Institucional Profundo
    primaryLight: '#2563EB',
    secondary: '#0F766E', // Verde Azulado Pastoral
    background: '#F8FAFC',
    surface: '#FFFFFF',
  },
  attendanceStatus: {
    presente: {
      bg: '#DCFCE7',
      text: '#166534',
      border: '#22C55E',
    },
    falta: {
      bg: '#FEE2E2',
      text: '#991B1B',
      border: '#EF4444',
    },
    justificado: {
      bg: '#FEF3C7',
      text: '#92400E',
      border: '#F59E0B',
    },
  },
  neutral: {
    textPrimary: '#1F2937',
    textSecondary: '#4B5563',
    border: '#D1D5DB',
  },
} as const;