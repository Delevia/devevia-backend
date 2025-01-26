from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session
from app.models import Driver
from fastapi import APIRouter, HTTPException, Depends
from ..database import get_async_db
from sqlalchemy.ext.asyncio import AsyncSession
from ..utils.coordinate_schema import CoordinatesUpdateRequest




router = APIRouter()


@router.post("/coordinates/")
async def update_driver_coordinates(
    payload: CoordinatesUpdateRequest,
    db: AsyncSession = Depends(get_async_db)):
    """
    Update the coordinates of drivers.

    Args:
        payload (CoordinatesUpdateRequest): Coordinates data from mobile apps.

    Returns:
        dict: Success message.
    """
    try:
        # Update driver coordinates if provided
        if payload.driver_coordinates:
            for driver_coord in payload.driver_coordinates:
                # Fetch the driver by ID
                driver = db.query(Driver).filter(Driver.id == driver_coord.driver_id).first()
                if not driver:
                    raise HTTPException(
                        status_code=404, detail=f"Driver with ID {driver_coord.driver_id} not found"
                    )
                
                # Update the driver's coordinates
                driver.latitude = driver_coord.latitude
                driver.longitude = driver_coord.longitude
                db.add(driver)

            # Commit changes to the database
            db.commit()
            return {"message": "Driver coordinates updated successfully"}
        else:
            raise HTTPException(
                status_code=400, detail="No driver coordinates provided in the request"
            )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
