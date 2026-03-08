/**
 * Demo risk zone overlay layer
 * Displays metric-specific risk zones on the map
 */

import { Layer, Source } from 'react-map-gl/maplibre'
import { AQI_RISK_ZONE, TEMPERATURE_HEAT_ISLAND } from '../../lib/map/demoRiskZones'
import type { InterpolationMetric } from '../../features/sensors/model/interpolation'

interface DemoZoneLayerProps {
  metric: InterpolationMetric
  isVisible: boolean
}

export function DemoZoneLayer({ metric, isVisible }: DemoZoneLayerProps) {
  if (!isVisible) {
    return null
  }

  const zoneData = metric === 'aqi' ? AQI_RISK_ZONE : TEMPERATURE_HEAT_ISLAND
  const fillColor = metric === 'aqi' ? '#9b59b6' : '#e74c3c' // Purple for AQI, Red for temperature
  const lineColor = metric === 'aqi' ? '#8e44ad' : '#c0392b' // Darker shades for outline

  return (
    <Source id="demo-risk-zone" type="geojson" data={zoneData}>
      <Layer
        id="demo-risk-zone-fill"
        type="fill"
        paint={{
          'fill-color': fillColor,
          'fill-opacity': 0.5,
        }}
      />
      <Layer
        id="demo-risk-zone-outline"
        type="line"
        paint={{
          'line-color': lineColor,
          'line-width': 2,
        }}
      />
    </Source>
  )
}
