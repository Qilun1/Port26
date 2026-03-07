import { useMemo } from 'react'
import { Layer, Source } from 'react-map-gl/maplibre'
import type { LayerProps } from 'react-map-gl/maplibre'
import type {
  InterpolatedGrid,
  InterpolationMetric,
} from '../../features/sensors/model/interpolation'
import { createInterpolationSurface } from '../../lib/map/interpolationSurface'

const SOURCE_ID = 'interpolation-surface-source'
const LAYER_ID = 'interpolation-surface-layer'

interface Props {
  grid: InterpolatedGrid
  metric: InterpolationMetric
}

export function InterpolationHeatmapLayer({ grid, metric }: Props) {
  const surface = useMemo(() => createInterpolationSurface(grid, metric), [grid, metric])

  if (!surface) {
    return null
  }

  const layer: LayerProps = {
    id: LAYER_ID,
    type: 'raster',
    source: SOURCE_ID,
    paint: {
      'raster-opacity': 0.66,
      'raster-resampling': 'linear',
    },
  }

  return (
    <Source
      id={SOURCE_ID}
      type="image"
      url={surface.url}
      coordinates={surface.coordinates}
    >
      <Layer {...layer} />
    </Source>
  )
}
