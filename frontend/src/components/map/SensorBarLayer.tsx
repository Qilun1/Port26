import { memo, useMemo } from 'react'
import type { CSSProperties } from 'react'
import { Marker } from 'react-map-gl/maplibre'
import type { ColorMode } from '../../features/sensors/model/colorMode'
import type { InterpolationMetric } from '../../features/sensors/model/interpolation'
import type { InterpolationTimeline } from '../../features/sensors/model/interpolationTimeline'
import type { Sensor } from '../../features/sensors/model/sensor'
import {
  computeFrameMean,
  computeRelativeRange,
  resolveColorValueRgba,
} from '../../lib/map/colorScales'
import { buildNearestFrameIndexBySensorId } from '../../lib/map/sensorGridMapping'

type SensorBarLayerProps = {
  sensors: Sensor[]
  metric: InterpolationMetric | null
  timeline: InterpolationTimeline | null
  currentValues: ArrayLike<number>
  colorMode: ColorMode
  relativeColorRange: number | null
  minValue: number | null
  maxValue: number | null
  isVisible: boolean
}

type SensorBarDatum = {
  sensor: Sensor
  heightPx: number
  colorCss: string
}

type SensorBarMeta = {
  sensor: Sensor
  frameIndex: number | null
  fallbackValue: number | null
}

const BAR_MIN_HEIGHT_PX = 6
const BAR_MAX_HEIGHT_PX_TEMPERATURE = 120
const BAR_MAX_HEIGHT_PX_AQI = 140

function clamp(value: number, minValue: number, maxValue: number): number {
  return Math.max(minValue, Math.min(maxValue, value))
}

function toLatestMetricValue(sensor: Sensor, metric: InterpolationMetric): number | null {
  if (metric === 'temperature') {
    return typeof sensor.latestTemperatureC === 'number' ? sensor.latestTemperatureC : null
  }

  return typeof sensor.latestAqi === 'number' ? sensor.latestAqi : null
}

function toColorCss(rgba: [number, number, number, number]): string {
  return `rgba(${rgba[0]}, ${rgba[1]}, ${rgba[2]}, ${(rgba[3] / 255).toFixed(3)})`
}

export function SensorBarLayer({
  sensors,
  metric,
  timeline,
  currentValues,
  colorMode,
  relativeColorRange,
  minValue,
  maxValue,
  isVisible,
}: SensorBarLayerProps) {
  const sensorFrameIndexById = useMemo(() => {
    return buildNearestFrameIndexBySensorId(sensors, timeline)
  }, [sensors, timeline])

  const sensorMeta = useMemo<SensorBarMeta[]>(() => {
    if (!metric) {
      return []
    }

    return sensors.map((sensor) => ({
      sensor,
      frameIndex: sensorFrameIndexById.get(sensor.id) ?? null,
      fallbackValue: toLatestMetricValue(sensor, metric),
    }))
  }, [metric, sensors, sensorFrameIndexById])

  const resolvedValueById = useMemo(() => {
    const values = new Map<string, number | null>()
    const numericValues: number[] = []

    for (const item of sensorMeta) {
      let value: number | null = null

      if (
        timeline
        && typeof item.frameIndex === 'number'
        && item.frameIndex >= 0
        && item.frameIndex < currentValues.length
      ) {
        const frameValue = currentValues[item.frameIndex]
        value = Number.isFinite(frameValue) ? frameValue : null
      }

      if (value === null) {
        value = item.fallbackValue
      }

      values.set(item.sensor.id, value)

      if (typeof value === 'number' && Number.isFinite(value)) {
        numericValues.push(value)
      }
    }

    return {
      values,
      numericValues,
    }
  }, [sensorMeta, timeline, currentValues])

  const fallbackRange = useMemo(() => {
    if (!metric) {
      return null
    }

    let localMin = Number.POSITIVE_INFINITY
    let localMax = Number.NEGATIVE_INFINITY

    for (const sensor of sensors) {
      const value = toLatestMetricValue(sensor, metric)
      if (typeof value !== 'number' || !Number.isFinite(value)) {
        continue
      }
      localMin = Math.min(localMin, value)
      localMax = Math.max(localMax, value)
    }

    if (!Number.isFinite(localMin) || !Number.isFinite(localMax)) {
      return null
    }

    return { minValue: localMin, maxValue: localMax }
  }, [metric, sensors])

  const barData = useMemo<SensorBarDatum[]>(() => {
    if (!metric) {
      return []
    }

    const absoluteMinValue = Number.isFinite(minValue)
      ? Number(minValue)
      : (fallbackRange?.minValue ?? 0)

    const absoluteMaxValue = Number.isFinite(maxValue)
      ? Number(maxValue)
      : (fallbackRange?.maxValue ?? 1)

    const frameMean = resolvedValueById.numericValues.length > 0
      ? computeFrameMean(resolvedValueById.numericValues)
      : 0
    const effectiveRelativeRange = Number.isFinite(relativeColorRange)
      ? Number(relativeColorRange)
      : computeRelativeRange(resolvedValueById.numericValues, frameMean, metric)

    const safeAbsoluteSpan = Math.max(absoluteMaxValue - absoluteMinValue, 1e-6)
    const safeRelativeRange = Math.max(effectiveRelativeRange, 1e-6)

    const maxBarHeight = metric === 'temperature' ? BAR_MAX_HEIGHT_PX_TEMPERATURE : BAR_MAX_HEIGHT_PX_AQI

    return sensorMeta.map((item) => {
      const value = resolvedValueById.values.get(item.sensor.id) ?? null

      if (typeof value !== 'number' || !Number.isFinite(value)) {
        return {
          sensor: item.sensor,
          heightPx: BAR_MIN_HEIGHT_PX,
          colorCss: 'rgba(169, 183, 200, 0.25)',
        }
      }

      const normalized = colorMode === 'relative'
        ? clamp(Math.abs(value - frameMean) / safeRelativeRange, 0, 1)
        : clamp((value - absoluteMinValue) / safeAbsoluteSpan, 0, 1)

      const heightPx = BAR_MIN_HEIGHT_PX + (normalized * (maxBarHeight - BAR_MIN_HEIGHT_PX))
      const rgba = resolveColorValueRgba(
        value,
        metric,
        colorMode,
        absoluteMinValue,
        absoluteMaxValue,
        frameMean,
        safeRelativeRange,
        214,
      )

      return {
        sensor: item.sensor,
        heightPx,
        colorCss: toColorCss(rgba),
      }
    })
  }, [
    metric,
    sensorMeta,
    resolvedValueById,
    colorMode,
    relativeColorRange,
    minValue,
    maxValue,
    fallbackRange,
  ])

  if (!metric || barData.length === 0) {
    return null
  }

  return (
    <>
      {barData.map((item) => (
        <Marker
          key={`sensor-bar-${item.sensor.id}`}
          latitude={item.sensor.latitude}
          longitude={item.sensor.longitude}
          anchor="bottom"
        >
          <div
            className={`sensor-bar${!isVisible ? ' sensor-bar--hidden' : ''}`}
            style={{
              '--sensor-bar-color': item.colorCss,
              '--sensor-bar-height': `${item.heightPx}px`,
            } as CSSProperties}
            aria-hidden="true"
          >
            <div
              className="sensor-bar__column"
              style={{ height: 'var(--sensor-bar-height)' }}
            />
            <div className="sensor-bar__base" />
          </div>
        </Marker>
      ))}
    </>
  )
}

export const MemoizedSensorBarLayer = memo(SensorBarLayer)
