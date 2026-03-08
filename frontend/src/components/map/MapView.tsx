import Map from 'react-map-gl/maplibre'
import { SensorLayer } from './SensorLayer'
import 'maplibre-gl/dist/maplibre-gl.css'
import { helsinkiInitialView, mapBounds, mapStyleUrl } from '../../lib/map/mapConfig'

export function MapView() {
  return (
    <main className="map-screen" aria-label="Helsinki weather sensor map">
      <Map
        initialViewState={helsinkiInitialView}
        mapStyle={mapStyleUrl}
        maxBounds={mapBounds}
        minZoom={8.5}
        maxZoom={14.5}
        attributionControl={false}
      >
        <SensorLayer />
      </Map>
    </main>
  )
}
