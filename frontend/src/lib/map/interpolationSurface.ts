import type {
  InterpolationBoundingBox,
  InterpolationMetric,
} from '../../features/sensors/model/interpolation'
import type { ColorMode } from '../../features/sensors/model/colorMode'
import {
  resolveColorValueRgba,
  computeFrameMean,
  computeRelativeRange,
  TEMPERATURE_COLOR_STOPS,
} from './colorScales'

export type InterpolationSurface = {
  url: string
  coordinates: [[number, number], [number, number], [number, number], [number, number]]
}

export type SparseSurfaceContext = {
  width: number
  height: number
  pixelOffsets: number[]
  edgeDistances: number[]
  minValue: number
  maxValue: number
  coordinates: [[number, number], [number, number], [number, number], [number, number]]
}

function resolveCoordinates(
  box: InterpolationBoundingBox,
): [[number, number], [number, number], [number, number], [number, number]] {
  return [
    [box.minLongitude, box.maxLatitude],
    [box.maxLongitude, box.maxLatitude],
    [box.maxLongitude, box.minLatitude],
    [box.minLongitude, box.minLatitude],
  ]
}

function toPixelOffset(index: number, cols: number, rows: number): number {
  const row = Math.floor(index / cols)
  const col = index % cols
  const y = (rows - 1) - row
  return ((y * cols) + col) * 4
}

export function valueToColor(
  value: number,
  minValue: number,
  maxValue: number,
  stops: Array<{ t: number; rgb: [number, number, number] }>,
): [number, number, number, number] {
  const normalized =
    maxValue > minValue ? Math.max(0, Math.min(1, (value - minValue) / (maxValue - minValue))) : 0.5

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
    184,
  ]
}

export function getColorStops(_metric: InterpolationMetric): Array<{ t: number; rgb: [number, number, number] }> {
  return TEMPERATURE_COLOR_STOPS
}

function computeEdgeDistancesFor2D(
  rows: number,
  cols: number,
  activeIndices: number[],
): number[] {
  const gridLength = rows * cols
  const indexToVertex = new Int32Array(gridLength)
  indexToVertex.fill(-1)

  for (let i = 0; i < activeIndices.length; i += 1) {
    indexToVertex[activeIndices[i]] = i
  }

  const isActive = (row: number, col: number): boolean => {
    if (row < 0 || row >= rows || col < 0 || col >= cols) {
      return false
    }
    const gridIndex = row * cols + col
    return indexToVertex[gridIndex] >= 0
  }

  const edgeDistances: number[] = []

  for (const gridIndex of activeIndices) {
    const row = Math.floor(gridIndex / cols)
    const col = gridIndex % cols

    let minDistanceToEdge = Infinity

    for (let radius = 1; radius <= Math.max(rows, cols); radius += 1) {
      let foundInactive = false

      for (let dr = -radius; dr <= radius; dr += 1) {
        for (let dc = -radius; dc <= radius; dc += 1) {
          if (Math.max(Math.abs(dr), Math.abs(dc)) !== radius) {
            continue
          }

          if (!isActive(row + dr, col + dc)) {
            foundInactive = true
            const dist = Math.sqrt(dr * dr + dc * dc)
            minDistanceToEdge = Math.min(minDistanceToEdge, dist)
          }
        }
      }

      if (foundInactive) {
        break
      }
    }

    edgeDistances.push(minDistanceToEdge)
  }

  return edgeDistances
}

export function buildSparseSurfaceContext(
  rows: number,
  cols: number,
  boundingBox: InterpolationBoundingBox,
  activeIndices: number[],
  timelineFrameValues: number[][],
): SparseSurfaceContext | null {
  if (rows <= 0 || cols <= 0 || activeIndices.length === 0) {
    return null
  }

  const gridLength = rows * cols
  const pixelOffsets: number[] = []
  let previousIndex = -1

  for (const index of activeIndices) {
    if (index <= previousIndex || index < 0 || index >= gridLength) {
      return null
    }

    pixelOffsets.push(toPixelOffset(index, cols, rows))
    previousIndex = index
  }

  let minValue = Number.POSITIVE_INFINITY
  let maxValue = Number.NEGATIVE_INFINITY

  for (const frameValues of timelineFrameValues) {
    if (frameValues.length !== activeIndices.length) {
      return null
    }

    for (const value of frameValues) {
      if (!Number.isFinite(value)) {
        continue
      }
      minValue = Math.min(minValue, value)
      maxValue = Math.max(maxValue, value)
    }
  }

  if (!Number.isFinite(minValue) || !Number.isFinite(maxValue)) {
    return null
  }

  const edgeDistances = computeEdgeDistancesFor2D(rows, cols, activeIndices)

  return {
    width: cols,
    height: rows,
    pixelOffsets,
    edgeDistances,
    minValue,
    maxValue,
    coordinates: resolveCoordinates(boundingBox),
  }
}

export function createSparseInterpolationSurface(
  contextData: SparseSurfaceContext,
  metric: InterpolationMetric,
  colorMode: ColorMode,
  frameValues: ArrayLike<number>,
  relativeRangeOverride: number | null,
): InterpolationSurface | null {
  if (typeof document === 'undefined') {
    return null
  }
  if (frameValues.length !== contextData.pixelOffsets.length) {
    return null
  }

  const canvas = document.createElement('canvas')
  canvas.width = contextData.width
  canvas.height = contextData.height

  const context = canvas.getContext('2d')
  if (!context) {
    return null
  }

  const image = context.createImageData(contextData.width, contextData.height)
  const frameMean = computeFrameMean(frameValues)
  const relativeRange = Number.isFinite(relativeRangeOverride)
    ? Number(relativeRangeOverride)
    : computeRelativeRange(frameValues, frameMean, metric)

  const edgeFadeStart = 8.0
  const edgeFadeEnd = 0.3

  for (let i = 0; i < frameValues.length; i += 1) {
    const offset = contextData.pixelOffsets[i]
    const [r, g, b, a] = resolveColorValueRgba(
      frameValues[i],
      metric,
      colorMode,
      contextData.minValue,
      contextData.maxValue,
      frameMean,
      relativeRange,
      184,
    )

    const edgeDistance = contextData.edgeDistances[i]
    const edgeAlpha = Math.max(0, Math.min(1,
      (edgeDistance - edgeFadeEnd) / (edgeFadeStart - edgeFadeEnd)
    ))
    const finalAlpha = Math.round(a * edgeAlpha)

    image.data[offset] = r
    image.data[offset + 1] = g
    image.data[offset + 2] = b
    image.data[offset + 3] = finalAlpha
  }

  context.putImageData(image, 0, 0)
  return {
    url: canvas.toDataURL('image/png'),
    coordinates: contextData.coordinates,
  }
}
