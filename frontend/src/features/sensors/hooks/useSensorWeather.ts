import { useEffect, useRef, useState } from 'react'
import { getCurrentWeatherBySensorId } from '../api/sensorsApi'
import type { WeatherReading } from '../model/weatherReading'

interface UseSensorWeatherResult {
  reading: WeatherReading | null
  isLoading: boolean
}

export function useSensorWeather(sensorId: string | null): UseSensorWeatherResult {
  const requestIdRef = useRef(0)
  const [reading, setReading] = useState<WeatherReading | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    if (!sensorId) {
      setReading(null)
      setIsLoading(false)
      return
    }

    requestIdRef.current += 1
    const requestId = requestIdRef.current
    setIsLoading(true)

    void getCurrentWeatherBySensorId(sensorId)
      .then((response) => {
        if (requestId !== requestIdRef.current) {
          return
        }
        setReading(response)
      })
      .finally(() => {
        if (requestId === requestIdRef.current) {
          setIsLoading(false)
        }
      })
  }, [sensorId])

  return {
    reading,
    isLoading,
  }
}
