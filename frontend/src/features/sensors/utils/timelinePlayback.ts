import type { InterpolationTimeline } from '../model/interpolationTimeline'

export const MINUTES_PER_DAY = 24 * 60
export const SOURCE_FRAME_INTERVAL_MINUTES = 15
export const PLAYBACK_SIMULATED_MINUTES_PER_SECOND = 4

export type MinuteFrameBlendWindow = {
  startFrameIndex: number
  endFrameIndex: number
  t: number
}

export function clampMinuteIndex(minuteIndex: number): number {
  if (!Number.isFinite(minuteIndex)) {
    return 0
  }

  const rounded = Math.floor(minuteIndex)
  return Math.max(0, Math.min(MINUTES_PER_DAY - 1, rounded))
}

export function resolveMinuteFrameBlendWindow(
  minuteIndex: number,
  frameCount: number,
): MinuteFrameBlendWindow {
  if (frameCount <= 0) {
    return {
      startFrameIndex: 0,
      endFrameIndex: 0,
      t: 0,
    }
  }

  const safeMinute = clampMinuteIndex(minuteIndex)
  const maxFrameIndex = frameCount - 1
  const segmentIndex = Math.floor(safeMinute / SOURCE_FRAME_INTERVAL_MINUTES)
  const startFrameIndex = Math.min(segmentIndex, maxFrameIndex)
  const endFrameIndex = Math.min(startFrameIndex + 1, maxFrameIndex)

  if (startFrameIndex === endFrameIndex) {
    return {
      startFrameIndex,
      endFrameIndex,
      t: 0,
    }
  }

  const minuteOffset = safeMinute - (segmentIndex * SOURCE_FRAME_INTERVAL_MINUTES)
  if (minuteOffset <= 0) {
    return {
      startFrameIndex,
      endFrameIndex,
      t: 0,
    }
  }

  return {
    startFrameIndex,
    endFrameIndex,
    t: minuteOffset / SOURCE_FRAME_INTERVAL_MINUTES,
  }
}

function blendFrameValues(startValues: number[], endValues: number[], t: number): Float32Array {
  const valueCount = startValues.length
  const output = new Float32Array(valueCount)

  for (let i = 0; i < valueCount; i += 1) {
    const startValue = startValues[i]
    output[i] = startValue + (t * (endValues[i] - startValue))
  }

  return output
}

export function getOrCreateMinuteFrameValues(
  timeline: InterpolationTimeline,
  minuteIndex: number,
  minuteCache: Map<number, ArrayLike<number>>,
): ArrayLike<number> {
  const safeMinute = clampMinuteIndex(minuteIndex)
  const cachedValues = minuteCache.get(safeMinute)
  if (cachedValues) {
    return cachedValues
  }

  if (timeline.frames.length === 0) {
    return []
  }

  const { startFrameIndex, endFrameIndex, t } = resolveMinuteFrameBlendWindow(
    safeMinute,
    timeline.frames.length,
  )

  const startValues = timeline.frames[startFrameIndex]?.values ?? []

  if (t === 0 || startFrameIndex === endFrameIndex) {
    minuteCache.set(safeMinute, startValues)
    return startValues
  }

  const endValues = timeline.frames[endFrameIndex]?.values ?? startValues
  const blendedValues = blendFrameValues(startValues, endValues, t)
  minuteCache.set(safeMinute, blendedValues)
  return blendedValues
}
