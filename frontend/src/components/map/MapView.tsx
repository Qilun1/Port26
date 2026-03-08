import Map from 'react-map-gl/maplibre'
import { Link } from 'react-router-dom'
import { SensorLayer } from './SensorLayer'
import 'maplibre-gl/dist/maplibre-gl.css'
import { helsinkiInitialView, mapBounds, mapStyleUrl } from '../../lib/map/mapConfig'

export function MapView() {
  return (
    <main className="map-screen" aria-label="Helsinki weather sensor map">
      <aside className="brand-overlay" aria-label="Company branding and sensor status">
        <Link
          className="brand-overlay__logo-link"
          to="/"
          aria-label="Go to WeatherSens landing page"
          title="Open WeatherSens about page"
        >
          <img
            className="brand-overlay__logo"
            src="/weathersenslogo_trsparent.png"
            alt="WeatherSens"
          />
        </Link>
        <p className="brand-overlay__status">
          Sensors online: <span>185</span>
        </p>
      </aside>

      <Map
        initialViewState={helsinkiInitialView}
        mapStyle={mapStyleUrl}
        maxBounds={mapBounds}
        minZoom={8.5}
        maxZoom={14.5}
        maxPitch={85}
        attributionControl={false}
      >
        <SensorLayer />
      </Map>
    </main>
  )
}
