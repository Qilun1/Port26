import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  MdAir,
  MdDeviceThermostat,
  MdOutlinePalette,
  MdSensors,
  MdTerrain,
} from 'react-icons/md'
import { Popup, useMap } from 'react-map-gl/maplibre'
import { useSensorData } from '../../app/providers/SensorDataProvider'
import {
  getInterpolationTimeline,
  getInterpolationTimestepMetrics,
  getSensorHistoryById,
  listSensors,
} from '../../features/sensors/api/sensorsApi'
import { toWeatherReading } from '../../features/sensors/api/sensorAdapter'
import type { ColorMode } from '../../features/sensors/model/colorMode'
import type { InterpolationMetric } from '../../features/sensors/model/interpolation'
import type { InterpolationTimeline } from '../../features/sensors/model/interpolationTimeline'
import type { Sensor } from '../../features/sensors/model/sensor'
import {
  clampMinuteIndex,
  getOrCreateMinuteFrameValues,
  MINUTES_PER_DAY,
  PLAYBACK_SIMULATED_MINUTES_PER_SECOND,
  resolveMinuteFrameBlendWindow,
} from '../../features/sensors/utils/timelinePlayback'
import type { SensorHistoryPoint } from '../../features/sensors/model/weatherReading'
import type { InterpolationTimestepMetricsSeries } from '../../features/sensors/model/interpolationMetrics'
import { InterpolationHeatmapLayer } from './InterpolationHeatmapLayer'
import { Surface3DLayer } from './Surface3DLayer'
import { DemoZoneLayer } from './DemoZoneLayer'
import { BottomControlsBar } from './BottomControlsBar'
import { MemoizedSensorBarLayer } from './SensorBarLayer'
import { SensorHistoryPanel } from './SensorHistoryPanel'
import { SensorMarker } from './SensorMarker'
import { SensorTooltip } from './SensorTooltip'
import type { ViewMode } from '../../features/sensors/model/viewMode'
import { computeFrameMean, computeRelativeRange } from '../../lib/map/colorScales'

const METRICS: InterpolationMetric[] = ['temperature', 'aqi']
const METRIC_LABELS: Record<InterpolationMetric, string> = {
  temperature: 'Temperature',
  aqi: 'Air Quality',
}
const TIMELINE_DATE = import.meta.env.VITE_TIMELINE_DATE ?? '2026-03-07'
const SURFACE_PITCH = 58
const SURFACE_BEARING = -18
const PLAYBACK_SPEED_STEP_MINUTES: Record<1 | 2 | 4, number> = {
  1: 1,
  2: 2,
  4: 4,
}

const PLAYBACK_SPEED_MULTIPLIERS: Record<0 | 1 | 2 | 4, number> = {
  0: 0,
  1: 1,
  2: 2,
  4: 4,
}

type SensorVisualizationMode = 'bars' | 'symbols' | 'off'

const SENSOR_VISUAL_MODE_SEQUENCE: SensorVisualizationMode[] = ['symbols', 'bars', 'off']

const SENSOR_VISUAL_MODE_LABELS: Record<SensorVisualizationMode, string> = {
  symbols: 'Symbols',
  bars: 'Bars',
  off: 'Off',
}

export function SensorLayer() {
  const mapCollection = useMap()
  const { loading: _contextLoading } = useSensorData()
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
  const [metricsByDate, setMetricsByDate] = useState<Record<string, InterpolationTimestepMetricsSeries>>({})
  const [metricsInFlightByDate, setMetricsInFlightByDate] = useState<Record<string, boolean>>({})
  const [metricsErrorsByDate, setMetricsErrorsByDate] = useState<Record<string, string | null>>({})
  const [currentMinuteIndex, setCurrentMinuteIndex] = useState(0)
  const [playbackSpeed, setPlaybackSpeed] = useState<0 | 1 | 2 | 4>(0)
  const [viewMode, setViewMode] = useState<ViewMode>('3d')
  const [sensorVisualizationMode, setSensorVisualizationMode] = useState<SensorVisualizationMode>('bars')
  const [colorMode, setColorMode] = useState<ColorMode>('relative')
  const [isDemoZoneVisible, setIsDemoZoneVisible] = useState(false)
  const [throttledSensorBarFrameValues, setThrottledSensorBarFrameValues] = useState<ArrayLike<number>>([])

  const activeMetricRef = useRef<InterpolationMetric | null>(null)
  const timelineCacheRef = useRef<Partial<Record<InterpolationMetric, InterpolationTimeline>>>({})
  const timelineControllersRef = useRef<Partial<Record<InterpolationMetric, AbortController>>>({})
  const metricsCacheRef = useRef<Record<string, InterpolationTimestepMetricsSeries>>({})
  const metricsControllerRef = useRef<AbortController | null>(null)
  const historyControllerRef = useRef<AbortController | null>(null)
  const playbackMinuteCursorRef = useRef(0)
  const lastNonZeroPlaybackSpeedRef = useRef<1 | 2 | 4>(1)
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
    metricsCacheRef.current = metricsByDate
  }, [metricsByDate])

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
      metricsControllerRef.current?.abort()
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

  const startMetricsLoad = useCallback((timelineDate: string) => {
    if (metricsControllerRef.current) {
      return
    }

    if (metricsCacheRef.current[timelineDate]) {
      return
    }

    const controller = new AbortController()
    metricsControllerRef.current = controller

    setMetricsInFlightByDate((current) => ({
      ...current,
      [timelineDate]: true,
    }))

    void getInterpolationTimestepMetrics(timelineDate, controller.signal)
      .then((series) => {
        setMetricsByDate((current) => ({
          ...current,
          [timelineDate]: series,
        }))

        setMetricsErrorsByDate((current) => ({
          ...current,
          [timelineDate]: null,
        }))
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return
        }

        const message = error instanceof Error ? error.message : 'Failed to load aggregate metrics.'
        setMetricsErrorsByDate((current) => ({
          ...current,
          [timelineDate]: message,
        }))
      })
      .finally(() => {
        metricsControllerRef.current = null
        setMetricsInFlightByDate((current) => ({
          ...current,
          [timelineDate]: false,
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

      startMetricsLoad(TIMELINE_DATE)

      const cachedTimeline = timelineCacheRef.current[metric]
      if (cachedTimeline) {
        setDisplayMetric(metric)
        setCurrentMinuteIndex(0)
        playbackMinuteCursorRef.current = 0
        return
      }

      startTimelineLoad(metric)
    },
    [startTimelineLoad, startMetricsLoad],
  )

  // Auto-hide demo zone when metric changes
  useEffect(() => {
    setIsDemoZoneVisible(false)
  }, [activeMetric])

  // Auto-load AQI metric when map mounts with sensors
  useEffect(() => {
    if (!isLoading && sensors.length > 0 && !activeMetric) {
      handleMetricSelect('aqi')
    }
  }, [isLoading, sensors.length, activeMetric, handleMetricSelect])

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

  const handleCycleSensorVisualizationMode = useCallback(() => {
    setSensorVisualizationMode((current) => {
      const currentIndex = SENSOR_VISUAL_MODE_SEQUENCE.indexOf(current)
      const nextIndex = (currentIndex + 1) % SENSOR_VISUAL_MODE_SEQUENCE.length
      return SENSOR_VISUAL_MODE_SEQUENCE[nextIndex]
    })
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

  // Throttle sensor bar visual updates to 10fps for performance during playback
  useEffect(() => {
    if (sensorVisualizationMode !== 'bars') {
      return
    }

    const THROTTLE_INTERVAL_MS = 100 // 10fps

    // Immediate update when not playing or on first render
    if (playbackSpeed === 0 || currentFrameValues.length === 0) {
      setThrottledSensorBarFrameValues(currentFrameValues)
      return
    }

    // During playback, throttle updates
    const intervalId = window.setInterval(() => {
      setThrottledSensorBarFrameValues(currentFrameValues)
    }, THROTTLE_INTERVAL_MS)

    return () => {
      window.clearInterval(intervalId)
    }
  }, [currentFrameValues, playbackSpeed, sensorVisualizationMode])

  useEffect(() => {
    if (playbackSpeed === 0 || minuteCount === 0) {
      return
    }

    let animationFrameId = 0
    let previousTick: number | null = null
    let simulatedMinutesCarry = 0
    const speedMultiplier = PLAYBACK_SPEED_MULTIPLIERS[playbackSpeed]
    const playbackStepMinutes = PLAYBACK_SPEED_STEP_MINUTES[playbackSpeed]

    const tick = (timestampMs: number) => {
      if (previousTick === null) {
        previousTick = timestampMs
        animationFrameId = window.requestAnimationFrame(tick)
        return
      }

      const elapsedSeconds = (timestampMs - previousTick) / 1000
      previousTick = timestampMs

      simulatedMinutesCarry += elapsedSeconds * PLAYBACK_SIMULATED_MINUTES_PER_SECOND * speedMultiplier
      const elapsedWholeMinutes = Math.floor(simulatedMinutesCarry)

      if (elapsedWholeMinutes > 0) {
        simulatedMinutesCarry -= elapsedWholeMinutes
        const deltaMinutes = elapsedWholeMinutes * playbackStepMinutes

        setCurrentMinuteIndex((current) => {
          const nextMinuteIndex = (current + deltaMinutes) % MINUTES_PER_DAY
          playbackMinuteCursorRef.current = nextMinuteIndex
          return nextMinuteIndex
        })
      }

      animationFrameId = window.requestAnimationFrame(tick)
    }

    animationFrameId = window.requestAnimationFrame(tick)

    return () => {
      window.cancelAnimationFrame(animationFrameId)
    }
  }, [playbackSpeed, minuteCount])

  useEffect(() => {
    if (minuteCount === 0) {
      setCurrentMinuteIndex(0)
      playbackMinuteCursorRef.current = 0
      setPlaybackSpeed(0)
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

  const handleChangePlaybackSpeed = useCallback((nextSpeed: 1 | 2 | 4) => {
    if (minuteCount === 0) {
      return
    }

    lastNonZeroPlaybackSpeedRef.current = nextSpeed
    setPlaybackSpeed(nextSpeed)
  }, [minuteCount])

  const handleTogglePlayback = useCallback(() => {
    if (minuteCount === 0) {
      return
    }

    setPlaybackSpeed((current) => {
      if (current === 0) {
        return lastNonZeroPlaybackSpeedRef.current
      }
      return 0
    })
  }, [minuteCount])

  const handleToggleDemoZone = useCallback(() => {
    setIsDemoZoneVisible((current) => !current)
  }, [])

  const reading = hoveredSensor ? toWeatherReading(hoveredSensor) : null
  const isTimelineLoading = activeMetric ? Boolean(timelineInFlightByMetric[activeMetric]) : false
  const timelineError = activeMetric ? (timelineErrorsByMetric[activeMetric] ?? null) : null
  const metricsSeries = metricsByDate[TIMELINE_DATE] ?? null
  const metricsError = metricsErrorsByDate[TIMELINE_DATE] ?? null
  const isMetricsLoading = Boolean(metricsInFlightByDate[TIMELINE_DATE])
  const selectedHistory = selectedSensor ? (historyPointsBySensor[selectedSensor.id] ?? []) : []
  const showSensorBars = sensorVisualizationMode === 'bars'
  const showSensorSymbols = sensorVisualizationMode === 'symbols'

  useEffect(() => {
    if (showSensorSymbols) {
      return
    }

    setHoveredSensor(null)
    historyControllerRef.current?.abort()
    setSelectedSensor(null)
    setHistoryLoading(false)
    setHistoryError(null)
  }, [showSensorSymbols])

  const currentHeightAnchorValue = useMemo<number | null>(() => {
    if (!renderedMetric || !metricsSeries || metricsSeries.items.length === 0) {
      return null
    }

    const frameCount = metricsSeries.items.length
    const { startFrameIndex, endFrameIndex, t } = resolveMinuteFrameBlendWindow(
      currentMinuteIndex,
      frameCount,
    )

    const startPoint = metricsSeries.items[startFrameIndex]
    const endPoint = metricsSeries.items[endFrameIndex] ?? startPoint

    const startValue = renderedMetric === 'aqi' ? startPoint?.avgAqi : startPoint?.avgTemperatureC
    const endValue = renderedMetric === 'aqi' ? endPoint?.avgAqi : endPoint?.avgTemperatureC

    if (typeof startValue === 'number' && typeof endValue === 'number') {
      return startValue + ((endValue - startValue) * t)
    }

    if (typeof startValue === 'number') {
      return startValue
    }

    if (typeof endValue === 'number') {
      return endValue
    }

    return null
  }, [currentMinuteIndex, metricsSeries, renderedMetric])

  const timelineValueRange = useMemo<{ minValue: number; maxValue: number } | null>(() => {
    if (!activeTimeline || activeTimeline.frames.length === 0) {
      return null
    }

    let minValue = Number.POSITIVE_INFINITY
    let maxValue = Number.NEGATIVE_INFINITY

    for (const frame of activeTimeline.frames) {
      for (const value of frame.values) {
        if (!Number.isFinite(value)) {
          continue
        }
        minValue = Math.min(minValue, value)
        maxValue = Math.max(maxValue, value)
      }
    }

    if (!Number.isFinite(minValue) || !Number.isFinite(maxValue)) {
      return null
    }

    return { minValue, maxValue }
  }, [activeTimeline])

  const stableRelativeColorRange = useMemo<number | null>(() => {
    if (!activeTimeline || !renderedMetric || activeTimeline.frames.length === 0) {
      return null
    }

    let maxRange = 0

    for (const frame of activeTimeline.frames) {
      const frameMean = computeFrameMean(frame.values)
      const frameRange = computeRelativeRange(frame.values, frameMean, renderedMetric)
      if (frameRange > maxRange) {
        maxRange = frameRange
      }
    }

    return maxRange > 0 ? maxRange : null
  }, [activeTimeline, renderedMetric])

  const sensorBarLayerProps = useMemo(() => ({
    sensors,
    metric: renderedMetric,
    timeline: activeTimeline,
    currentValues: throttledSensorBarFrameValues,
    colorMode,
    relativeColorRange: stableRelativeColorRange,
    minValue: timelineValueRange?.minValue ?? null,
    maxValue: timelineValueRange?.maxValue ?? null,
    isVisible: showSensorBars,
  }), [
    sensors,
    renderedMetric,
    activeTimeline,
    throttledSensorBarFrameValues,
    colorMode,
    stableRelativeColorRange,
    timelineValueRange,
    showSensorBars,
  ])

  useEffect(() => {
    const map = mapCollection.current?.getMap()
    if (!map) {
      return
    }

    if (viewMode === '3d') {
      map.easeTo({
        pitch: SURFACE_PITCH,
        bearing: SURFACE_BEARING,
        duration: 400,
      })
      return
    }

    map.easeTo({
      pitch: 0,
      bearing: 0,
      duration: 300,
    })
  }, [mapCollection, viewMode])

  return (
    <>
      {viewMode === '2d' && renderedMetric && activeTimeline && (
        <InterpolationHeatmapLayer
          timeline={activeTimeline}
          currentValues={currentFrameValues}
          metric={renderedMetric}
          colorMode={colorMode}
          relativeColorRange={stableRelativeColorRange}
        />
      )}

      {renderedMetric && activeTimeline && (
        <Surface3DLayer
          timeline={activeTimeline}
          currentValues={currentFrameValues}
          metric={renderedMetric}
          colorMode={colorMode}
          relativeColorRange={stableRelativeColorRange}
          heightAnchorValue={currentHeightAnchorValue}
          visible={viewMode === '3d'}
        />
      )}

      {renderedMetric && (
        <DemoZoneLayer
          metric={renderedMetric}
          isVisible={isDemoZoneVisible}
        />
      )}

      <div className="metric-controls" role="group" aria-label="Interpolation metric selector">
        <div className="metric-controls__segmented" role="group" aria-label="Metric selector">
          {METRICS.map((metric) => (
            <button
              key={metric}
              type="button"
              className={`metric-controls__segment-button metric-controls__segment-button--${metric}${metric === activeMetric ? ' metric-controls__segment-button--active' : ''}`}
              onClick={() => handleMetricSelect(metric)}
              title={METRIC_LABELS[metric]}
            >
              {metric === 'temperature' ? <MdDeviceThermostat aria-hidden="true" /> : <MdAir aria-hidden="true" />}
              <span>{metric === 'temperature' ? 'Temp' : 'AQI'}</span>
            </button>
          ))}
        </div>

        <div className="metric-controls__divider" aria-hidden="true" />

        <button
          type="button"
          className={`metric-controls__button${sensorVisualizationMode !== 'off' ? ' metric-controls__button--active' : ''}`}
          onClick={handleCycleSensorVisualizationMode}
          title="Cycle sensor visualization mode: Symbols, Bars, Off"
        >
          <span className="metric-controls__button-label">
            Sensors: {SENSOR_VISUAL_MODE_LABELS[sensorVisualizationMode]}
          </span>
          <span className="metric-controls__button-icon" aria-hidden="true"><MdSensors /></span>
        </button>

        <button
          type="button"
          className="metric-controls__button"
          onClick={() => setColorMode((current) => (current === 'absolute' ? 'relative' : 'absolute'))}
          title="Relative mode highlights neighborhoods warmer or cooler than the city average."
        >
          <span className="metric-controls__button-label">Color: {colorMode === 'absolute' ? 'Absolute' : 'Relative'}</span>
          <span className="metric-controls__button-icon" aria-hidden="true"><MdOutlinePalette /></span>
        </button>

        <button
          type="button"
          className="metric-controls__button"
          onClick={() => setViewMode((current) => (current === '2d' ? '3d' : '2d'))}
          disabled={!activeTimeline}
          title="Toggle 2D/3D view"
        >
          <span className="metric-controls__button-label">View: {viewMode === '2d' ? '2D Heatmap' : '3D Surface'}</span>
          <span className="metric-controls__button-icon" aria-hidden="true"><MdTerrain /></span>
        </button>

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

      {activeTimeline && renderedMetric && timelineValueRange && (
        <BottomControlsBar
          minuteCount={minuteCount}
          currentMinuteIndex={currentMinuteIndex}
          playbackSpeed={playbackSpeed}
          isTimelineLoading={isTimelineLoading}
          onTogglePlayback={handleTogglePlayback}
          onChangePlaybackSpeed={handleChangePlaybackSpeed}
          metric={renderedMetric}
          series={metricsSeries}
          metricsError={metricsError}
          isMetricsLoading={isMetricsLoading}
          onSeek={handleSeek}
          colorMode={colorMode}
          currentValues={currentFrameValues}
          relativeColorRange={stableRelativeColorRange}
          minValue={timelineValueRange.minValue}
          maxValue={timelineValueRange.maxValue}
          showColorBar={true}
          timelineDate={TIMELINE_DATE}
          onToggleDemoZone={handleToggleDemoZone}
          isDemoZoneVisible={isDemoZoneVisible}
        />
      )}

      {renderedMetric && (
        <MemoizedSensorBarLayer {...sensorBarLayerProps} />
      )}

      {sensors.map((sensor) => (
        <SensorMarker
          key={sensor.id}
          sensor={sensor}
          onHoverStart={handleHoverStart}
          onHoverEnd={handleHoverEnd}
          onClick={handleSensorClick}
          isVisible={showSensorSymbols}
          isSelected={selectedSensor?.id === sensor.id}
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
