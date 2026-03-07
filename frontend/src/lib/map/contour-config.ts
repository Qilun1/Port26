export interface SurfaceContourConfig {
  enabled: boolean
  interval: number
  bandHalfWidth: number
  intensity: number
  colorModulation: [number, number, number]
}

// Centralized contour tuning for 3D surface readability.
// interval: distance between contour lines in normalized [0..1] value space.
// bandHalfWidth: half-width of each contour band in normalized interval-space.
// intensity: how strongly contour lines modulate the lit color.
// colorModulation: contour tint added at contour center (black keeps lines subtle).
export const SURFACE_CONTOUR_CONFIG: SurfaceContourConfig = {
  enabled: true,
  interval: 0.12,
  bandHalfWidth: 0.08,
  intensity: 0.14,
  colorModulation: [0.0, 0.0, 0.0],
}
