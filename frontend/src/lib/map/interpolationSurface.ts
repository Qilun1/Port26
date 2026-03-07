import type {
  InterpolationBoundingBox,
  InterpolationMetric,
} from '../../features/sensors/model/interpolation'

type ColorStop = {
  t: number
  rgb: [number, number, number]
}

export type InterpolationSurface = {
  url: string
  coordinates: [[number, number], [number, number], [number, number], [number, number]]
}

export type SparseSurfaceContext = {
  width: number
  height: number
  pixelOffsets: number[]
  minValue: number
  maxValue: number
  coordinates: [[number, number], [number, number], [number, number], [number, number]]
}

function clamp(value: number, minValue: number, maxValue: number): number {
  return Math.max(minValue, Math.min(maxValue, value))
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

function getColorStops(metric: InterpolationMetric): ColorStop[] {
  if (metric === 'aqi') {
    return [
      { t: 0, rgb: [74, 198, 117] },
      { t: 0.5, rgb: [244, 211, 94] },
      { t: 1, rgb: [248, 90, 62] },
    ]
  }

  return [
    { t: 0, rgb: [77, 146, 232] },
    { t: 0.5, rgb: [132, 227, 176] },
    { t: 1, rgb: [255, 111, 97] },
  ]
}

function valueToColor(
  value: number,
  minValue: number,
  maxValue: number,
  stops: ColorStop[],
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
    184,
  ]
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

  return {
    width: cols,
    height: rows,
    pixelOffsets,
    minValue,
    maxValue,
    coordinates: resolveCoordinates(boundingBox),
  }
}

export function createSparseInterpolationSurface(
  contextData: SparseSurfaceContext,
  metric: InterpolationMetric,
  frameValues: ArrayLike<number>,
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
  const stops = getColorStops(metric)

  for (let i = 0; i < frameValues.length; i += 1) {
    const offset = contextData.pixelOffsets[i]
    const [r, g, b, a] = valueToColor(
      frameValues[i],
      contextData.minValue,
      contextData.maxValue,
      stops,
    )
    image.data[offset] = r
    image.data[offset + 1] = g
    image.data[offset + 2] = b
    image.data[offset + 3] = a
  }

  context.putImageData(image, 0, 0)
  return {
    url: canvas.toDataURL('image/png'),
    coordinates: contextData.coordinates,
  }
}
