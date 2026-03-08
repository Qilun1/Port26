import type {
  InterpolatedGrid,
  InterpolationMetric,
} from '../../features/sensors/model/interpolation'

const CELL_PIXEL_RESOLUTION = 12

type ColorStop = {
  t: number
  rgb: [number, number, number]
}

type GridMatrix = {
  values: Array<Array<number | null>>
  rowCount: number
  colCount: number
}

export type InterpolationSurface = {
  url: string
  coordinates: [[number, number], [number, number], [number, number], [number, number]]
}

function clamp(value: number, minValue: number, maxValue: number): number {
  return Math.max(minValue, Math.min(maxValue, value))
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

function toGridMatrix(grid: InterpolatedGrid): GridMatrix | null {
  if (grid.points.length === 0) {
    return null
  }

  const rowCount = Math.max(...grid.points.map((point) => point.row)) + 1
  const colCount = Math.max(...grid.points.map((point) => point.col)) + 1

  if (rowCount <= 0 || colCount <= 0) {
    return null
  }

  const values: Array<Array<number | null>> = Array.from({ length: rowCount }, () =>
    Array.from({ length: colCount }, () => null),
  )

  for (const point of grid.points) {
    values[point.row][point.col] = point.interpolatedValue
  }

  return {
    values,
    rowCount,
    colCount,
  }
}

function bilinearFromCorners(
  v00: number | null,
  v10: number | null,
  v01: number | null,
  v11: number | null,
  tx: number,
  ty: number,
): number | null {
  const corners: Array<[number | null, number]> = [
    [v00, (1 - tx) * (1 - ty)],
    [v10, tx * (1 - ty)],
    [v01, (1 - tx) * ty],
    [v11, tx * ty],
  ]

  let weightedSum = 0
  let weightTotal = 0

  for (const [value, weight] of corners) {
    if (value === null || weight <= 0) {
      continue
    }

    weightedSum += value * weight
    weightTotal += weight
  }

  if (weightTotal <= 0) {
    return null
  }

  return weightedSum / weightTotal
}

function sampleBilinear(matrix: GridMatrix, gx: number, gy: number): number | null {
  const x0 = clamp(Math.floor(gx), 0, matrix.colCount - 1)
  const y0 = clamp(Math.floor(gy), 0, matrix.rowCount - 1)
  const x1 = clamp(x0 + 1, 0, matrix.colCount - 1)
  const y1 = clamp(y0 + 1, 0, matrix.rowCount - 1)

  const tx = clamp(gx - x0, 0, 1)
  const ty = clamp(gy - y0, 0, 1)

  return bilinearFromCorners(
    matrix.values[y0][x0],
    matrix.values[y0][x1],
    matrix.values[y1][x0],
    matrix.values[y1][x1],
    tx,
    ty,
  )
}

function getValueRange(matrix: GridMatrix): { minValue: number; maxValue: number } | null {
  const values = matrix.values.flat().filter((value): value is number => value !== null)
  if (values.length === 0) {
    return null
  }

  return {
    minValue: Math.min(...values),
    maxValue: Math.max(...values),
  }
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

export function createInterpolationSurface(
  grid: InterpolatedGrid,
  metric: InterpolationMetric,
): InterpolationSurface | null {
  if (typeof document === 'undefined') {
    return null
  }

  const matrix = toGridMatrix(grid)
  if (!matrix) {
    return null
  }

  const range = getValueRange(matrix)
  if (!range) {
    return null
  }

  const width = Math.max(2, ((matrix.colCount - 1) * CELL_PIXEL_RESOLUTION) + 1)
  const height = Math.max(2, ((matrix.rowCount - 1) * CELL_PIXEL_RESOLUTION) + 1)

  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height

  const context = canvas.getContext('2d')
  if (!context) {
    return null
  }

  const image = context.createImageData(width, height)
  const stops = getColorStops(metric)

  for (let y = 0; y < height; y += 1) {
    const gy = ((height - 1 - y) / Math.max(1, height - 1)) * (matrix.rowCount - 1)

    for (let x = 0; x < width; x += 1) {
      const gx = (x / Math.max(1, width - 1)) * (matrix.colCount - 1)
      const value = sampleBilinear(matrix, gx, gy)

      const index = (y * width + x) * 4
      if (value === null) {
        image.data[index] = 0
        image.data[index + 1] = 0
        image.data[index + 2] = 0
        image.data[index + 3] = 0
        continue
      }

      const [r, g, b, a] = valueToColor(value, range.minValue, range.maxValue, stops)
      image.data[index] = r
      image.data[index + 1] = g
      image.data[index + 2] = b
      image.data[index + 3] = a
    }
  }

  context.putImageData(image, 0, 0)

  const box = grid.boundingBox
  return {
    url: canvas.toDataURL('image/png'),
    coordinates: [
      [box.minLongitude, box.maxLatitude],
      [box.maxLongitude, box.maxLatitude],
      [box.maxLongitude, box.minLatitude],
      [box.minLongitude, box.minLatitude],
    ],
  }
}
