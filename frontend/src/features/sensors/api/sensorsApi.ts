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
  grid_size_meters?: number
  cell_size_m?: number
  count?: number
  bounding_box?: {
    min_latitude: number
    min_longitude: number
    max_latitude: number
    max_longitude: number
  }
  bbox?: {
    min_latitude: number
    min_longitude: number
    max_latitude: number
    max_longitude: number
  }
  points?: BackendInterpolationGridPoint[]
  rows?: number
  cols?: number
  values?: Array<number | null>
  mask?: number[]
}

function toPointFromMaskedMatrix(
  row: number,
  col: number,
  rows: number,
  cols: number,
  value: number | null,
  box: {
    min_latitude: number
    min_longitude: number
    max_latitude: number
    max_longitude: number
  },
): BackendInterpolationGridPoint {
  const rowSpan = Math.max(1, rows)
  const colSpan = Math.max(1, cols)
  const cellLat = (box.max_latitude - box.min_latitude) / rowSpan
  const cellLon = (box.max_longitude - box.min_longitude) / colSpan

  return {
    row,
    col,
    latitude: box.min_latitude + (row * cellLat) + (cellLat / 2),
    longitude: box.min_longitude + (col * cellLon) + (cellLon / 2),
    interpolated_value: value,
  }
}

function adaptInterpolationPayload(
  payload: BackendInterpolationGridResponse,
): InterpolatedGrid {
  const box = payload.bbox ?? payload.bounding_box
  if (!box) {
    throw new Error('Interpolation response is missing bbox/bounding_box.')
  }

  const gridSizeMeters = payload.cell_size_m ?? payload.grid_size_meters
  if (typeof gridSizeMeters !== 'number' || Number.isNaN(gridSizeMeters)) {
    throw new Error('Interpolation response is missing cell size information.')
  }

  if (Array.isArray(payload.points)) {
    return {
      metric: payload.metric,
      gridSizeMeters,
      count: payload.count ?? payload.points.length,
      boundingBox: {
        minLatitude: box.min_latitude,
        minLongitude: box.min_longitude,
        maxLatitude: box.max_latitude,
        maxLongitude: box.max_longitude,
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

  if (
    typeof payload.rows !== 'number'
    || typeof payload.cols !== 'number'
    || !Array.isArray(payload.values)
  ) {
    throw new Error('Interpolation response has unsupported shape.')
  }

  const points: BackendInterpolationGridPoint[] = []
  const expectedLength = payload.rows * payload.cols
  const usableLength = Math.min(expectedLength, payload.values.length)

  for (let index = 0; index < usableLength; index += 1) {
    const row = Math.floor(index / payload.cols)
    const col = index % payload.cols
    points.push(
      toPointFromMaskedMatrix(
        row,
        col,
        payload.rows,
        payload.cols,
        payload.values[index],
        box,
      ),
    )
  }

  return {
    metric: payload.metric,
    gridSizeMeters,
    count: payload.mask?.reduce((sum, item) => sum + (item === 1 ? 1 : 0), 0) ?? points.length,
    boundingBox: {
      minLatitude: box.min_latitude,
      minLongitude: box.min_longitude,
      maxLatitude: box.max_latitude,
      maxLongitude: box.max_longitude,
    },
    points: points.map((point) => ({
      row: point.row,
      col: point.col,
      latitude: point.latitude,
      longitude: point.longitude,
      interpolatedValue: point.interpolated_value,
    })),
  }
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

  return adaptInterpolationPayload(payload)
}
