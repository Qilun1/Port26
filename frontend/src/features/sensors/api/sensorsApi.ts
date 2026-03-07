import type { Sensor } from '../model/sensor'
import type {
  InterpolatedGrid,
  InterpolationMetric,
} from '../model/interpolation'
import type { InterpolationTimeline } from '../model/interpolationTimeline'
import type { SensorHistorySeries, WeatherReading } from '../model/weatherReading'
import {
  adaptBackendSensor,
  adaptBackendSensorHistory,
  toWeatherReading,
  type BackendSensorHistoryResponse,
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

interface BackendInterpolationTimelineFrame {
  timestamp: string
  values: number[]
}

interface BackendInterpolationTimelineResponse {
  metric: InterpolationMetric
  date: string
  grid_size_meters: number
  rows: number
  cols: number
  bounding_box: {
    min_latitude: number
    min_longitude: number
    max_latitude: number
    max_longitude: number
  }
  active_indices: number[]
  timestamps: string[]
  frames: BackendInterpolationTimelineFrame[]
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
    const rows = Math.max(...payload.points.map((point) => point.row)) + 1
    const cols = Math.max(...payload.points.map((point) => point.col)) + 1
    const expectedLength = rows * cols
    const values: Array<number | null> = Array.from({ length: expectedLength }, () => null)

    for (const point of payload.points) {
      const index = (point.row * cols) + point.col
      values[index] = point.interpolated_value
    }

    return {
      metric: payload.metric,
      gridSizeMeters,
      rows,
      cols,
      boundingBox: {
        minLatitude: box.min_latitude,
        minLongitude: box.min_longitude,
        maxLatitude: box.max_latitude,
        maxLongitude: box.max_longitude,
      },
      values,
      mask: values.map((value) => (value === null ? 0 : 1)),
    }
  }

  if (
    typeof payload.rows !== 'number'
    || typeof payload.cols !== 'number'
    || !Array.isArray(payload.values)
  ) {
    throw new Error('Interpolation response has unsupported shape.')
  }

  const expectedLength = payload.rows * payload.cols
  const values = payload.values.slice(0, expectedLength)
  while (values.length < expectedLength) {
    values.push(null)
  }

  const mask = Array.isArray(payload.mask)
    ? payload.mask.slice(0, expectedLength)
    : values.map((value) => (value === null ? 0 : 1))

  return {
    metric: payload.metric,
    gridSizeMeters,
    rows: payload.rows,
    cols: payload.cols,
    boundingBox: {
      minLatitude: box.min_latitude,
      minLongitude: box.min_longitude,
      maxLatitude: box.max_latitude,
      maxLongitude: box.max_longitude,
    },
    values,
    mask,
  }
}

function adaptInterpolationTimelinePayload(
  payload: BackendInterpolationTimelineResponse,
): InterpolationTimeline {
  if (!Array.isArray(payload.active_indices) || payload.active_indices.length === 0) {
    throw new Error('Interpolation timeline is missing active_indices.')
  }

  if (!Array.isArray(payload.frames) || payload.frames.length !== payload.timestamps.length) {
    throw new Error('Interpolation timeline has mismatched frame/timestamp arrays.')
  }

  const activeLength = payload.active_indices.length

  let previousIndex = -1
  for (const index of payload.active_indices) {
    if (!Number.isInteger(index) || index <= previousIndex || index < 0 || index >= (payload.rows * payload.cols)) {
      throw new Error('Interpolation timeline active_indices are invalid.')
    }
    previousIndex = index
  }

  return {
    metric: payload.metric,
    date: payload.date,
    gridSizeMeters: payload.grid_size_meters,
    rows: payload.rows,
    cols: payload.cols,
    boundingBox: {
      minLatitude: payload.bounding_box.min_latitude,
      minLongitude: payload.bounding_box.min_longitude,
      maxLatitude: payload.bounding_box.max_latitude,
      maxLongitude: payload.bounding_box.max_longitude,
    },
    activeIndices: payload.active_indices,
    timestamps: payload.timestamps,
    frames: payload.frames.map((frame, index) => {
      if (!Array.isArray(frame.values) || frame.values.length !== activeLength) {
        throw new Error('Interpolation timeline frame values do not match active_indices length.')
      }

      if (frame.timestamp !== payload.timestamps[index]) {
        throw new Error('Interpolation timeline timestamps are out of sync.')
      }

      return {
        timestamp: frame.timestamp,
        values: frame.values,
      }
    }),
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

export async function getInterpolationTimeline(
  metric: InterpolationMetric,
  date: string,
  gridSizeMeters = DEFAULT_INTERPOLATION_GRID_SIZE_METERS,
  signal?: AbortSignal,
): Promise<InterpolationTimeline> {
  const query = new URLSearchParams({
    metric,
    date,
    grid_size_meters: String(gridSizeMeters),
  })

  const response = await fetch(`${API_BASE_URL}/interpolation/timeline?${query.toString()}`, {
    signal,
  })

  if (!response.ok) {
    let detail = `Failed to fetch interpolation timeline (${metric}): ${response.status}`

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

  const payload = (await response.json()) as BackendInterpolationTimelineResponse
  return adaptInterpolationTimelinePayload(payload)
}

export async function getSensorHistoryById(
  sensorId: number,
  signal?: AbortSignal,
): Promise<SensorHistorySeries> {
  const response = await fetch(`${API_BASE_URL}/sensors/${sensorId}/readings`, {
    signal,
  })

  if (!response.ok) {
    let detail = `Failed to fetch history for sensor ${sensorId}: ${response.status}`

    try {
      const errorPayload = (await response.json()) as { detail?: string }
      if (typeof errorPayload.detail === 'string' && errorPayload.detail.length > 0) {
        detail = errorPayload.detail
      }
    } catch {
      // Keep fallback message when backend did not return JSON.
    }

    throw new Error(detail)
  }

  const payload = (await response.json()) as BackendSensorHistoryResponse
  return adaptBackendSensorHistory(payload)
}
