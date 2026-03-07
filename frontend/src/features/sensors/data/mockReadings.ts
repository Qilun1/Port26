import type { WeatherReading } from '../model/weatherReading'

export const mockReadingsBySensorId: Record<string, WeatherReading> = {
  'HEL-CENTRE-001': {
    sensorId: 'HEL-CENTRE-001',
    temperatureC: -2.4,
    humidityPct: 78,
    windSpeedMs: 5.1,
    timestamp: '2026-03-07T11:23:00.000Z',
  },
  'ESPOO-OTANIEMI-002': {
    sensorId: 'ESPOO-OTANIEMI-002',
    temperatureC: -1.9,
    humidityPct: 81,
    windSpeedMs: 6.3,
    timestamp: '2026-03-07T11:23:00.000Z',
  },
  'VANTAA-AIRPORT-003': {
    sensorId: 'VANTAA-AIRPORT-003',
    temperatureC: -3.1,
    humidityPct: 74,
    windSpeedMs: 7.8,
    timestamp: '2026-03-07T11:23:00.000Z',
  },
  'EAST-SIPOO-004': {
    sensorId: 'EAST-SIPOO-004',
    temperatureC: -3.8,
    humidityPct: 71,
    windSpeedMs: 6.9,
    timestamp: '2026-03-07T11:23:00.000Z',
  },
  'KIRKKONUMMI-005': {
    sensorId: 'KIRKKONUMMI-005',
    temperatureC: -2.7,
    humidityPct: 76,
    windSpeedMs: 5.7,
    timestamp: '2026-03-07T11:23:00.000Z',
  },
  'SUOMENLINNA-006': {
    sensorId: 'SUOMENLINNA-006',
    temperatureC: -1.4,
    humidityPct: 84,
    windSpeedMs: 8.6,
    timestamp: '2026-03-07T11:23:00.000Z',
  },
}
