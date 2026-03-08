import { useEffect, useMemo, useState } from 'react'
import type { ColorMode } from '../../features/sensors/model/colorMode'
import type { InterpolationMetric } from '../../features/sensors/model/interpolation'
import {
  computeFrameMean,
  computeRelativeRange,
  getLegendGradient,
} from '../../lib/map/colorScales'

interface ColorBarLegendProps {
  metric: InterpolationMetric
  colorMode: ColorMode
  currentValues: ArrayLike<number>
  relativeColorRange: number | null
  minValue: number
  maxValue: number
}

/**
 * Compact color bar legend for 3D surface visualization.
 * Displays metric-specific color gradient and numeric range labels.
 * Fixed position in bottom-right corner of map.
 */
export function ColorBarLegend({
  metric,
  colorMode,
  currentValues,
  relativeColorRange,
  minValue,
  maxValue,
}: ColorBarLegendProps) {
  const midValue = (minValue + maxValue) / 2
  const frameMean = useMemo(() => computeFrameMean(currentValues), [currentValues])
  const relativeRange = useMemo(
    () => Number.isFinite(relativeColorRange)
      ? Number(relativeColorRange)
      : computeRelativeRange(currentValues, frameMean, metric),
    [currentValues, frameMean, metric, relativeColorRange],
  )

  const gradientStyle = useMemo(
    () => ({ backgroundImage: getLegendGradient(metric, colorMode, true) }),
    [metric, colorMode],
  )

  const formatValue = (val: number) => {
    if (metric === 'aqi') {
      return Math.round(val).toString()
    }
    return val.toFixed(1)
  }

  const minLabel = colorMode === 'relative' ? formatValue(-relativeRange) : formatValue(minValue)
  const midLabel = colorMode === 'relative' ? formatValue(0) : formatValue(midValue)
  const maxLabel = colorMode === 'relative' ? `+${formatValue(relativeRange)}` : formatValue(maxValue)

  const title = colorMode === 'relative' 
    ? (metric === 'aqi' ? 'AQI Difference' : 'Temperature Difference')
    : (metric === 'aqi' ? 'Air Quality Index' : 'Temperature °C')
  const [isTransitioning, setIsTransitioning] = useState(false)

  useEffect(() => {
    setIsTransitioning(true)
    const timeoutId = window.setTimeout(() => {
      setIsTransitioning(false)
    }, 260)

    return () => {
      window.clearTimeout(timeoutId)
    }
  }, [metric, colorMode])

  return (
    <div
      className={`color-bar-legend color-bar-legend--vertical${isTransitioning ? ' color-bar-legend--transitioning' : ''}`}
      aria-label={`${metric} color scale`}
    >
      <div className="color-bar-legend__title">{title}</div>

      <div className="color-bar-legend__content">
        <div className="color-bar-legend__bar color-bar-legend__bar--vertical" style={gradientStyle} />

        <div className="color-bar-legend__labels color-bar-legend__labels--vertical">
          <div className="color-bar-legend__label color-bar-legend__label--max">
            {maxLabel}
          </div>
          <div className="color-bar-legend__label color-bar-legend__label--mid">
            {midLabel}
          </div>
          <div className="color-bar-legend__label color-bar-legend__label--min">
            {minLabel}
          </div>
        </div>
      </div>
    </div>
  )
}
