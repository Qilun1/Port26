export interface InterpolationTimestepMetricPoint {
  timestampUtc: string
  avgAqi: number | null
  avgTemperatureC: number | null
  sensorCountAqi: number
  sensorCountTemperature: number
}

export interface InterpolationTimestepMetricsSeries {
  date: string
  count: number
  items: InterpolationTimestepMetricPoint[]
}
