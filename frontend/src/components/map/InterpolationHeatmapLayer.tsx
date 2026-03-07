import { useMemo } from 'react'
import { Layer, Source } from 'react-map-gl/maplibre'
import type { LayerProps } from 'react-map-gl/maplibre'
import type { InterpolationMetric } from '../../features/sensors/model/interpolation'
import type { InterpolationTimeline } from '../../features/sensors/model/interpolationTimeline'
import {
  buildSparseSurfaceContext,
  createSparseInterpolationSurface,
} from '../../lib/map/interpolationSurface'

const SOURCE_ID = 'interpolation-surface-source'
const LAYER_ID = 'interpolation-surface-layer'

interface Props {
  timeline: InterpolationTimeline
  currentValues: ArrayLike<number>
  metric: InterpolationMetric
}

export function InterpolationHeatmapLayer({ timeline, currentValues, metric }: Props) {
  const staticContext = useMemo(
    () =>
      buildSparseSurfaceContext(
        timeline.rows,
        timeline.cols,
        timeline.boundingBox,
        timeline.activeIndices,
        timeline.frames.map((frame) => frame.values),
      ),
    [timeline],
  )

  const surface = useMemo(() => {
    if (!staticContext) {
      return null
    }
    return createSparseInterpolationSurface(staticContext, metric, currentValues)
  }, [staticContext, metric, currentValues])

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
