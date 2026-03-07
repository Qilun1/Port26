from fastapi import APIRouter, Depends, HTTPException, status

from config import get_settings
from schemas import SensorListResponse
from services import SensorService

router = APIRouter(prefix="/sensors", tags=["sensors"])


def get_sensor_service() -> SensorService:
    return SensorService(get_settings())


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
