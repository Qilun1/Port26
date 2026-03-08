import type { InterpolationMetric } from '../../features/sensors/model/interpolation'
import type { ColorMode } from '../../features/sensors/model/colorMode'
import {
  computeFrameMean,
  computeRelativeRange,
  resolveColorValueRgba,
} from './colorScales'

export const SURFACE_HEIGHT_SCALE_BY_METRIC: Record<InterpolationMetric, number> = {
  temperature: 72,
  aqi: 55,
}

export function getSurfaceHeightScale(metric: InterpolationMetric): number {
  return SURFACE_HEIGHT_SCALE_BY_METRIC[metric]
}

export function updateSurfaceNormalizedValues(
  frameValues: ArrayLike<number>,
  dailyMinValue: number,
  dailyMaxValue: number,
  outputNormalizedValues: Float32Array,
): void {
  const denominator = dailyMaxValue - dailyMinValue

  for (let i = 0; i < frameValues.length; i += 1) {
    const value = frameValues[i]
    const safeValue = Number.isFinite(value) ? value : dailyMinValue
    const normalized = denominator > 0
      ? Math.max(0, Math.min(1, (safeValue - dailyMinValue) / denominator))
      : 0.5

    outputNormalizedValues[i] = normalized
  }
}

export function updateSurfacePositions(
  basePositions: Float32Array,
  frameValues: ArrayLike<number>,
  heightAnchorValue: number,
  heightScale: number,
  outputPositions: Float32Array,
): void {
  const vertexCount = frameValues.length
  const safeAnchor = Number.isFinite(heightAnchorValue) ? heightAnchorValue : 0

  for (let i = 0; i < vertexCount; i += 1) {
    const offset = i * 3
    const value = frameValues[i]
    const safeValue = Number.isFinite(value) ? value : safeAnchor
    const height = (safeValue - safeAnchor) * heightScale

    outputPositions[offset] = basePositions[offset]
    outputPositions[offset + 1] = basePositions[offset + 1]
    outputPositions[offset + 2] = height
  }
}

export function updateSurfaceColors(
  frameValues: ArrayLike<number>,
  dailyMinValue: number,
  dailyMaxValue: number,
  metric: InterpolationMetric,
  colorMode: ColorMode,
  relativeRangeOverride: number | null,
  outputColors: Uint8Array,
): void {
  const frameMean = computeFrameMean(frameValues)
  const relativeRange = Number.isFinite(relativeRangeOverride)
    ? Number(relativeRangeOverride)
    : computeRelativeRange(frameValues, frameMean, metric)

  for (let i = 0; i < frameValues.length; i += 1) {
    const colorOffset = i * 4
    const value = frameValues[i]
    const safeValue = Number.isFinite(value) ? value : dailyMinValue
    const [r, g, b, a] = resolveColorValueRgba(
      safeValue,
      metric,
      colorMode,
      dailyMinValue,
      dailyMaxValue,
      frameMean,
      relativeRange,
      184,
    )
    outputColors[colorOffset] = r
    outputColors[colorOffset + 1] = g
    outputColors[colorOffset + 2] = b
    outputColors[colorOffset + 3] = a
  }
}
