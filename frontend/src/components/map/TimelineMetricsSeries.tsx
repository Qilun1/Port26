import { useMemo } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { InterpolationMetric } from '../../features/sensors/model/interpolation'
import type { InterpolationTimestepMetricsSeries } from '../../features/sensors/model/interpolationMetrics'

interface TimelineMetricsSeriesProps {
  metric: InterpolationMetric
  series: InterpolationTimestepMetricsSeries | null
  currentMinuteIndex: number
  isLoading: boolean
  error: string | null
  onSeek: (nextMinuteIndex: number) => void
}

type ChartPoint = {
  minuteIndex: number
  avgAqi: number | null
  avgTemperatureC: number | null
}

function formatMinuteLabel(minuteIndex: number): string {
  const safeMinute = Math.max(0, Math.min(1439, Math.round(minuteIndex)))
  const hours = Math.floor(safeMinute / 60)
  const minutes = safeMinute % 60
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`
}

export function TimelineMetricsSeries({
  metric,
  series,
  currentMinuteIndex,
  isLoading,
  error,
  onSeek,
}: TimelineMetricsSeriesProps) {
  const chartData = useMemo<ChartPoint[]>(() => {
    if (!series) {
      return []
    }

    return series.items.map((item, index) => ({
      minuteIndex: Math.min(1439, index * 15),
      avgAqi: item.avgAqi,
      avgTemperatureC: item.avgTemperatureC,
    }))
  }, [series])

  const activeDataKey = metric === 'aqi' ? 'avgAqi' : 'avgTemperatureC'
  const activeStroke = metric === 'aqi' ? '#ffb466' : '#6dd3a8'

  const handleChartClick = (state: unknown) => {
    const activeLabel = (state as { activeLabel?: unknown } | undefined)?.activeLabel
    if (typeof activeLabel === 'number' && Number.isFinite(activeLabel)) {
      onSeek(activeLabel)
    }
  }

  return (
    <section className="timeline-metrics" aria-label="Timeline aggregate metric series">
      {isLoading && <div className="timeline-metrics__state">Loading aggregate metrics...</div>}
      {!isLoading && error && <div className="timeline-metrics__state timeline-metrics__state--error">{error}</div>}
      {!isLoading && !error && chartData.length === 0 && (
        <div className="timeline-metrics__state">No aggregate metrics available for this day.</div>
      )}

      {!isLoading && !error && chartData.length > 0 && (
        <div className="timeline-metrics__chart-wrap">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 8, right: 12, left: 0, bottom: 0 }} onClick={handleChartClick}>
              <CartesianGrid stroke="rgba(255, 255, 255, 0.12)" strokeDasharray="3 3" />
              <XAxis
                dataKey="minuteIndex"
                type="number"
                domain={[0, 1439]}
                tickFormatter={formatMinuteLabel}
                stroke="rgba(255, 255, 255, 0.72)"
                minTickGap={22}
              />
              <YAxis stroke="rgba(255, 255, 255, 0.72)" width={42} />
              <Tooltip
                labelFormatter={(value) => formatMinuteLabel(Number(value))}
                formatter={(value) => (typeof value === 'number' ? value.toFixed(2) : value)}
              />
              <ReferenceLine x={currentMinuteIndex} stroke="rgba(93, 196, 255, 0.85)" strokeWidth={2} />
              <Line
                type="monotone"
                dataKey={activeDataKey}
                name={metric === 'aqi' ? 'Average AQI' : 'Average Temperature C'}
                stroke={activeStroke}
                strokeWidth={2}
                dot={false}
                connectNulls
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </section>
  )
}
