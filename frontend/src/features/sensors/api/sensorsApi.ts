import type { Sensor } from '../model/sensor'
import type {
  InterpolatedGrid,
  InterpolationMetric,
} from '../model/interpolation'
import type { WeatherReading } from '../model/weatherReading'
import {
  adaptBackendSensor,
  toWeatherReading,
  type BackendSensorListResponse,
} from './sensorAdapter'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

const DEFAULT_INTERPOLATION_GRID_SIZE_METERS = 100

interface BackendInterpolationGridPoint {
  row: number
  col: number
  latitude: number
  longitude: number
  interpolated_value: number | null
}

interface BackendInterpolationGridResponse {
  metric: InterpolationMetric
  grid_size_meters: number
  count: number
  bounding_box: {
    min_latitude: number
    min_longitude: number
    max_latitude: number
    max_longitude: number
  }
  points: BackendInterpolationGridPoint[]
}

async function fetchBackendSensors(): Promise<BackendSensorListResponse> {
  const response = await fetch(`${API_BASE_URL}/sensors`)
  if (!response.ok) {
    throw new Error(`Failed to fetch sensors: ${response.status}`)
  }

  return response.json() as Promise<BackendSensorListResponse>
}

export async function listSensors(): Promise<Sensor[]> {
  const payload = await fetchBackendSensors()
  return payload.sensors.map(adaptBackendSensor)
}

export async function getCurrentWeatherBySensorId(
  sensorId: string,
): Promise<WeatherReading | null> {
  const sensors = await listSensors()
  const sensor = sensors.find((item) => item.id === sensorId)
  return sensor ? toWeatherReading(sensor) : null
}

export async function getInterpolatedGrid(
  metric: InterpolationMetric,
  gridSizeMeters = DEFAULT_INTERPOLATION_GRID_SIZE_METERS,
  signal?: AbortSignal,
): Promise<InterpolatedGrid> {
  const query = new URLSearchParams({
    metric,
    grid_size_meters: String(gridSizeMeters),
  })

  const response = await fetch(`${API_BASE_URL}/interpolation/grid?${query.toString()}`, {
    signal,
  })

  if (!response.ok) {
    let detail = `Failed to fetch interpolation grid (${metric}): ${response.status}`

    try {
      const errorPayload = (await response.json()) as { detail?: string }
      if (typeof errorPayload.detail === 'string' && errorPayload.detail.length > 0) {
        detail = errorPayload.detail
      }
    } catch {
      // Keep default fallback message when backend did not return JSON.
    }

    throw new Error(detail)
  }

  const payload = (await response.json()) as BackendInterpolationGridResponse

  return {
    metric: payload.metric,
    gridSizeMeters: payload.grid_size_meters,
    count: payload.count,
    boundingBox: {
      minLatitude: payload.bounding_box.min_latitude,
      minLongitude: payload.bounding_box.min_longitude,
      maxLatitude: payload.bounding_box.max_latitude,
      maxLongitude: payload.bounding_box.max_longitude,
    },
    points: payload.points.map((point) => ({
      row: point.row,
      col: point.col,
      latitude: point.latitude,
      longitude: point.longitude,
      interpolatedValue: point.interpolated_value,
    })),
  }
}
