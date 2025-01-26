from fastapi import FastAPI, HTTPException
from ..utils.pushNotification_schema import NotificationRequest, DriverCoordinateRequest
from ..utils.push_notifcation import send_push_notification
from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_async_db
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.models import DriverLocation  # Assuming a DriverLocation model is defined in models
router = APIRouter()


@router.post("/send-notification/")
async def send_notification(notification: NotificationRequest):
    """
    Endpoint to send a push notification using external IDs or a segment.

    Args:
        notification (NotificationRequest): Notification data.

    Returns:
        dict: Status of the push notification.
    """
    try:
        # Ensure at least one targeting option is provided
        if not notification.external_ids and not notification.segment:
            raise HTTPException(
                status_code=400, 
                detail="Either 'external_ids' or 'segment' must be provided to send a notification."
            )

        # Call the utility function to send the notification
        response = await send_push_notification(
            title=notification.title,
            message=notification.message,
            external_ids=notification.external_ids,  # Use the correct key
            segment=notification.segment  # Optional segment
        )

        return {"message": "Notification sent successfully", "response": response}

    except HTTPException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

    except Exception as e:
        # General exception handler for unexpected errors
        raise HTTPException(status_code=500, detail=str(e))



@router.put("/drivers/{driver_id}/coordinates")
async def update_driver_coordinates(
    driver_id: int,
    coordinates: DriverCoordinateRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Update a driver's current coordinates.

    Args:
        driver_id (int): The ID of the driver.
        coordinates (DriverCoordinateRequest): The latitude and longitude of the driver.
        db (Session): Database session.

    Returns:
        dict: A success message with updated coordinates.
    """
    try:
        # Check if driver exists in the database
        driver_location = db.query(DriverLocation).filter(DriverLocation.driver_id == driver_id).first()
        if not driver_location:
            raise HTTPException(status_code=404, detail="Driver not found")

        # Update driver coordinates
        driver_location.latitude = coordinates.latitude
        driver_location.longitude = coordinates.longitude
        db.commit()

        return {"message": "Driver coordinates updated successfully", "data": coordinates.dict()}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/drivers/{driver_id}/coordinates")
async def get_driver_coordinates(driver_id: int, db: AsyncSession = Depends(get_async_db),):
    """
    Get a driver's current coordinates.

    Args:
        driver_id (int): The ID of the driver.
        db (Session): Database session.

    Returns:
        dict: Driver's coordinates if found.
    """
    try:
        # Retrieve driver coordinates from the database
        driver_location = db.query(DriverLocation).filter(DriverLocation.driver_id == driver_id).first()
        if not driver_location:
            raise HTTPException(status_code=404, detail="Driver not found")

        return {
            "driver_id": driver_location.driver_id,
            "latitude": driver_location.latitude,
            "longitude": driver_location.longitude,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
