import type { InterpolationMetric } from '../../features/sensors/model/interpolation'
import type { ColorMode } from '../../features/sensors/model/colorMode'
import { getAqiColor, getPaletteGradient } from './aqi-color-palette'

export type ColorStop = {
  t: number
  rgb: [number, number, number]
}

export const TEMPERATURE_COLOR_STOPS: ColorStop[] = [
  { t: 0, rgb: [77, 146, 232] },
  { t: 0.5, rgb: [132, 227, 176] },
  { t: 1, rgb: [255, 111, 97] },
]

export const RELATIVE_BLUE: [number, number, number] = [38, 102, 255]
export const RELATIVE_WHITE: [number, number, number] = [240, 242, 245]
export const RELATIVE_RED: [number, number, number] = [255, 65, 85]

export const AQI_RELATIVE_LIGHT_GREEN: [number, number, number] = [144, 238, 144]
export const AQI_RELATIVE_DEEP_PURPLE: [number, number, number] = [75, 0, 130]

export const RELATIVE_COLOR_RANGE: Record<InterpolationMetric, number> = {
  temperature: 1.2,
  aqi: 6,
}

function clamp(value: number, minValue: number, maxValue: number): number {
  return Math.max(minValue, Math.min(maxValue, value))
}

function interpolateRgb(
  left: [number, number, number],
  right: [number, number, number],
  t: number,
): [number, number, number] {
  const localT = clamp(t, 0, 1)
  return [
    Math.round(left[0] + (right[0] - left[0]) * localT),
    Math.round(left[1] + (right[1] - left[1]) * localT),
    Math.round(left[2] + (right[2] - left[2]) * localT),
  ]
}

export function valueToColorFromStops(
  value: number,
  minValue: number,
  maxValue: number,
  stops: ColorStop[],
  alpha: number,
): [number, number, number, number] {
  const normalized =
    maxValue > minValue ? clamp((value - minValue) / (maxValue - minValue), 0, 1) : 0.5

  let left = stops[0]
  let right = stops[stops.length - 1]

  for (let index = 0; index < stops.length - 1; index += 1) {
    const current = stops[index]
    const next = stops[index + 1]
    if (normalized >= current.t && normalized <= next.t) {
      left = current
      right = next
      break
    }
  }

  const span = right.t - left.t
  const localT = span > 0 ? (normalized - left.t) / span : 0

  return [
    Math.round(left.rgb[0] + (right.rgb[0] - left.rgb[0]) * localT),
    Math.round(left.rgb[1] + (right.rgb[1] - left.rgb[1]) * localT),
    Math.round(left.rgb[2] + (right.rgb[2] - left.rgb[2]) * localT),
    alpha,
  ]
}

export function computeFrameMean(values: ArrayLike<number>): number {
  let sum = 0
  let count = 0

  for (let i = 0; i < values.length; i += 1) {
    const value = values[i]
    if (!Number.isFinite(value)) {
      continue
    }
    sum += value
    count += 1
  }

  if (count === 0) {
    return 0
  }

  return sum / count
}

export function computeRelativeRange(
  values: ArrayLike<number>,
  frameMean: number,
  metric: InterpolationMetric,
): number {
  let maxAbsDeviation = 0

  for (let i = 0; i < values.length; i += 1) {
    const value = values[i]
    if (!Number.isFinite(value)) {
      continue
    }
    const absDeviation = Math.abs(value - frameMean)
    if (absDeviation > maxAbsDeviation) {
      maxAbsDeviation = absDeviation
    }
  }

  return Math.max(maxAbsDeviation, RELATIVE_COLOR_RANGE[metric])
}

export function relativeValueToColor(
  relativeValue: number,
  relativeRange: number,
  metric: InterpolationMetric,
  alpha: number,
): [number, number, number, number] {
  const safeRange = Math.max(relativeRange, 1e-6)
  const absValue = Math.abs(relativeValue)
  const normalized = clamp(absValue / safeRange, 0, 1)

  let rgb: [number, number, number]

  if (metric === 'aqi') {
    // AQI uses light green to deep purple gradient for difference magnitude
    rgb = interpolateRgb(AQI_RELATIVE_LIGHT_GREEN, AQI_RELATIVE_DEEP_PURPLE, normalized)
  } else {
    // Temperature uses blue-white-red diverging gradient
    const signedNormalized = clamp((relativeValue / safeRange + 1) * 0.5, 0, 1)
    rgb = signedNormalized <= 0.5
      ? interpolateRgb(RELATIVE_BLUE, RELATIVE_WHITE, signedNormalized / 0.5)
      : interpolateRgb(RELATIVE_WHITE, RELATIVE_RED, (signedNormalized - 0.5) / 0.5)
  }

  return [rgb[0], rgb[1], rgb[2], alpha]
}

export function resolveColorValueRgba(
  value: number,
  metric: InterpolationMetric,
  colorMode: ColorMode,
  absoluteMinValue: number,
  absoluteMaxValue: number,
  frameMean: number,
  relativeRange: number,
  alpha: number,
): [number, number, number, number] {
  if (colorMode === 'relative') {
    return relativeValueToColor(value - frameMean, relativeRange, metric, alpha)
  }

  if (metric === 'aqi') {
    return getAqiColor(value, absoluteMinValue, absoluteMaxValue, alpha)
  }

  return valueToColorFromStops(
    value,
    absoluteMinValue,
    absoluteMaxValue,
    TEMPERATURE_COLOR_STOPS,
    alpha,
  )
}

function toCssGradient(
  stops: Array<{ t: number; rgb: [number, number, number] }>,
  direction: 'to right' | 'to bottom' = 'to right',
): string {
  const tokens = stops.map((stop) => {
    const percent = Math.round(stop.t * 100)
    return `rgb(${stop.rgb[0]}, ${stop.rgb[1]}, ${stop.rgb[2]}) ${percent}%`
  })
  return `linear-gradient(${direction}, ${tokens.join(', ')})`
}

export function getLegendGradient(
  metric: InterpolationMetric,
  colorMode: ColorMode,
  vertical: boolean = false,
): string {
  const direction = vertical ? 'to bottom' : 'to right'
  
  if (colorMode === 'relative') {
    if (metric === 'aqi') {
      // Vertical: max at top, min at bottom (reverse order)
      const stops = vertical
        ? [
            { t: 0, rgb: AQI_RELATIVE_DEEP_PURPLE },
            { t: 1, rgb: AQI_RELATIVE_LIGHT_GREEN },
          ]
        : [
            { t: 0, rgb: AQI_RELATIVE_LIGHT_GREEN },
            { t: 1, rgb: AQI_RELATIVE_DEEP_PURPLE },
          ]
      return toCssGradient(stops, direction)
    }
    // Vertical: max at top, min at bottom (reverse order)
    const stops = vertical
      ? [
          { t: 0, rgb: RELATIVE_RED },
          { t: 0.5, rgb: RELATIVE_WHITE },
          { t: 1, rgb: RELATIVE_BLUE },
        ]
      : [
          { t: 0, rgb: RELATIVE_BLUE },
          { t: 0.5, rgb: RELATIVE_WHITE },
          { t: 1, rgb: RELATIVE_RED },
        ]
    return toCssGradient(stops, direction)
  }

  if (metric === 'aqi') {
    return getPaletteGradient(direction, vertical)
  }

  // Vertical: reverse temperature stops for top-to-bottom
  const stops = vertical
    ? [
        { t: 0, rgb: TEMPERATURE_COLOR_STOPS[2].rgb },
        { t: 0.5, rgb: TEMPERATURE_COLOR_STOPS[1].rgb },
        { t: 1, rgb: TEMPERATURE_COLOR_STOPS[0].rgb },
      ]
    : TEMPERATURE_COLOR_STOPS
  return toCssGradient(stops, direction)
}
