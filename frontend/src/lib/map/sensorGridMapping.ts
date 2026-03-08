import type { InterpolationTimeline } from '../../features/sensors/model/interpolationTimeline'
import type { Sensor } from '../../features/sensors/model/sensor'

function clamp(value: number, minValue: number, maxValue: number): number {
  return Math.max(minValue, Math.min(maxValue, value))
}

function toGridIndexFromSensor(sensor: Sensor, timeline: InterpolationTimeline): number {
  const latSpan = timeline.boundingBox.maxLatitude - timeline.boundingBox.minLatitude
  const lonSpan = timeline.boundingBox.maxLongitude - timeline.boundingBox.minLongitude

  const latRatio = latSpan > 0
    ? clamp((sensor.latitude - timeline.boundingBox.minLatitude) / latSpan, 0, 1)
    : 0.5

  const lonRatio = lonSpan > 0
    ? clamp((sensor.longitude - timeline.boundingBox.minLongitude) / lonSpan, 0, 1)
    : 0.5

  const row = Math.round(latRatio * (timeline.rows - 1))
  const col = Math.round(lonRatio * (timeline.cols - 1))
  return (row * timeline.cols) + col
}

/**
 * Maps each sensor to a frame index in the active interpolation values array.
 * Prefers exact grid matches and falls back to nearest active grid point.
 */
export function buildNearestFrameIndexBySensorId(
  sensors: Sensor[],
  timeline: InterpolationTimeline | null,
): Map<string, number | null> {
  const result = new Map<string, number | null>()

  if (!timeline || timeline.activeIndices.length === 0) {
    for (const sensor of sensors) {
      result.set(sensor.id, null)
    }
    return result
  }

  const directIndexMap = new Map<number, number>()
  const activeGridPoints = timeline.activeIndices.map((gridIndex, frameIndex) => ({
    frameIndex,
    row: Math.floor(gridIndex / timeline.cols),
    col: gridIndex % timeline.cols,
  }))

  for (let frameIndex = 0; frameIndex < timeline.activeIndices.length; frameIndex += 1) {
    directIndexMap.set(timeline.activeIndices[frameIndex], frameIndex)
  }

  for (const sensor of sensors) {
    const gridIndex = toGridIndexFromSensor(sensor, timeline)
    const directFrameIndex = directIndexMap.get(gridIndex)

    if (typeof directFrameIndex === 'number') {
      result.set(sensor.id, directFrameIndex)
      continue
    }

    const targetRow = Math.floor(gridIndex / timeline.cols)
    const targetCol = gridIndex % timeline.cols

    let nearestFrameIndex: number | null = null
    let bestDistance = Number.POSITIVE_INFINITY

    for (const point of activeGridPoints) {
      const dr = point.row - targetRow
      const dc = point.col - targetCol
      const squaredDistance = (dr * dr) + (dc * dc)

      if (squaredDistance < bestDistance) {
        bestDistance = squaredDistance
        nearestFrameIndex = point.frameIndex
      }
    }

    result.set(sensor.id, nearestFrameIndex)
  }

  return result
}
