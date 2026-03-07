from fastapi import APIRouter, Depends, HTTPException, status

from config import get_settings
from schemas import SensorHistoryReadingItem, SensorHistoryResponse, SensorListResponse
from services import SensorReadingsService, SensorService

router = APIRouter(prefix="/sensors", tags=["sensors"])


def get_sensor_service() -> SensorService:
    return SensorService(get_settings())


def get_sensor_readings_service() -> SensorReadingsService:
    return SensorReadingsService(get_settings())


@router.get("", response_model=SensorListResponse)
def list_sensors(service: SensorService = Depends(get_sensor_service)) -> SensorListResponse:
    try:
        sensors = service.list_sensors()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not fetch sensors from data source.",
        ) from exc

    return SensorListResponse(sensors=sensors, count=len(sensors))


@router.get("/{sensor_id}/readings", response_model=SensorHistoryResponse)
def get_sensor_history_by_id(
    sensor_id: int,
    sensor_service: SensorService = Depends(get_sensor_service),
    readings_service: SensorReadingsService = Depends(get_sensor_readings_service),
) -> SensorHistoryResponse:
    try:
        sensors = sensor_service.list_sensors()
        if not any(sensor.id == sensor_id for sensor in sensors):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sensor was not found.",
            )

        readings = readings_service.list_sensor_readings_by_sensor_id(sensor_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not fetch sensor history from data source.",
        ) from exc

    items = [
        SensorHistoryReadingItem(
            timestamp=str(row["timestamp"]),
            aqi=row.get("aqi"),
            temperature=row.get("temperature"),
        )
        for row in readings
    ]

    return SensorHistoryResponse(sensor_id=sensor_id, readings=items, count=len(items))
