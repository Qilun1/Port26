import type { InterpolationMetric } from '../../features/sensors/model/interpolation'
import type { ColorMode } from '../../features/sensors/model/colorMode'

interface VisualizationContextProps {
  metric: InterpolationMetric
  colorMode: ColorMode
  currentMinuteIndex: number
  timelineDate: string
}

function formatMinuteClock(minuteIndex: number): string {
  const safeMinute = Math.max(0, Math.min(1439, Math.floor(minuteIndex)))
  const hours = Math.floor(safeMinute / 60)
  const minutes = safeMinute % 60
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`
}

function formatDateLong(dateString: string): string {
  try {
    const date = new Date(dateString)
    const day = date.getDate()
    const suffix = (() => {
      if (day > 3 && day < 21) return 'th'
      switch (day % 10) {
        case 1: return 'st'
        case 2: return 'nd'
        case 3: return 'rd'
        default: return 'th'
      }
    })()
    
    const monthNames = [
      'January', 'February', 'March', 'April', 'May', 'June',
      'July', 'August', 'September', 'October', 'November', 'December'
    ]
    
    return `${day}${suffix} of ${monthNames[date.getMonth()]} ${date.getFullYear()}`
  } catch {
    return dateString
  }
}

function getVisualizationDescription(metric: InterpolationMetric, colorMode: ColorMode): string {
  if (colorMode === 'relative') {
    return metric === 'aqi' 
      ? 'Relative difference in Air Quality Index (AQI)'
      : 'Relative difference in Temperature'
  }
  
  return metric === 'aqi'
    ? 'Air Quality Index (AQI)'
    : 'Temperature'
}

function getMetricColor(metric: InterpolationMetric): string {
  return metric === 'aqi' ? '#9b6bdb' : '#4d92e8'
}

export function VisualizationContext({
  metric,
  colorMode,
  currentMinuteIndex,
  timelineDate,
}: VisualizationContextProps) {
  const description = getVisualizationDescription(metric, colorMode)
  const dateFormatted = formatDateLong(timelineDate)
  const timeFormatted = formatMinuteClock(currentMinuteIndex)
  const metricColor = getMetricColor(metric)

  return (
    <div className="visualization-context">
      <div className="visualization-context__row">
        <span className="visualization-context__label">Displaying:</span>
        <span 
          className="visualization-context__value visualization-context__value--highlight"
          style={{ color: metricColor }}
        >
          {description}
        </span>
      </div>
      <div className="visualization-context__row">
        <span className="visualization-context__label">Date:</span>
        <span className="visualization-context__value visualization-context__value--highlight">{dateFormatted}</span>
      </div>
      <div className="visualization-context__row visualization-context__row--prominent">
        <span className="visualization-context__label">Time:</span>
        <span className="visualization-context__value visualization-context__value--time">{timeFormatted}</span>
      </div>
    </div>
  )
}
