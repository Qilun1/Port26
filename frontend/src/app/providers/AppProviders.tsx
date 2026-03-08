import type { PropsWithChildren } from 'react'
import { BrowserRouter } from 'react-router-dom'
import { SensorDataProvider } from './SensorDataProvider'

export function AppProviders({ children }: PropsWithChildren) {
  return (
    <BrowserRouter>
      <SensorDataProvider>{children}</SensorDataProvider>
    </BrowserRouter>
  )
}
