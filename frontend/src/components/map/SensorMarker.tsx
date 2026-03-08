import { Marker } from 'react-map-gl/maplibre'
import type { Sensor } from '../../features/sensors/model/sensor'

interface SensorMarkerProps {
  sensor: Sensor
  onHoverStart: (sensor: Sensor) => void
  onHoverEnd: () => void
  onClick: (sensor: Sensor) => void
  isVisible: boolean
  isSelected: boolean
}

export function SensorMarker({
  sensor,
  onHoverStart,
  onHoverEnd,
  onClick,
  isVisible,
  isSelected,
}: SensorMarkerProps) {
  const className = [
    'sensor-marker',
    !isVisible && 'sensor-marker--hidden',
    isSelected && 'sensor-marker--selected',
  ].filter(Boolean).join(' ')

  return (
    <Marker latitude={sensor.latitude} longitude={sensor.longitude} anchor="center">
      <button
        className={className}
        type="button"
        aria-label={`Sensor ${sensor.name}`}
        onMouseEnter={() => onHoverStart(sensor)}
        onMouseLeave={onHoverEnd}
        onClick={() => onClick(sensor)}
        aria-hidden={!isVisible}
        tabIndex={isVisible ? 0 : -1}
      >
        <img
          className="sensor-marker__icon"
          src="/sensor_icon.png"
          alt=""
          aria-hidden="true"
        />
      </button>
    </Marker>
  )
}
