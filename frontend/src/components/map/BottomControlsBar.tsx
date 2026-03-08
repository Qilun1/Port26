import { MdLocalFireDepartment, MdWarningAmber } from 'react-icons/md'
import type { InterpolationMetric } from '../../features/sensors/model/interpolation'
import type { InterpolationTimestepMetricsSeries } from '../../features/sensors/model/interpolationMetrics'
import type { ColorMode } from '../../features/sensors/model/colorMode'
import { TimelineControls } from './TimelineControls'
import { TimelineMetricsSeries } from './TimelineMetricsSeries'
import { ColorBarLegend } from './ColorBarLegend'
import { VisualizationContext } from './VisualizationContext'

interface BottomControlsBarProps {
  // Timeline Controls props
  minuteCount: number
  currentMinuteIndex: number
  playbackSpeed: 0 | 1 | 2 | 4
  isTimelineLoading: boolean
  onTogglePlayback: () => void
  onChangePlaybackSpeed: (speed: 1 | 2 | 4) => void

  // Timeline Metrics props
  metric: InterpolationMetric | null
  series: InterpolationTimestepMetricsSeries | null
  metricsError: string | null
  isMetricsLoading: boolean
  onSeek: (nextMinuteIndex: number) => void

  // ColorBar Legend props
  colorMode: ColorMode
  currentValues: ArrayLike<number>
  relativeColorRange: number | null
  minValue: number
  maxValue: number

  // Visibility control
  showColorBar: boolean

  // Timeline date
  timelineDate: string

  // Demo zone overlay
  onToggleDemoZone?: () => void
  isDemoZoneVisible?: boolean
}

/**
 * Unified bottom control bar containing playback controls, timeline chart, and color legend.
 * Provides a clean, horizontally-aligned interface for timeline navigation and visualization.
 */
export function BottomControlsBar({
  minuteCount,
  currentMinuteIndex,
  playbackSpeed,
  isTimelineLoading,
  onTogglePlayback,
  onChangePlaybackSpeed,
  metric,
  series,
  metricsError,
  isMetricsLoading,
  onSeek,
  colorMode,
  currentValues,
  relativeColorRange,
  minValue,
  maxValue,
  showColorBar,
  timelineDate,
  onToggleDemoZone,
  isDemoZoneVisible = false,
}: BottomControlsBarProps) {
  if (!metric) {
    return null
  }

  return (
    <div className="bottom-controls-bar">
      <div className="bottom-controls-bar__section bottom-controls-bar__section--left">
        <div className="bottom-controls-bar__left-stack">
          <VisualizationContext
            metric={metric}
            colorMode={colorMode}
            currentMinuteIndex={currentMinuteIndex}
            timelineDate={timelineDate}
          />
          <TimelineControls
            minuteCount={minuteCount}
            currentMinuteIndex={currentMinuteIndex}
            playbackSpeed={playbackSpeed}
            isLoading={isTimelineLoading}
            onTogglePlayback={onTogglePlayback}
            onChangePlaybackSpeed={onChangePlaybackSpeed}
          />
          <TimelineMetricsSeries
            metric={metric}
            series={series}
            currentMinuteIndex={currentMinuteIndex}
            isLoading={isMetricsLoading}
            error={metricsError}
            onSeek={onSeek}
          />
        </div>
      </div>

      {showColorBar && (
        <div className="bottom-controls-bar__section bottom-controls-bar__section--right">
          <div className="bottom-controls-bar__right-group">
            {onToggleDemoZone && (
              <button
                type="button"
                className={`demo-zone-toggle demo-zone-toggle--${metric}${isDemoZoneVisible ? ' demo-zone-toggle--active' : ''}`}
                onClick={onToggleDemoZone}
                title={metric === 'aqi' ? 'Toggle air pollution risk zones' : 'Toggle urban heat island zones'}
              >
                <span className="demo-zone-toggle__icon">
                  {metric === 'aqi' ? (
                    <MdWarningAmber aria-hidden="true" />
                  ) : (
                    <MdLocalFireDepartment aria-hidden="true" />
                  )}
                </span>
                <span className="demo-zone-toggle__text">
                  {metric === 'aqi' ? 'Display risk zones' : 'Display heat islands'}
                </span>
              </button>
            )}
            <ColorBarLegend
              metric={metric}
              colorMode={colorMode}
              currentValues={currentValues}
              relativeColorRange={relativeColorRange}
              minValue={minValue}
              maxValue={maxValue}
            />
          </div>
        </div>
      )}
    </div>
  )
}
