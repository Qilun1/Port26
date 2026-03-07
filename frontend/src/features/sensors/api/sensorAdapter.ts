import type { Sensor } from '../model/sensor'
import type { WeatherReading } from '../model/weatherReading'

export interface BackendSensorListItem {
  id: number
  sensor_code: string
  name: string | null
  latitude: number
  longitude: number
  latest_temperature_c: number | null
  latest_air_pressure_hpa: number | null
  latest_aqi: number | null
}

export interface BackendSensorListResponse {
  sensors: BackendSensorListItem[]
  count: number
}

export function adaptBackendSensor(item: BackendSensorListItem): Sensor {
  return {
    id: String(item.id),
    name: item.name ?? item.sensor_code,
    latitude: item.latitude,
    longitude: item.longitude,
    latestTemperatureC: item.latest_temperature_c,
    latestAirPressureHpa: item.latest_air_pressure_hpa,
    latestAqi: item.latest_aqi,
  }
}

export function toWeatherReading(sensor: Sensor): WeatherReading {
  return {
    sensorId: sensor.id,
    temperatureC: sensor.latestTemperatureC ?? null,
    humidityPct: null,
    windSpeedMs: null,
    airPressureHpa: sensor.latestAirPressureHpa ?? null,
    aqi: sensor.latestAqi ?? null,
    timestamp: null,
  }
}