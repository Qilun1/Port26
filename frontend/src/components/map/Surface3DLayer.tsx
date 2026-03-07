import { useEffect, useMemo, useRef } from 'react'
import type { MutableRefObject } from 'react'
import { useMap } from 'react-map-gl/maplibre'
import type { CustomLayerInterface, Map as MapLibreMap } from 'maplibre-gl'
import type { ColorMode } from '../../features/sensors/model/colorMode'
import type { InterpolationMetric } from '../../features/sensors/model/interpolation'
import type { InterpolationTimeline } from '../../features/sensors/model/interpolationTimeline'
import { buildSurfaceMeshContext } from '../../lib/map/surfaceMesh'
import { SURFACE_CONTOUR_CONFIG } from '../../lib/map/contour-config'
import {
  SURFACE_HEIGHT_SCALE,
  updateSurfaceColors,
  updateSurfaceNormalizedValues,
  updateSurfacePositions,
} from '../../lib/map/surfaceAttributes'

const SURFACE_LAYER_ID = 'interpolation-surface-3d-layer'

type LayerBuffers = {
  program: WebGLProgram
  positionBuffer: WebGLBuffer
  colorBuffer: WebGLBuffer
  contourValueBuffer: WebGLBuffer
  edgeDistanceBuffer: WebGLBuffer
  indexBuffer: WebGLBuffer
  positionLocation: number
  colorLocation: number
  contourValueLocation: number
  edgeDistanceLocation: number
  matrixLocation: WebGLUniformLocation
  contourParamsLocation: WebGLUniformLocation
  contourColorModLocation: WebGLUniformLocation
  positions: Float32Array
  targetPositions: Float32Array
  colors: Uint8Array
  targetColors: Uint8Array
  contourValues: Float32Array
  targetContourValues: Float32Array
  edgeDistances: Float32Array
  indexCount: number
  hasPendingTransition: boolean
}

interface Surface3DLayerProps {
  timeline: InterpolationTimeline
  currentValues: ArrayLike<number>
  metric: InterpolationMetric
  colorMode: ColorMode
  relativeColorRange: number | null
  heightAnchorValue: number | null
  visible: boolean
}

function createShader(gl: WebGLRenderingContext, type: number, source: string): WebGLShader {
  const shader = gl.createShader(type)
  if (!shader) {
    throw new Error('Failed to allocate WebGL shader.')
  }

  gl.shaderSource(shader, source)
  gl.compileShader(shader)

  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    const log = gl.getShaderInfoLog(shader) ?? 'Unknown shader compile error.'
    gl.deleteShader(shader)
    throw new Error(log)
  }

  return shader
}

function createProgram(
  gl: WebGLRenderingContext,
  vertexSource: string,
  fragmentSource: string,
): WebGLProgram {
  const vertexShader = createShader(gl, gl.VERTEX_SHADER, vertexSource)
  const fragmentShader = createShader(gl, gl.FRAGMENT_SHADER, fragmentSource)

  const program = gl.createProgram()
  if (!program) {
    gl.deleteShader(vertexShader)
    gl.deleteShader(fragmentShader)
    throw new Error('Failed to allocate WebGL program.')
  }

  gl.attachShader(program, vertexShader)
  gl.attachShader(program, fragmentShader)
  gl.linkProgram(program)

  gl.deleteShader(vertexShader)
  gl.deleteShader(fragmentShader)

  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    const log = gl.getProgramInfoLog(program) ?? 'Unknown program link error.'
    gl.deleteProgram(program)
    throw new Error(log)
  }

  return program
}

function buildCustomLayer(
  map: MapLibreMap,
  meshContext: NonNullable<ReturnType<typeof buildSurfaceMeshContext>>,
  frameValuesRef: MutableRefObject<ArrayLike<number>>,
  metricRef: MutableRefObject<InterpolationMetric>,
  colorModeRef: MutableRefObject<ColorMode>,
  relativeColorRangeRef: MutableRefObject<number | null>,
  anchorValueRef: MutableRefObject<number | null>,
  dirtyRef: MutableRefObject<boolean>,
  buffersRef: MutableRefObject<LayerBuffers | null>,
): CustomLayerInterface {
  const vertexShader = `
    attribute vec3 a_position;
    attribute vec4 a_color;
    attribute float a_contour_value;
    attribute float a_edge_distance;
    uniform mat4 u_matrix;
    varying vec4 v_color;
    varying float v_height;
    varying float v_contour_value;
    varying float v_edge_distance;

    void main() {
      gl_Position = u_matrix * vec4(a_position, 1.0);
      v_color = a_color;
      v_height = a_position.z;
      v_contour_value = a_contour_value;
      v_edge_distance = a_edge_distance;
    }
  `

  const fragmentShader = `
    precision mediump float;
    varying vec4 v_color;
    varying float v_height;
    varying float v_contour_value;
    varying float v_edge_distance;
    uniform vec4 u_contour_params;
    uniform vec3 u_contour_color_mod;

    void main() {
      // Height-based lighting: higher = brighter, lower = darker
      // Creates subtle relief effect for better surface readability at angles
      float heightFactor = 0.7 + 0.3 * clamp(v_height * 0.02, 0.0, 1.0);

      // Apply lighting to color channels
      vec3 lit = v_color.rgb * heightFactor;

      float contourMix = 0.0;
      if (u_contour_params.x > 0.5) {
        float interval = max(u_contour_params.y, 0.0001);
        float bandHalfWidth = clamp(u_contour_params.z, 0.0001, 0.49);
        float phase = fract(v_contour_value / interval);
        float distanceToLine = min(phase, 1.0 - phase);
        float lineMask = 1.0 - smoothstep(0.0, bandHalfWidth, distanceToLine);
        contourMix = lineMask * clamp(u_contour_params.w, 0.0, 1.0);
      }

      vec3 contoured = (lit * (1.0 - contourMix)) + (u_contour_color_mod * contourMix);
      
      // Edge fadeout for smooth boundaries
      float edgeFadeStart = 8.0;
      float edgeFadeEnd = 0.3;
      float edgeAlpha = smoothstep(edgeFadeEnd, edgeFadeStart, v_edge_distance);
      float finalAlpha = v_color.a * edgeAlpha;
      
      gl_FragColor = vec4(contoured, finalAlpha);
    }
  `

  return {
    id: SURFACE_LAYER_ID,
    type: 'custom',
    renderingMode: '3d',
    onAdd: (_map, gl) => {
      const program = createProgram(gl, vertexShader, fragmentShader)
      const positionLocation = gl.getAttribLocation(program, 'a_position')
      const colorLocation = gl.getAttribLocation(program, 'a_color')
      const contourValueLocation = gl.getAttribLocation(program, 'a_contour_value')
      const edgeDistanceLocation = gl.getAttribLocation(program, 'a_edge_distance')
      const matrixLocation = gl.getUniformLocation(program, 'u_matrix')
      const contourParamsLocation = gl.getUniformLocation(program, 'u_contour_params')
      const contourColorModLocation = gl.getUniformLocation(program, 'u_contour_color_mod')

      if (
        positionLocation < 0
        || colorLocation < 0
        || contourValueLocation < 0
        || edgeDistanceLocation < 0
        || !matrixLocation
        || !contourParamsLocation
        || !contourColorModLocation
      ) {
        throw new Error('Missing shader attribute locations for 3D surface layer.')
      }

      const positionBuffer = gl.createBuffer()
      const colorBuffer = gl.createBuffer()
      const contourValueBuffer = gl.createBuffer()
      const edgeDistanceBuffer = gl.createBuffer()
      const indexBuffer = gl.createBuffer()

      if (!positionBuffer || !colorBuffer || !contourValueBuffer || !edgeDistanceBuffer || !indexBuffer) {
        throw new Error('Failed to allocate WebGL buffers for 3D surface layer.')
      }

      const positions = new Float32Array(meshContext.basePositions)
      const targetPositions = new Float32Array(meshContext.basePositions)
      const colors = new Uint8Array(meshContext.basePositions.length / 3 * 4)
      const targetColors = new Uint8Array(meshContext.basePositions.length / 3 * 4)
      const contourValues = new Float32Array(meshContext.basePositions.length / 3)
      const targetContourValues = new Float32Array(meshContext.basePositions.length / 3)
      const edgeDistances = new Float32Array(meshContext.edgeDistances)

      const anchorValue = Number.isFinite(anchorValueRef.current)
        ? Number(anchorValueRef.current)
        : meshContext.dailyMinValue

      updateSurfacePositions(
        meshContext.basePositions,
        frameValuesRef.current,
        anchorValue,
        SURFACE_HEIGHT_SCALE * meshContext.meterToMercator,
        targetPositions,
      )

      positions.set(targetPositions)

      updateSurfaceColors(
        frameValuesRef.current,
        meshContext.dailyMinValue,
        meshContext.dailyMaxValue,
        metricRef.current,
        colorModeRef.current,
        relativeColorRangeRef.current,
        targetColors,
      )

      colors.set(targetColors)

      updateSurfaceNormalizedValues(
        frameValuesRef.current,
        meshContext.dailyMinValue,
        meshContext.dailyMaxValue,
        targetContourValues,
      )

      contourValues.set(targetContourValues)

      gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer)
      gl.bufferData(gl.ARRAY_BUFFER, positions, gl.DYNAMIC_DRAW)

      gl.bindBuffer(gl.ARRAY_BUFFER, colorBuffer)
      gl.bufferData(gl.ARRAY_BUFFER, colors, gl.DYNAMIC_DRAW)

      gl.bindBuffer(gl.ARRAY_BUFFER, contourValueBuffer)
      gl.bufferData(gl.ARRAY_BUFFER, contourValues, gl.DYNAMIC_DRAW)

      gl.bindBuffer(gl.ARRAY_BUFFER, edgeDistanceBuffer)
      gl.bufferData(gl.ARRAY_BUFFER, edgeDistances, gl.STATIC_DRAW)

      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, indexBuffer)
      gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, meshContext.indices, gl.STATIC_DRAW)

      buffersRef.current = {
        program,
        positionBuffer,
        colorBuffer,
        contourValueBuffer,
        edgeDistanceBuffer,
        indexBuffer,
        positionLocation,
        colorLocation,
        contourValueLocation,
        edgeDistanceLocation,
        matrixLocation,
        contourParamsLocation,
        contourColorModLocation,
        positions,
        targetPositions,
        colors,
        targetColors,
        contourValues,
        targetContourValues,
        edgeDistances,
        indexCount: meshContext.indices.length,
        hasPendingTransition: false,
      }

      dirtyRef.current = false
      map.triggerRepaint()
    },
    render: (gl, matrix) => {
      const buffers = buffersRef.current
      if (!buffers) {
        return
      }

      if (dirtyRef.current) {
        const anchorValue = Number.isFinite(anchorValueRef.current)
          ? Number(anchorValueRef.current)
          : meshContext.dailyMinValue

        updateSurfacePositions(
          meshContext.basePositions,
          frameValuesRef.current,
          anchorValue,
          SURFACE_HEIGHT_SCALE * meshContext.meterToMercator,
          buffers.targetPositions,
        )

        updateSurfaceColors(
          frameValuesRef.current,
          meshContext.dailyMinValue,
          meshContext.dailyMaxValue,
          metricRef.current,
          colorModeRef.current,
          relativeColorRangeRef.current,
          buffers.targetColors,
        )

        updateSurfaceNormalizedValues(
          frameValuesRef.current,
          meshContext.dailyMinValue,
          meshContext.dailyMaxValue,
          buffers.targetContourValues,
        )

        buffers.hasPendingTransition = true
        dirtyRef.current = false
      }

      if (buffers.hasPendingTransition) {
        const lerpFactor = 0.22
        let stillTransitioning = false

        for (let i = 0; i < buffers.positions.length; i += 1) {
          const current = buffers.positions[i]
          const target = buffers.targetPositions[i]
          const next = current + ((target - current) * lerpFactor)
          buffers.positions[i] = next
          if (Math.abs(target - next) > 0.00005) {
            stillTransitioning = true
          }
        }

        for (let i = 0; i < buffers.colors.length; i += 1) {
          const current = buffers.colors[i]
          const target = buffers.targetColors[i]
          const next = current + ((target - current) * lerpFactor)
          buffers.colors[i] = Math.round(next)
          if (Math.abs(target - next) > 1) {
            stillTransitioning = true
          }
        }

        for (let i = 0; i < buffers.contourValues.length; i += 1) {
          const current = buffers.contourValues[i]
          const target = buffers.targetContourValues[i]
          const next = current + ((target - current) * lerpFactor)
          buffers.contourValues[i] = next
          if (Math.abs(target - next) > 0.0005) {
            stillTransitioning = true
          }
        }

        gl.bindBuffer(gl.ARRAY_BUFFER, buffers.positionBuffer)
        gl.bufferSubData(gl.ARRAY_BUFFER, 0, buffers.positions)

        gl.bindBuffer(gl.ARRAY_BUFFER, buffers.colorBuffer)
        gl.bufferSubData(gl.ARRAY_BUFFER, 0, buffers.colors)

        gl.bindBuffer(gl.ARRAY_BUFFER, buffers.contourValueBuffer)
        gl.bufferSubData(gl.ARRAY_BUFFER, 0, buffers.contourValues)

        buffers.hasPendingTransition = stillTransitioning
        if (stillTransitioning) {
          map.triggerRepaint()
        }
      }

      gl.useProgram(buffers.program)
      gl.enable(gl.DEPTH_TEST)
      gl.enable(gl.BLEND)
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA)

      gl.bindBuffer(gl.ARRAY_BUFFER, buffers.positionBuffer)
      gl.enableVertexAttribArray(buffers.positionLocation)
      gl.vertexAttribPointer(buffers.positionLocation, 3, gl.FLOAT, false, 0, 0)

      gl.bindBuffer(gl.ARRAY_BUFFER, buffers.colorBuffer)
      gl.enableVertexAttribArray(buffers.colorLocation)
      gl.vertexAttribPointer(buffers.colorLocation, 4, gl.UNSIGNED_BYTE, true, 0, 0)

      gl.bindBuffer(gl.ARRAY_BUFFER, buffers.contourValueBuffer)
      gl.enableVertexAttribArray(buffers.contourValueLocation)
      gl.vertexAttribPointer(buffers.contourValueLocation, 1, gl.FLOAT, false, 0, 0)

      gl.bindBuffer(gl.ARRAY_BUFFER, buffers.edgeDistanceBuffer)
      gl.enableVertexAttribArray(buffers.edgeDistanceLocation)
      gl.vertexAttribPointer(buffers.edgeDistanceLocation, 1, gl.FLOAT, false, 0, 0)

      gl.uniform4f(
        buffers.contourParamsLocation,
        SURFACE_CONTOUR_CONFIG.enabled ? 1 : 0,
        SURFACE_CONTOUR_CONFIG.interval,
        SURFACE_CONTOUR_CONFIG.bandHalfWidth,
        SURFACE_CONTOUR_CONFIG.intensity,
      )
      gl.uniform3f(
        buffers.contourColorModLocation,
        SURFACE_CONTOUR_CONFIG.colorModulation[0],
        SURFACE_CONTOUR_CONFIG.colorModulation[1],
        SURFACE_CONTOUR_CONFIG.colorModulation[2],
      )

      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, buffers.indexBuffer)
      gl.uniformMatrix4fv(buffers.matrixLocation, false, matrix as Float32List)
      gl.drawElements(gl.TRIANGLES, buffers.indexCount, gl.UNSIGNED_SHORT, 0)
    },
    onRemove: (_map, gl) => {
      const buffers = buffersRef.current
      if (!buffers) {
        return
      }

      gl.deleteBuffer(buffers.positionBuffer)
      gl.deleteBuffer(buffers.colorBuffer)
      gl.deleteBuffer(buffers.contourValueBuffer)
      gl.deleteBuffer(buffers.edgeDistanceBuffer)
      gl.deleteBuffer(buffers.indexBuffer)
      gl.deleteProgram(buffers.program)
      buffersRef.current = null
    },
  }
}

export function Surface3DLayer({
  timeline,
  currentValues,
  metric,
  colorMode,
  relativeColorRange,
  heightAnchorValue,
  visible,
}: Surface3DLayerProps) {
  const mapCollection = useMap()
  const frameValuesRef = useRef<ArrayLike<number>>(currentValues)
  const metricRef = useRef(metric)
  const colorModeRef = useRef<ColorMode>(colorMode)
  const relativeColorRangeRef = useRef<number | null>(relativeColorRange)
  const anchorValueRef = useRef<number | null>(heightAnchorValue)
  const dirtyRef = useRef(true)
  const buffersRef = useRef<LayerBuffers | null>(null)

  const meshContext = useMemo(
    () =>
      buildSurfaceMeshContext(
        timeline.rows,
        timeline.cols,
        timeline.boundingBox,
        timeline.activeIndices,
        timeline.frames.map((frame) => frame.values),
      ),
    [timeline],
  )

  useEffect(() => {
    frameValuesRef.current = currentValues
    dirtyRef.current = true

    const map = mapCollection.current?.getMap()
    if (map && visible) {
      map.triggerRepaint()
    }
  }, [currentValues, mapCollection, visible])

  useEffect(() => {
    metricRef.current = metric
    dirtyRef.current = true

    const map = mapCollection.current?.getMap()
    if (map && visible) {
      map.triggerRepaint()
    }
  }, [metric, mapCollection, visible])

  useEffect(() => {
    colorModeRef.current = colorMode
    dirtyRef.current = true

    const map = mapCollection.current?.getMap()
    if (map && visible) {
      map.triggerRepaint()
    }
  }, [colorMode, mapCollection, visible])

  useEffect(() => {
    relativeColorRangeRef.current = relativeColorRange
    dirtyRef.current = true

    const map = mapCollection.current?.getMap()
    if (map && visible) {
      map.triggerRepaint()
    }
  }, [relativeColorRange, mapCollection, visible])

  useEffect(() => {
    anchorValueRef.current = heightAnchorValue
    dirtyRef.current = true

    const map = mapCollection.current?.getMap()
    if (map && visible) {
      map.triggerRepaint()
    }
  }, [heightAnchorValue, mapCollection, visible])

  useEffect(() => {
    const map = mapCollection.current?.getMap()
    if (!map) {
      return
    }

    const existingLayer = map.getLayer(SURFACE_LAYER_ID)

    if (!visible || !meshContext) {
      if (existingLayer) {
        map.removeLayer(SURFACE_LAYER_ID)
      }
      return
    }

    if (existingLayer) {
      map.removeLayer(SURFACE_LAYER_ID)
    }

    const customLayer = buildCustomLayer(
      map,
      meshContext,
      frameValuesRef,
      metricRef,
      colorModeRef,
      relativeColorRangeRef,
      anchorValueRef,
      dirtyRef,
      buffersRef,
    )

    map.addLayer(customLayer)
    map.triggerRepaint()

    return () => {
      if (map.getLayer(SURFACE_LAYER_ID)) {
        map.removeLayer(SURFACE_LAYER_ID)
      }
    }
  }, [mapCollection, meshContext, visible])

  return null
}
