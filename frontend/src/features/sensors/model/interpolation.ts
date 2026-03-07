export type InterpolationMetric = 'temperature' | 'aqi'

export interface InterpolationBoundingBox {
  minLatitude: number
  minLongitude: number
  maxLatitude: number
  maxLongitude: number
}

export interface InterpolatedGrid {
  metric: InterpolationMetric
  gridSizeMeters: number
  rows: number
  cols: number
  boundingBox: InterpolationBoundingBox
  values: Array<number | null>
  mask: number[]
}
