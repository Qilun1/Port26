import type { InterpolationBoundingBox, InterpolationMetric } from './interpolation'

export interface InterpolationTimelineFrame {
  timestamp: string
  values: number[]
}

export interface InterpolationTimeline {
  metric: InterpolationMetric
  date: string
  gridSizeMeters: number
  rows: number
  cols: number
  boundingBox: InterpolationBoundingBox
  activeIndices: number[]
  timestamps: string[]
  frames: InterpolationTimelineFrame[]
}
