import type { ViewState } from 'react-map-gl/maplibre'

export const helsinkiInitialView: ViewState = {
  latitude: 60.1699,
  longitude: 24.9384,
  zoom: 10.6,
  bearing: 0,
  pitch: 0,
  padding: { top: 0, bottom: 0, left: 0, right: 0 },
}

export const mapStyleUrl =
  'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'

export const mapBounds: [[number, number], [number, number]] = [
  [24.2, 59.85],
  [25.9, 60.8],
]
