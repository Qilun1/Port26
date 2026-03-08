import { createContext, useContext, useState, type PropsWithChildren } from 'react'
import type { Sensor } from '../../features/sensors/model/sensor'
import type { InterpolationTimeline } from '../../features/sensors/model/interpolationTimeline'

interface SensorDataContextValue {
  sensors: Sensor[]
  aqiTimeline: InterpolationTimeline | null
  loading: boolean
  error: string | null
}

const SensorDataContext = createContext<SensorDataContextValue | undefined>(undefined)

export function SensorDataProvider({ children }: PropsWithChildren) {
  // Simplified provider - no preloading, just provides empty state
  const [loading] = useState(false)

  const value: SensorDataContextValue = {
    sensors: [],
    aqiTimeline: null,
    loading,
    error: null,
  }

  return <SensorDataContext.Provider value={value}>{children}</SensorDataContext.Provider>
}

export function useSensorData(): SensorDataContextValue {
  const context = useContext(SensorDataContext)
  if (context === undefined) {
    throw new Error('useSensorData must be used within a SensorDataProvider')
  }
  return context
}
