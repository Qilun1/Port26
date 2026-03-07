import { useMemo } from 'react'
import { Layer, Source } from 'react-map-gl/maplibre'
import type { LayerProps } from 'react-map-gl/maplibre'
import type { InterpolationMetric } from '../../features/sensors/model/interpolation'
import type { ColorMode } from '../../features/sensors/model/colorMode'
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
  colorMode: ColorMode
  relativeColorRange: number | null
}

export function InterpolationHeatmapLayer({
  timeline,
  currentValues,
  metric,
  colorMode,
  relativeColorRange,
}: Props) {
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
    return createSparseInterpolationSurface(
      staticContext,
      metric,
      colorMode,
      currentValues,
      relativeColorRange,
    )
  }, [staticContext, metric, colorMode, currentValues, relativeColorRange])

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
      'raster-fade-duration': 260,
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
