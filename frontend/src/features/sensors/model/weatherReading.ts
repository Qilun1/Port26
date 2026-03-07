export interface WeatherReading {
  sensorId: string
  temperatureC: number | null
  humidityPct: number | null
  windSpeedMs: number | null
  airPressureHpa?: number | null
  aqi?: number | null
  timestamp: string | null
}
