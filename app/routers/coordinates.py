from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session
from app.models import Driver
from fastapi import APIRouter, HTTPException, Depends
from ..database import get_async_db
from sqlalchemy.ext.asyncio import AsyncSession
from ..utils.coordinate_schema import CoordinatesUpdateRequest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select




router = APIRouter()


@router.put("/coordinates/")
async def update_driver_coordinates(
    payload: CoordinatesUpdateRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Update the coordinates of drivers.

    Args:
        payload (CoordinatesUpdateRequest): Coordinates data from mobile apps.

    Returns:
        dict: Success message.
    """
    try:
        if not payload.driver_coordinates:
            raise HTTPException(
                status_code=400, detail="No driver coordinates provided in the request"
            )

        for driver_coord in payload.driver_coordinates:
            # Fetch the driver asynchronously
            result = await db.execute(select(Driver).filter(Driver.id == driver_coord.driver_id))
            driver = result.scalars().first()

            if not driver:
                raise HTTPException(
                    status_code=404, detail=f"Driver with ID {driver_coord.driver_id} not found"
                )

            # Update the driver's coordinates
            driver.latitude = driver_coord.latitude
            driver.longitude = driver_coord.longitude
            db.add(driver)  # Add changes to session

        # Commit changes to the database
        await db.commit()
        return {"message": "Driver coordinates updated successfully"}

    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")