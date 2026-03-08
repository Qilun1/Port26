import type { WeatherReading } from '../model/weatherReading'
import { formatTimestamp } from '../../../lib/utils/format'

const NA_LABEL = 'N/A'

function formatNullableNumber(
  value: number | null | undefined,
  fractionDigits: number,
  unit: string,
): string {
  if (value == null || Number.isNaN(value)) {
    return NA_LABEL
  }

  return `${value.toFixed(fractionDigits)} ${unit}`
}

export function toTemperatureLabel(reading: WeatherReading): string {
  return formatNullableNumber(reading.temperatureC, 1, 'C')
}

export function toHumidityLabel(reading: WeatherReading): string {
  return formatNullableNumber(reading.humidityPct, 0, '%')
}

export function toWindSpeedLabel(reading: WeatherReading): string {
  return formatNullableNumber(reading.windSpeedMs, 1, 'm/s')
}

export function toAirPressureLabel(reading: WeatherReading): string {
  return formatNullableNumber(reading.airPressureHpa, 1, 'hPa')
}

export function toAqiLabel(reading: WeatherReading): string {
  if (reading.aqi === null) {
    return NA_LABEL
  }

  return String(reading.aqi)
}

export function toTimestampLabel(reading: WeatherReading): string {
  if (!reading.timestamp) {
    return NA_LABEL
  }

  return formatTimestamp(reading.timestamp)
}
