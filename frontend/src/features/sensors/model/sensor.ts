export interface Sensor {
  id: string
  name: string
  latitude: number
  longitude: number
  latestTemperatureC?: number | null
  latestAirPressureHpa?: number | null
  latestAqi?: number | null
}
