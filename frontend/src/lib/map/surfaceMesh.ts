import { MercatorCoordinate } from 'maplibre-gl'
import type { InterpolationBoundingBox } from '../../features/sensors/model/interpolation'

export interface SurfaceMeshContext {
  basePositions: Float32Array
  edgeDistances: Float32Array
  indices: Uint16Array
  dailyMinValue: number
  dailyMaxValue: number
  meterToMercator: number
}

function toLatitude(row: number, rows: number, box: InterpolationBoundingBox): number {
  if (rows <= 1) {
    return box.minLatitude
  }

  // Backend row indexing grows south -> north (row 0 is minLatitude).
  const t = row / (rows - 1)
  return box.minLatitude + ((box.maxLatitude - box.minLatitude) * t)
}

function toLongitude(col: number, cols: number, box: InterpolationBoundingBox): number {
  if (cols <= 1) {
    return box.minLongitude
  }

  const t = col / (cols - 1)
  return box.minLongitude + ((box.maxLongitude - box.minLongitude) * t)
}

function resolveDailyValueRange(
  timelineFrameValues: number[][],
): { dailyMinValue: number; dailyMaxValue: number } | null {
  let dailyMinValue = Number.POSITIVE_INFINITY
  let dailyMaxValue = Number.NEGATIVE_INFINITY

  for (const frameValues of timelineFrameValues) {
    for (const value of frameValues) {
      if (!Number.isFinite(value)) {
        continue
      }
      dailyMinValue = Math.min(dailyMinValue, value)
      dailyMaxValue = Math.max(dailyMaxValue, value)
    }
  }

  if (!Number.isFinite(dailyMinValue) || !Number.isFinite(dailyMaxValue)) {
    return null
  }

  return { dailyMinValue, dailyMaxValue }
}

function computeEdgeDistances(
  rows: number,
  cols: number,
  activeIndices: number[],
  indexToVertex: Int32Array,
): Float32Array {
  const edgeDistances = new Float32Array(activeIndices.length)
  
  const isActive = (row: number, col: number): boolean => {
    if (row < 0 || row >= rows || col < 0 || col >= cols) {
      return false
    }
    const gridIndex = row * cols + col
    return indexToVertex[gridIndex] >= 0
  }

  for (let i = 0; i < activeIndices.length; i += 1) {
    const gridIndex = activeIndices[i]
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

    edgeDistances[i] = minDistanceToEdge
  }

  return edgeDistances
}

export function buildSurfaceMeshContext(
  rows: number,
  cols: number,
  boundingBox: InterpolationBoundingBox,
  activeIndices: number[],
  timelineFrameValues: number[][],
): SurfaceMeshContext | null {
  if (rows <= 1 || cols <= 1 || activeIndices.length === 0 || activeIndices.length > 65535) {
    return null
  }

  const gridLength = rows * cols
  const indexToVertex = new Int32Array(gridLength)
  indexToVertex.fill(-1)

  const basePositions = new Float32Array(activeIndices.length * 3)
  let previousGridIndex = -1

  for (let i = 0; i < activeIndices.length; i += 1) {
    const gridIndex = activeIndices[i]
    if (gridIndex <= previousGridIndex || gridIndex < 0 || gridIndex >= gridLength) {
      return null
    }

    previousGridIndex = gridIndex
    indexToVertex[gridIndex] = i

    const row = Math.floor(gridIndex / cols)
    const col = gridIndex % cols
    const latitude = toLatitude(row, rows, boundingBox)
    const longitude = toLongitude(col, cols, boundingBox)
    const mercator = MercatorCoordinate.fromLngLat({ lng: longitude, lat: latitude }, 0)

    const offset = i * 3
    basePositions[offset] = mercator.x
    basePositions[offset + 1] = mercator.y
    basePositions[offset + 2] = 0
  }

  const edgeDistances = computeEdgeDistances(rows, cols, activeIndices, indexToVertex)

  for (const frameValues of timelineFrameValues) {
    if (frameValues.length !== activeIndices.length) {
      return null
    }
  }

  const indexBuffer: number[] = []

  for (let row = 0; row < rows - 1; row += 1) {
    for (let col = 0; col < cols - 1; col += 1) {
      const topLeft = row * cols + col
      const bottomLeft = (row + 1) * cols + col
      const topRight = row * cols + (col + 1)
      const bottomRight = (row + 1) * cols + (col + 1)

      const a = indexToVertex[topLeft]
      const b = indexToVertex[bottomLeft]
      const c = indexToVertex[topRight]
      const d = indexToVertex[bottomRight]

      if (a < 0 || b < 0 || c < 0 || d < 0) {
        continue
      }

      indexBuffer.push(a, b, c)
      indexBuffer.push(b, d, c)
    }
  }

  if (indexBuffer.length === 0) {
    return null
  }

  const valueRange = resolveDailyValueRange(timelineFrameValues)
  if (!valueRange) {
    return null
  }

  const centerLatitude = (boundingBox.minLatitude + boundingBox.maxLatitude) * 0.5
  const centerLongitude = (boundingBox.minLongitude + boundingBox.maxLongitude) * 0.5
  const centerMercator = MercatorCoordinate.fromLngLat({ lng: centerLongitude, lat: centerLatitude }, 0)

  return {
    basePositions,
    edgeDistances,
    indices: Uint16Array.from(indexBuffer),
    dailyMinValue: valueRange.dailyMinValue,
    dailyMaxValue: valueRange.dailyMaxValue,
    meterToMercator: centerMercator.meterInMercatorCoordinateUnits(),
  }
}
