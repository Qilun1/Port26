/**
 * Demo risk zone overlays for showcasing automatic detection features
 * 
 * These zones are hardcoded for demonstration purposes:
 * - AQI: Air pollution risk zones (purple outline)
 * - Temperature: Urban heat islands (red outline)
 */

import type { FeatureCollection, Polygon } from 'geojson';

/**
 * Air pollution risk zone near Mannerheimintie
 * Elongated NE-SE direction, ~500m length
 */
export const AQI_RISK_ZONE: FeatureCollection<Polygon> = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      properties: {
        name: 'Air Pollution Risk Zone',
        riskLevel: 'Moderate',
      },
      geometry: {
        type: 'Polygon',
        coordinates: [
          [
            [24.91618682517142, 60.18626707275491], // SW corner
            [24.91618682517142, 60.18796707275491], // NW corner
            [24.91918682517142, 60.18916707275491], // N corner
            [24.92018682517142, 60.18796707275491], // NE corner
            [24.92018682517142, 60.18626707275491], // SE corner
            [24.91618682517142, 60.18626707275491], // Close the polygon
          ],
        ],
      },
    },
  ],
};

/**
 * Urban heat island zone in residential area
 * Elongated NE-SE direction, ~500m length
 */
export const TEMPERATURE_HEAT_ISLAND: FeatureCollection<Polygon> = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      properties: {
        name: 'Urban Heat Island',
        riskLevel: 'High',
      },
      geometry: {
        type: 'Polygon',
        coordinates: [
          [
            [24.93436211531028, 60.16428517516771], // SW corner
            [24.93436211531028, 60.16598517516771], // NW corner
            [24.93736211531028, 60.16718517516771], // N corner
            [24.93836211531028, 60.16598517516771], // NE corner
            [24.93836211531028, 60.16428517516771], // SE corner
            [24.93436211531028, 60.16428517516771], // Close the polygon
          ],
        ],
      },
    },
  ],
}
