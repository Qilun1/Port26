export const theme = {
  colors: {
    background: '#0c1117',
    card: '#141b23',
    cardBorder: '#2a3441',
    textPrimary: '#f3f7fc',
    textSecondary: '#a9b7c8',
    sensorMarker: '#5dc4ff',
    sensorMarkerHover: '#7dd2ff',
    sensorMarkerStroke: '#d9f3ff',
  },
  shadows: {
    marker: '0 0 16px rgba(93, 196, 255, 0.65)',
    tooltip: '0 14px 34px rgba(0, 0, 0, 0.46)',
  },
  radius: {
    sm: '8px',
    md: '12px',
    full: '999px',
  },
  fonts: {
    body: '"Segoe UI", "Segoe UI Variable", "Inter", sans-serif',
    mono: '"Cascadia Code", "Consolas", monospace',
  },
} as const
