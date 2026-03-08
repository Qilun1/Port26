import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { Sensor } from '../../features/sensors/model/sensor'
import type { SensorHistoryPoint } from '../../features/sensors/model/weatherReading'

interface SensorHistoryPanelProps {
  sensor: Sensor
  points: SensorHistoryPoint[]
  isLoading: boolean
  error: string | null
  onClose: () => void
}

function formatHourLabel(value: string): string {
  const date = new Date(value)
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

function formatTooltipLabel(value: string): string {
  const date = new Date(value)
  return date.toLocaleString([], {
    hour: '2-digit',
    minute: '2-digit',
    day: '2-digit',
    month: '2-digit',
  })
}

export function SensorHistoryPanel({
  sensor,
  points,
  isLoading,
  error,
  onClose,
}: SensorHistoryPanelProps) {
  return (
    <aside className="sensor-history-panel" aria-label="Sensor history panel">
      <header className="sensor-history-panel__header">
        <div>
          <h2 className="sensor-history-panel__title">{sensor.name}</h2>
          <p className="sensor-history-panel__meta">Sensor #{sensor.id}</p>
        </div>
        <button
          type="button"
          className="sensor-history-panel__close"
          onClick={onClose}
          aria-label="Close sensor history panel"
        >
          Close
        </button>
      </header>

      {isLoading && <p className="sensor-history-panel__state">Loading historical readings...</p>}
      {!isLoading && error && <p className="sensor-history-panel__state sensor-history-panel__state--error">{error}</p>}
      {!isLoading && !error && points.length === 0 && (
        <p className="sensor-history-panel__state">No historical readings available for this sensor.</p>
      )}

      {!isLoading && !error && points.length > 0 && (
        <div className="sensor-history-panel__charts">
          <section className="sensor-history-panel__chart-card">
            <h3 className="sensor-history-panel__chart-title">Temperature</h3>
            <div className="sensor-history-panel__chart-wrap">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={points} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                  <CartesianGrid stroke="rgba(255, 255, 255, 0.12)" strokeDasharray="3 3" />
                  <XAxis
                    dataKey="timestamp"
                    tickFormatter={formatHourLabel}
                    stroke="rgba(255, 255, 255, 0.72)"
                    minTickGap={22}
                  />
                  <YAxis stroke="rgba(255, 255, 255, 0.72)" width={36} />
                  <Tooltip labelFormatter={formatTooltipLabel} />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="temperature"
                    name="Temperature C"
                    stroke="#6dd3a8"
                    strokeWidth={2}
                    dot={false}
                    connectNulls
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </section>

          <section className="sensor-history-panel__chart-card">
            <h3 className="sensor-history-panel__chart-title">Air Quality</h3>
            <div className="sensor-history-panel__chart-wrap">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={points} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                  <CartesianGrid stroke="rgba(255, 255, 255, 0.12)" strokeDasharray="3 3" />
                  <XAxis
                    dataKey="timestamp"
                    tickFormatter={formatHourLabel}
                    stroke="rgba(255, 255, 255, 0.72)"
                    minTickGap={22}
                  />
                  <YAxis stroke="rgba(255, 255, 255, 0.72)" width={36} />
                  <Tooltip labelFormatter={formatTooltipLabel} />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="aqi"
                    name="AQI"
                    stroke="#ffb466"
                    strokeWidth={2}
                    dot={false}
                    connectNulls
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </section>
        </div>
      )}
    </aside>
  )
}
