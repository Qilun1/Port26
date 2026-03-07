import { useCallback, useEffect, useRef, useState } from 'react'
import { Popup } from 'react-map-gl/maplibre'
import {
  getInterpolatedGrid,
  listSensors,
} from '../../features/sensors/api/sensorsApi'
import { toWeatherReading } from '../../features/sensors/api/sensorAdapter'
import type {
  InterpolatedGrid,
  InterpolationMetric,
} from '../../features/sensors/model/interpolation'
import type { Sensor } from '../../features/sensors/model/sensor'
import { InterpolationHeatmapLayer } from './InterpolationHeatmapLayer'
import { SensorMarker } from './SensorMarker'
import { SensorTooltip } from './SensorTooltip'

const METRICS: InterpolationMetric[] = ['temperature', 'aqi']
const METRIC_LABELS: Record<InterpolationMetric, string> = {
  temperature: 'Temperature',
  aqi: 'Air quality index',
}

export function SensorLayer() {
  const [sensors, setSensors] = useState<Sensor[]>([])
  const [hoveredSensor, setHoveredSensor] = useState<Sensor | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [activeMetric, setActiveMetric] = useState<InterpolationMetric | null>(null)
  const [displayMetric, setDisplayMetric] = useState<InterpolationMetric | null>(null)
  const [gridByMetric, setGridByMetric] = useState<Partial<Record<InterpolationMetric, InterpolatedGrid>>>(
    {},
  )
  const [inFlightByMetric, setInFlightByMetric] = useState<
    Partial<Record<InterpolationMetric, boolean>>
  >({})
  const [errorsByMetric, setErrorsByMetric] = useState<
    Partial<Record<InterpolationMetric, string | null>>
  >({})

  const activeMetricRef = useRef<InterpolationMetric | null>(null)
  const cacheRef = useRef<Partial<Record<InterpolationMetric, InterpolatedGrid>>>({})
  const controllersRef = useRef<Partial<Record<InterpolationMetric, AbortController>>>({})

  useEffect(() => {
    activeMetricRef.current = activeMetric
  }, [activeMetric])

  useEffect(() => {
    cacheRef.current = gridByMetric
  }, [gridByMetric])

  useEffect(() => {
    setIsLoading(true)
    void listSensors()
      .then((items) => {
        setSensors(items)
      })
      .finally(() => {
        setIsLoading(false)
      })
  }, [])

  useEffect(() => {
    return () => {
      for (const controller of Object.values(controllersRef.current)) {
        controller?.abort()
      }
    }
  }, [])

  const startMetricLoad = useCallback((metric: InterpolationMetric) => {
    if (controllersRef.current[metric]) {
      return
    }

    const controller = new AbortController()
    controllersRef.current[metric] = controller

    setInFlightByMetric((current) => ({
      ...current,
      [metric]: true,
    }))

    void getInterpolatedGrid(metric, undefined, controller.signal)
      .then((grid) => {
        setGridByMetric((current) => ({
          ...current,
          [metric]: grid,
        }))

        setErrorsByMetric((current) => ({
          ...current,
          [metric]: null,
        }))

        if (activeMetricRef.current === metric) {
          setDisplayMetric(metric)
        }
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return
        }

        const message = error instanceof Error ? error.message : 'Failed to load heatmap data.'
        setErrorsByMetric((current) => ({
          ...current,
          [metric]: message,
        }))
      })
      .finally(() => {
        delete controllersRef.current[metric]
        setInFlightByMetric((current) => ({
          ...current,
          [metric]: false,
        }))
      })
  }, [])

  const handleMetricSelect = useCallback(
    (metric: InterpolationMetric) => {
      setActiveMetric(metric)
      setErrorsByMetric((current) => ({
        ...current,
        [metric]: null,
      }))

      if (cacheRef.current[metric]) {
        setDisplayMetric(metric)
        return
      }

      startMetricLoad(metric)
    },
    [startMetricLoad],
  )

  const handleHoverStart = useCallback((sensor: Sensor) => {
    setHoveredSensor(sensor)
  }, [])

  const handleHoverEnd = useCallback(() => {
    setHoveredSensor(null)
  }, [])

  const reading = hoveredSensor ? toWeatherReading(hoveredSensor) : null
  const isGridLoading = activeMetric ? Boolean(inFlightByMetric[activeMetric]) : false
  const gridError = activeMetric ? (errorsByMetric[activeMetric] ?? null) : null
  const renderedMetric = displayMetric && gridByMetric[displayMetric] ? displayMetric : null
  const activeGrid = renderedMetric ? (gridByMetric[renderedMetric] ?? null) : null

  return (
    <>
      {renderedMetric && activeGrid && (
        <InterpolationHeatmapLayer grid={activeGrid} metric={renderedMetric} />
      )}

      <div className="metric-controls" role="group" aria-label="Interpolation metric selector">
        {METRICS.map((metric) => (
          <button
            key={metric}
            type="button"
            className={`metric-controls__button${metric === activeMetric ? ' metric-controls__button--active' : ''}`}
            onClick={() => handleMetricSelect(metric)}
          >
            {METRIC_LABELS[metric]}
          </button>
        ))}

        <div className="metric-controls__status" aria-live="polite">
          {isGridLoading && 'Loading interpolation grid...'}
          {!isGridLoading && gridError}
          {!isGridLoading && !gridError && !activeMetric && 'Choose a metric to load heatmap data.'}
          {!isGridLoading && !gridError && activeMetric && renderedMetric && activeGrid
            ? `${activeGrid.count} points (${METRIC_LABELS[renderedMetric]})`
            : null}
          {isGridLoading && renderedMetric && renderedMetric !== activeMetric
            ? `Showing cached ${METRIC_LABELS[renderedMetric]} while loading ${METRIC_LABELS[activeMetric ?? renderedMetric]}...`
            : null}
        </div>
      </div>

      {sensors.map((sensor) => (
        <SensorMarker
          key={sensor.id}
          sensor={sensor}
          onHoverStart={handleHoverStart}
          onHoverEnd={handleHoverEnd}
        />
      ))}

      {hoveredSensor && (
        <Popup
          latitude={hoveredSensor.latitude}
          longitude={hoveredSensor.longitude}
          anchor="top"
          closeButton={false}
          closeOnClick={false}
          offset={20}
          className="sensor-popup"
        >
          <SensorTooltip
            sensor={hoveredSensor}
            reading={reading}
            isLoading={isLoading}
          />
        </Popup>
      )}
    </>
  )
}
