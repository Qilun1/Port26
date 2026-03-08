export type InterpolationMetric = 'temperature' | 'aqi'

export interface InterpolationBoundingBox {
  minLatitude: number
  minLongitude: number
  maxLatitude: number
  maxLongitude: number
}

export interface InterpolatedGridPoint {
  row: number
  col: number
  latitude: number
  longitude: number
  interpolatedValue: number | null
}

export interface InterpolatedGrid {
  metric: InterpolationMetric
  gridSizeMeters: number
  count: number
  boundingBox: InterpolationBoundingBox
  points: InterpolatedGridPoint[]
}
