import type { Sensor } from '../../features/sensors/model/sensor'
import type { WeatherReading } from '../../features/sensors/model/weatherReading'
import {
  toAirPressureLabel,
  toAqiLabel,
  toHumidityLabel,
  toTemperatureLabel,
  toTimestampLabel,
  toWindSpeedLabel,
} from '../../features/sensors/utils/sensorFormatters'

interface SensorTooltipProps {
  sensor: Sensor
  reading: WeatherReading | null
  isLoading: boolean
}

export function SensorTooltip({
  sensor,
  reading,
  isLoading,
}: SensorTooltipProps) {
  return (
    <div className="sensor-tooltip">
      <div className="sensor-tooltip__title">{sensor.name}</div>
      <div className="sensor-tooltip__sensor-id">{sensor.id}</div>

      {isLoading && <div className="sensor-tooltip__loading">Loading weather data...</div>}

      {!isLoading && !reading && (
        <div className="sensor-tooltip__loading">No reading available.</div>
      )}

      {!isLoading && reading && (
        <dl className="sensor-tooltip__stats">
          <div className="sensor-tooltip__row">
            <dt>Temperature</dt>
            <dd>{toTemperatureLabel(reading)}</dd>
          </div>
          <div className="sensor-tooltip__row">
            <dt>Humidity</dt>
            <dd>{toHumidityLabel(reading)}</dd>
          </div>
          <div className="sensor-tooltip__row">
            <dt>Wind</dt>
            <dd>{toWindSpeedLabel(reading)}</dd>
          </div>
          <div className="sensor-tooltip__row">
            <dt>Pressure</dt>
            <dd>{toAirPressureLabel(reading)}</dd>
          </div>
          <div className="sensor-tooltip__row">
            <dt>AQI</dt>
            <dd>{toAqiLabel(reading)}</dd>
          </div>
          <div className="sensor-tooltip__row sensor-tooltip__row--timestamp">
            <dt>Timestamp</dt>
            <dd>{toTimestampLabel(reading)}</dd>
          </div>
        </dl>
      )}
    </div>
  )
}
