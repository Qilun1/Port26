import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Popup } from 'react-map-gl/maplibre'
import {
  getInterpolationTimeline,
  getSensorHistoryById,
  listSensors,
} from '../../features/sensors/api/sensorsApi'
import { toWeatherReading } from '../../features/sensors/api/sensorAdapter'
import type { InterpolationMetric } from '../../features/sensors/model/interpolation'
import type { InterpolationTimeline } from '../../features/sensors/model/interpolationTimeline'
import type { Sensor } from '../../features/sensors/model/sensor'
import {
  clampMinuteIndex,
  getOrCreateMinuteFrameValues,
  MINUTES_PER_DAY,
  PLAYBACK_SIMULATED_MINUTES_PER_SECOND,
} from '../../features/sensors/utils/timelinePlayback'
import type { SensorHistoryPoint } from '../../features/sensors/model/weatherReading'
import { InterpolationHeatmapLayer } from './InterpolationHeatmapLayer'
import { SensorHistoryPanel } from './SensorHistoryPanel'
import { SensorMarker } from './SensorMarker'
import { SensorTooltip } from './SensorTooltip'
import { TimelineControls } from './TimelineControls'

const METRICS: InterpolationMetric[] = ['temperature', 'aqi']
const METRIC_LABELS: Record<InterpolationMetric, string> = {
  temperature: 'Temperature',
  aqi: 'Air quality index',
}
const TIMELINE_DATE = import.meta.env.VITE_TIMELINE_DATE ?? '2026-03-07'

export function SensorLayer() {
  const [sensors, setSensors] = useState<Sensor[]>([])
  const [hoveredSensor, setHoveredSensor] = useState<Sensor | null>(null)
  const [selectedSensor, setSelectedSensor] = useState<Sensor | null>(null)
  const [historyPointsBySensor, setHistoryPointsBySensor] = useState<
    Record<string, SensorHistoryPoint[]>
  >({})
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyError, setHistoryError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [activeMetric, setActiveMetric] = useState<InterpolationMetric | null>(null)
  const [displayMetric, setDisplayMetric] = useState<InterpolationMetric | null>(null)
  const [timelineByMetric, setTimelineByMetric] = useState<
    Partial<Record<InterpolationMetric, InterpolationTimeline>>
  >({})
  const [timelineInFlightByMetric, setTimelineInFlightByMetric] = useState<
    Partial<Record<InterpolationMetric, boolean>>
  >({})
  const [timelineErrorsByMetric, setTimelineErrorsByMetric] = useState<
    Partial<Record<InterpolationMetric, string | null>>
  >({})
  const [currentMinuteIndex, setCurrentMinuteIndex] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)

  const activeMetricRef = useRef<InterpolationMetric | null>(null)
  const timelineCacheRef = useRef<Partial<Record<InterpolationMetric, InterpolationTimeline>>>({})
  const timelineControllersRef = useRef<Partial<Record<InterpolationMetric, AbortController>>>({})
  const historyControllerRef = useRef<AbortController | null>(null)
  const playbackMinuteCursorRef = useRef(0)
  const minuteFrameCacheByMetricRef = useRef<
    Partial<Record<InterpolationMetric, Map<number, ArrayLike<number>>>>
  >({})

  useEffect(() => {
    activeMetricRef.current = activeMetric
  }, [activeMetric])

  useEffect(() => {
    timelineCacheRef.current = timelineByMetric
  }, [timelineByMetric])

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
      for (const controller of Object.values(timelineControllersRef.current)) {
        controller?.abort()
      }
      historyControllerRef.current?.abort()
    }
  }, [])

  const startTimelineLoad = useCallback((metric: InterpolationMetric) => {
    if (timelineControllersRef.current[metric]) {
      return
    }

    const controller = new AbortController()
    timelineControllersRef.current[metric] = controller

    setTimelineInFlightByMetric((current) => ({
      ...current,
      [metric]: true,
    }))

    void getInterpolationTimeline(metric, TIMELINE_DATE, undefined, controller.signal)
      .then((timeline) => {
        setTimelineByMetric((current) => ({
          ...current,
          [metric]: timeline,
        }))

        setTimelineErrorsByMetric((current) => ({
          ...current,
          [metric]: null,
        }))

        if (activeMetricRef.current === metric) {
          setDisplayMetric(metric)
          setCurrentMinuteIndex(0)
          playbackMinuteCursorRef.current = 0
        }

        minuteFrameCacheByMetricRef.current[metric] = new Map<number, ArrayLike<number>>()
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return
        }

        const message = error instanceof Error ? error.message : 'Failed to load timeline data.'
        setTimelineErrorsByMetric((current) => ({
          ...current,
          [metric]: message,
        }))
      })
      .finally(() => {
        delete timelineControllersRef.current[metric]
        setTimelineInFlightByMetric((current) => ({
          ...current,
          [metric]: false,
        }))
      })
  }, [])

  const handleMetricSelect = useCallback(
    (metric: InterpolationMetric) => {
      setActiveMetric(metric)
      setTimelineErrorsByMetric((current) => ({
        ...current,
        [metric]: null,
      }))

      const cachedTimeline = timelineCacheRef.current[metric]
      if (cachedTimeline) {
        setDisplayMetric(metric)
        setCurrentMinuteIndex(0)
        playbackMinuteCursorRef.current = 0
        return
      }

      startTimelineLoad(metric)
    },
    [startTimelineLoad],
  )

  const handleHoverStart = useCallback((sensor: Sensor) => {
    setHoveredSensor(sensor)
  }, [])

  const handleHoverEnd = useCallback(() => {
    setHoveredSensor(null)
  }, [])

  const handleSensorClick = useCallback((sensor: Sensor) => {
    setSelectedSensor(sensor)
    setHistoryError(null)

    historyControllerRef.current?.abort()

    const cached = historyPointsBySensor[sensor.id]
    if (cached) {
      setHistoryLoading(false)
      return
    }

    const controller = new AbortController()
    historyControllerRef.current = controller

    setHistoryLoading(true)

    void getSensorHistoryById(Number(sensor.id), controller.signal)
      .then((series) => {
        setHistoryPointsBySensor((current) => ({
          ...current,
          [sensor.id]: series.points,
        }))
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return
        }

        setHistoryError(
          error instanceof Error ? error.message : 'Failed to load historical readings.',
        )
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setHistoryLoading(false)
        }
      })
  }, [historyPointsBySensor])

  const handlePanelClose = useCallback(() => {
    historyControllerRef.current?.abort()
    setSelectedSensor(null)
    setHistoryLoading(false)
    setHistoryError(null)
  }, [])

  const renderedMetric = displayMetric && timelineByMetric[displayMetric] ? displayMetric : null
  const activeTimeline = renderedMetric ? (timelineByMetric[renderedMetric] ?? null) : null
  const sourceFrameCount = activeTimeline?.frames.length ?? 0
  const minuteCount = sourceFrameCount > 0 ? MINUTES_PER_DAY : 0

  const currentFrameValues = useMemo<ArrayLike<number>>(() => {
    if (!activeTimeline || !renderedMetric) {
      return []
    }

    let minuteCache = minuteFrameCacheByMetricRef.current[renderedMetric]
    if (!minuteCache) {
      minuteCache = new Map<number, ArrayLike<number>>()
      minuteFrameCacheByMetricRef.current[renderedMetric] = minuteCache
    }

    return getOrCreateMinuteFrameValues(activeTimeline, currentMinuteIndex, minuteCache)
  }, [activeTimeline, renderedMetric, currentMinuteIndex])

  useEffect(() => {
    if (!isPlaying || minuteCount === 0) {
      return
    }

    let animationFrameId = 0
    let previousTick: number | null = null

    const tick = (timestampMs: number) => {
      if (previousTick === null) {
        previousTick = timestampMs
        animationFrameId = window.requestAnimationFrame(tick)
        return
      }

      const elapsedSeconds = (timestampMs - previousTick) / 1000
      previousTick = timestampMs

      playbackMinuteCursorRef.current =
        (playbackMinuteCursorRef.current
          + (elapsedSeconds * PLAYBACK_SIMULATED_MINUTES_PER_SECOND))
        % MINUTES_PER_DAY

      const nextMinuteIndex = Math.floor(playbackMinuteCursorRef.current)
      setCurrentMinuteIndex((current) => (current === nextMinuteIndex ? current : nextMinuteIndex))

      animationFrameId = window.requestAnimationFrame(tick)
    }

    animationFrameId = window.requestAnimationFrame(tick)

    return () => {
      window.cancelAnimationFrame(animationFrameId)
    }
  }, [isPlaying, minuteCount])

  useEffect(() => {
    if (minuteCount === 0) {
      setCurrentMinuteIndex(0)
      playbackMinuteCursorRef.current = 0
      setIsPlaying(false)
      return
    }

    setCurrentMinuteIndex((current) => {
      const clamped = clampMinuteIndex(current)
      playbackMinuteCursorRef.current = clamped
      return clamped
    })
  }, [minuteCount])

  useEffect(() => {
    playbackMinuteCursorRef.current = currentMinuteIndex
  }, [currentMinuteIndex])

  const handleSeek = useCallback((nextMinuteIndex: number) => {
    const clamped = clampMinuteIndex(nextMinuteIndex)
    playbackMinuteCursorRef.current = clamped
    setCurrentMinuteIndex(clamped)
  }, [])

  const handleTogglePlay = useCallback(() => {
    if (minuteCount === 0) {
      return
    }

    setIsPlaying((current) => !current)
  }, [minuteCount])

  const reading = hoveredSensor ? toWeatherReading(hoveredSensor) : null
  const isTimelineLoading = activeMetric ? Boolean(timelineInFlightByMetric[activeMetric]) : false
  const timelineError = activeMetric ? (timelineErrorsByMetric[activeMetric] ?? null) : null
  const selectedHistory = selectedSensor ? (historyPointsBySensor[selectedSensor.id] ?? []) : []

  return (
    <>
      {renderedMetric && activeTimeline && (
        <InterpolationHeatmapLayer
          timeline={activeTimeline}
          currentValues={currentFrameValues}
          metric={renderedMetric}
        />
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
          {isTimelineLoading && 'Loading timeline...'}
          {!isTimelineLoading && timelineError}
          {!isTimelineLoading && !timelineError && !activeMetric && 'Choose a metric to load timeline.'}
          {!isTimelineLoading && !timelineError && activeTimeline
            ? `${activeTimeline.frames.length} frames (${METRIC_LABELS[activeTimeline.metric]})`
            : null}
          {isTimelineLoading && renderedMetric && renderedMetric !== activeMetric
            ? `Showing cached ${METRIC_LABELS[renderedMetric]} while loading ${METRIC_LABELS[activeMetric ?? renderedMetric]}...`
            : null}
        </div>
      </div>

      {activeTimeline && (
        <TimelineControls
          minuteCount={minuteCount}
          currentMinuteIndex={currentMinuteIndex}
          isPlaying={isPlaying}
          isLoading={isTimelineLoading}
          error={timelineError}
          onSeek={handleSeek}
          onTogglePlay={handleTogglePlay}
        />
      )}

      {sensors.map((sensor) => (
        <SensorMarker
          key={sensor.id}
          sensor={sensor}
          onHoverStart={handleHoverStart}
          onHoverEnd={handleHoverEnd}
          onClick={handleSensorClick}
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

      {selectedSensor && (
        <SensorHistoryPanel
          sensor={selectedSensor}
          points={selectedHistory}
          isLoading={historyLoading}
          error={historyError}
          onClose={handlePanelClose}
        />
      )}
    </>
  )
}
