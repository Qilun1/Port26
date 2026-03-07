import { Marker } from 'react-map-gl/maplibre'
import type { Sensor } from '../../features/sensors/model/sensor'

interface SensorMarkerProps {
  sensor: Sensor
  onHoverStart: (sensor: Sensor) => void
  onHoverEnd: () => void
  onClick: (sensor: Sensor) => void
}

export function SensorMarker({
  sensor,
  onHoverStart,
  onHoverEnd,
  onClick,
}: SensorMarkerProps) {
  return (
    <Marker latitude={sensor.latitude} longitude={sensor.longitude} anchor="center">
      <button
        className="sensor-marker"
        type="button"
        aria-label={`Sensor ${sensor.name}`}
        onMouseEnter={() => onHoverStart(sensor)}
        onMouseLeave={onHoverEnd}
        onClick={() => onClick(sensor)}
      />
    </Marker>
  )
}
