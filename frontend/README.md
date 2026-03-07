# Helsinki Weather Sensor Map MVP (Frontend)

Frontend-only MVP for visualizing a mock dense weather sensor network in the Helsinki region.

## Stack

- React + TypeScript + Vite
- MapLibre GL JS
- `react-map-gl` (MapLibre integration)

## Run

```bash
cd frontend
npm install
npm run dev
```

Production build:

```bash
npm run build
npm run preview
```

## Project Structure

```text
src/
  app/
    App.tsx
    providers/
      AppProviders.tsx
  components/
    map/
      MapView.tsx
      SensorLayer.tsx
      SensorMarker.tsx
      SensorTooltip.tsx
  features/
    sensors/
      api/
        sensorsApi.ts
      model/
        sensor.ts
        weatherReading.ts
      data/
        mockSensors.ts
        mockReadings.ts
      hooks/
        useSensorWeather.ts
      utils/
        sensorFormatters.ts
  lib/
    map/
      mapConfig.ts
    theme/
      theme.ts
    utils/
      format.ts
  styles/
    globals.css
  main.tsx
```

## Where To Add Sensors

Add new sensors in:

- `src/features/sensors/data/mockSensors.ts`

Each sensor uses:

- `id`
- `name`
- `latitude`
- `longitude`

## Mock API Layer (Replace Later)

Current local API abstraction lives in:

- `src/features/sensors/api/sensorsApi.ts`

It exposes:

- `listSensors()`
- `getCurrentWeatherBySensorId(sensorId)`

To switch to real endpoints later, replace the internals of those functions with `fetch`/HTTP calls while keeping the same signatures to avoid touching map components.
