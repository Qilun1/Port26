export interface WeatherReading {
  sensorId: string
  temperatureC: number | null
  humidityPct: number | null
  windSpeedMs: number | null
  airPressureHpa?: number | null
  aqi?: number | null
  timestamp: string | null
}

export interface SensorHistoryPoint {
  timestamp: string
  aqi: number | null
  temperature: number | null
}

export interface SensorHistorySeries {
  sensorId: string
  points: SensorHistoryPoint[]
}
