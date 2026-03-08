/**
 * Centralized AQI color palette for 2D/3D surface and legend.
 * Uses the standard EPA AQI category colors mapped to actual AQI values.
 */

export interface ColorStop {
  aqi: number
  rgb: [number, number, number]
}

/**
 * Standard EPA AQI category colors:
 * 0-50: Good (Green)
 * 51-100: Moderate (Yellow)
 * 101-150: Unhealthy for Sensitive Groups (Orange)
 * 151-200: Unhealthy (Red)
 * 201-300: Very Unhealthy (Purple)
 * 301-500: Hazardous (Maroon)
 */
export const AQI_COLOR_PALETTE: ColorStop[] = [
  { aqi: 0, rgb: [0, 228, 0] },
  { aqi: 50, rgb: [255, 255, 0] },
  { aqi: 100, rgb: [255, 126, 0] },
  { aqi: 150, rgb: [255, 0, 0] },
  { aqi: 200, rgb: [143, 63, 151] },
  { aqi: 300, rgb: [126, 0, 35] },
  { aqi: 500, rgb: [126, 0, 35] },
]

/**
 * Get RGBA color for an AQI value.
 * Uses actual AQI values (not normalized) and interpolates between
 * standard EPA AQI category breakpoints.
 */
export function getAqiColor(
  value: number,
  _minValue: number,
  _maxValue: number,
  alpha: number = 255,
): [number, number, number, number] {
  const clampedAqi = Math.max(0, Math.min(500, value))

  let left = AQI_COLOR_PALETTE[0]
  let right = AQI_COLOR_PALETTE[AQI_COLOR_PALETTE.length - 1]

  for (let i = 0; i < AQI_COLOR_PALETTE.length - 1; i += 1) {
    const current = AQI_COLOR_PALETTE[i]
    const next = AQI_COLOR_PALETTE[i + 1]
    if (clampedAqi >= current.aqi && clampedAqi <= next.aqi) {
      left = current
      right = next
      break
    }
  }

  const span = right.aqi - left.aqi
  const localT = span > 0 ? (clampedAqi - left.aqi) / span : 0

  return [
    Math.round(left.rgb[0] + (right.rgb[0] - left.rgb[0]) * localT),
    Math.round(left.rgb[1] + (right.rgb[1] - left.rgb[1]) * localT),
    Math.round(left.rgb[2] + (right.rgb[2] - left.rgb[2]) * localT),
    Math.round(alpha),
  ]
}

/**
 * Get palette stops for legend rendering.
 * Returns array of [position (0-1), color (rgb)].
 */
export function getPaletteStops(): Array<{ position: number; color: string }> {
  return AQI_COLOR_PALETTE.slice(0, -1).map((stop) => ({
    position: stop.aqi / 300,
    color: `rgb(${stop.rgb[0]}, ${stop.rgb[1]}, ${stop.rgb[2]})`,
  }))
}

/**
 * Generate a smooth gradient CSS string for legend bar.
 * Converts palette to CSS linear-gradient format.
 * Uses 0-300 range for legend display (showing common AQI values).
 */
export function getPaletteGradient(
  direction: 'to right' | 'to bottom' = 'to right',
  reverse: boolean = false,
): string {
  const baseStops = AQI_COLOR_PALETTE.slice(0, -1)
  const orderedStops = reverse ? [...baseStops].reverse() : baseStops

  const stops = orderedStops.map((stop) => {
    const color = `rgb(${stop.rgb[0]}, ${stop.rgb[1]}, ${stop.rgb[2]})`
    const basePercent = Math.round((stop.aqi / 300) * 100)
    const percent = reverse ? 100 - basePercent : basePercent
    return `${color} ${percent}%`
  }).join(', ')

  return `linear-gradient(${direction}, ${stops})`
}
