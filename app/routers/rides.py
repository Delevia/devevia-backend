from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from ..database import get_async_db
from ..models import  Ride, Rating, Driver, Rider, PaymentMethod
from ..utils.rides_utility_functions import find_drivers_nearby, categorize_drivers_by_rating, update_driver_rating, tokenize_card
from ..enums import RideStatusEnum, PaymentMethodEnum
from ..utils.rides_schemas import RatingRequest, PaymentMethodRequest, RideRequest, ModifyRidePriceRequest, ModifyRideResponse
from sqlalchemy.ext.asyncio import AsyncSession
from ..utils.rides_utility_functions import calculate_estimated_price
from sqlalchemy.future import select
import traceback
from sqlalchemy import update
import logging  # Added logging for debugging




router = APIRouter()

# Ride Request Endpoint using RideRequest Schema
@router.post("/ride/request", status_code=status.HTTP_200_OK)
async def request_ride(
    request: RideRequest,  # Use the RideRequest schema as the request body
    rider_id: int,  # You can pass rider_id as part of the request or extract it from authentication token
    db: AsyncSession = Depends(get_async_db)
):
    # Validate the booking type and recipient phone number
    if request.booking_for == "other" and not request.recipient_phone_number:
        raise HTTPException(
            status_code=400,
            detail="Recipient phone number is required when booking for someone else."
        )

    # Ensure the rider exists in the `riders` table
    result = await db.execute(select(Rider).filter(Rider.id == rider_id))
    rider = result.scalars().first()
    if not rider:
        raise HTTPException(status_code=404, detail="Rider not found")

    # Calculate the estimated prices for both STANDARD and VIP rides
    try:
        standard_price = calculate_estimated_price(
            request.pickup_location, request.dropoff_location, ride_type="STANDARD"
        )
        logging.info(f"Calculated STANDARD price: {standard_price}")  # Logging for debug
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating STANDARD price: {e}")

    try:
        vip_price = calculate_estimated_price(
            request.pickup_location, request.dropoff_location, ride_type="VIP"
        )
        logging.info(f"Calculated VIP price: {vip_price}")  # Logging for debug
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating VIP price: {e}")

    # Store the ride as 'INITIATED' in the database
    new_ride = Ride(
        rider_id=rider_id,
        pickup_location=request.pickup_location,
        dropoff_location=request.dropoff_location,
        status=RideStatusEnum.INITIATED,  # Set status to INITIATED
        estimated_price=None,  # No price yet because the rider has not selected the ride type
        booking_for=request.booking_for,
        recipient_phone_number=request.recipient_phone_number if request.booking_for == "other" else None
    )

    try:
        async with db.begin_nested():  # Ensure transaction safety
            db.add(new_ride)
            await db.flush()  # Save the new ride in the database
            logging.info(f"New ride created with ID: {new_ride.id}")  # Log ride ID
            await db.commit()  # Commit the transaction

        await db.refresh(new_ride)  # Refresh to get the updated ride data

        # Log final ride details
        logging.info(f"Ride after commit: {new_ride}")

        # Return the ride options with estimated prices
        return {
            "message": "Ride options",
            "ride_id": new_ride.id,  # Return the ride ID for future references
            "estimated_prices": {
                "STANDARD": standard_price,  # Corrected typo
                "VIP": vip_price  # Corrected key name to uppercase
            }
        }
    except Exception as e:
        await db.rollback()  # Ensure the transaction is rolled back on error
        logging.error(f"An error occurred during ride request: {e}")  # Log error details
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")
    

# Select Ride Type
@router.post("/ride/select", status_code=status.HTTP_200_OK)
async def select_ride_type(
    rider_id: int,
    ride_type: str,  # Should be either 'VIP' or 'STANDARD'
    ride_id: int,     # Ride ID should be included in the request body
    db: AsyncSession = Depends(get_async_db)
):
    # Check if the ride type is valid
    if ride_type not in ["VIP", "STANDARD"]:
        raise HTTPException(status_code=400, detail="Invalid ride type. Must be 'VIP' or 'STANDARD'.")

    # Calculate estimated price based on the selected ride type
    estimated_price = 300 if ride_type == "VIP" else 200  # Static prices

    # Fetch the rider to ensure it exists
    result = await db.execute(select(Rider).filter(Rider.id == rider_id))
    rider = result.scalars().first()
    if not rider:
        raise HTTPException(status_code=404, detail="Rider not found.")

    # Fetch the ride by ride_id
    result = await db.execute(select(Ride).filter(Ride.id == ride_id))
    ride = result.scalars().first()

    # Check if the ride exists
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")

    # Update the ride with the selected ride type and estimated price
    ride.ride_type = ride_type
    ride.estimated_price = estimated_price

    # Commit the changes to the database
    await db.commit()
    await db.refresh(ride)

    # Assign a default driver (driver_id = 1) if needed

    return {
        "message": f"{ride_type} ride selected. Please confirm the ride.",
        "rider_id": rider_id,
        "ride_id": ride_id,
        "ride_type": ride_type,
        "estimated_price": estimated_price,
        "confirmation_required": True
    }


# Driver Accept Ride Endpoint
@router.post("/ride/accept/{ride_id}", status_code=status.HTTP_200_OK)
async def accept_ride(
    ride_id: int,
    driver_id: int,
    db: AsyncSession = Depends(get_async_db)
):
    try:
        # Retrieve the ride from the database
        ride = await db.get(Ride, ride_id)
        if not ride:
            raise HTTPException(status_code=404, detail="Ride not found")

        # Ensure the ride is in the PENDING status
        if ride.status != RideStatusEnum.PENDING:
            raise HTTPException(status_code=400, detail="Ride is not available for acceptance")

        # Ensure the driver exists in the database
        driver = await db.get(Driver, driver_id)
        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found")

        # Update the ride status to ACCEPTED and assign the driver
        ride.status = RideStatusEnum.ACCEPTED
        ride.driver_id = driver_id

        # Save the updated ride without explicit transaction handling
        db.add(ride)
        await db.commit()  # Commit the transaction to save changes
        await db.refresh(ride)  # Refresh the ride instance after committing

        return {
            "message": "Ride accepted successfully",
            "ride": {
                "ride_id": ride.id,
                "rider_id": ride.rider_id,
                "driver_id": ride.driver_id,
                "status": ride.status,
                "pickup_location": ride.pickup_location,
                "dropoff_location": ride.dropoff_location
            }
        }

    except Exception as e:
        # Rollback in case of an error
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")
    
 

# Confirm Ride Endpoint
@router.post("/ride/confirm", status_code=status.HTTP_200_OK)
async def confirm_ride(
    ride_id: int,
    rider_id: int,
    db: AsyncSession = Depends(get_async_db)
):
    ride = await db.get(Ride, ride_id)
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found.")
    
    if ride.rider_id != rider_id:
        raise HTTPException(status_code=403, detail="Unauthorized: You cannot confirm this ride.")
    
    try:
        payment_method_query = await db.execute(
            select(PaymentMethod).where(
                PaymentMethod.rider_id == rider_id,
                PaymentMethod.is_default == True
            )
        )
        payment_method = payment_method_query.scalar()
        
        if not payment_method:
            print(f"No default payment method found for rider ID: {rider_id}")
    
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"Error while fetching payment method: {error_details}")
        raise HTTPException(status_code=500, detail="An error occurred while fetching the payment method.")
    
    if not payment_method:
        raise HTTPException(
            status_code=400,
            detail="No payment method selected. Please add a payment method before confirming the ride."
        )

    ride.status = RideStatusEnum.PENDING
    
    try:
        db.add(ride)
        await db.commit()
        await db.refresh(ride)

        return {
            "message": "Ride confirmed and awaiting driver's acceptance.",
            "ride_id": ride.id,
            "status": ride.status,
            "payment_method": payment_method.payment_type
        }
    
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"Error during ride confirmation: {error_details}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"An error occurred while confirming the ride: {e}")



#Start Ride Endpoint
@router.post("/ride/start/{ride_id}", status_code=status.HTTP_200_OK)
async def start_ride(
    ride_id: int,
    driver_id: int,
    db: AsyncSession = Depends(get_async_db)
):
    try:
        # Retrieve the ride from the database
        ride = await db.get(Ride, ride_id)
        if not ride:
            raise HTTPException(status_code=404, detail="Ride not found")

        # Ensure the ride is in the ACCEPTED status before starting
        if ride.status != RideStatusEnum.ACCEPTED:
            raise HTTPException(status_code=400, detail="Ride is not in an acceptable state to start")

        # Ensure the driver trying to start the ride is assigned to the ride
        if ride.driver_id != driver_id:
            raise HTTPException(status_code=403, detail="You are not authorized to start this ride")

        # Update the ride status to ONGOING
        ride.status = RideStatusEnum.ONGOING

        # Save the updated ride status
        db.add(ride)
        await db.commit()  # Commit the transaction to save changes
        await db.refresh(ride)  # Refresh the ride instance after committing

        return {
            "message": "Ride started successfully",
            "ride": {
                "ride_id": ride.id,
                "rider_id": ride.rider_id,
                "driver_id": ride.driver_id,
                "status": ride.status,
                "pickup_location": ride.pickup_location,
                "dropoff_location": ride.dropoff_location
            }
        }

    except Exception as e:
        # Rollback in case of an error
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")


# Complete Ride Endpoint
@router.post("/ride/complete/{ride_id}", status_code=status.HTTP_200_OK)
async def complete_ride(
    ride_id: int,
    driver_id: int,
    db: AsyncSession = Depends(get_async_db)
):
    try:
        # Retrieve the ride from the database
        ride = await db.get(Ride, ride_id)
        if not ride:
            raise HTTPException(status_code=404, detail="Ride not found")

        # Ensure the ride is in the ONGOING status before completing
        if ride.status != RideStatusEnum.ONGOING:
            raise HTTPException(status_code=400, detail="Ride is not currently ongoing and cannot be completed")

        # Ensure the driver completing the ride is the one assigned to the ride
        if ride.driver_id != driver_id:
            raise HTTPException(status_code=403, detail="You are not authorized to complete this ride")

        # Update the ride status to COMPLETED
        ride.status = RideStatusEnum.COMPLETED

        # Save the updated ride status
        db.add(ride)
        await db.commit()  # Commit the transaction to save changes
        await db.refresh(ride)  # Refresh the ride instance after committing

        return {
            "message": "Ride completed successfully",
            "ride": {
                "ride_id": ride.id,
                "rider_id": ride.rider_id,
                "driver_id": ride.driver_id,
                "status": ride.status,
                "pickup_location": ride.pickup_location,
                "dropoff_location": ride.dropoff_location,
                "fare": ride.fare  # Assuming the fare is already calculated and stored
            }
        }

    except Exception as e:
        # Rollback in case of an error
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")



# Cancel Ride Endpoint
@router.post("/ride/cancel/{ride_id}", status_code=status.HTTP_200_OK)
async def cancel_ride(
    ride_id: int,
    user_id: int,  # Can be either rider or driver ID based on the logic
    db: AsyncSession = Depends(get_async_db)
):
    try:
        # Retrieve the ride from the database
        ride = await db.get(Ride, ride_id)
        if not ride:
            raise HTTPException(status_code=404, detail="Ride not found")

        # Check if the ride is already completed or ongoing, as they cannot be canceled
        if ride.status in [RideStatusEnum.COMPLETED, RideStatusEnum.ONGOING]:
            raise HTTPException(status_code=400, detail="Ride cannot be canceled after it has started or been completed")

        # Check if the user is authorized to cancel the ride (either the rider or the assigned driver)
        if ride.rider_id != user_id and ride.driver_id != user_id:
            raise HTTPException(status_code=403, detail="You are not authorized to cancel this ride")

        # Update the ride status to REJECTED (indicating it was canceled)
        ride.status = RideStatusEnum.REJECTED

        # Save the updated ride status
        db.add(ride)
        await db.commit()  # Commit the transaction to save changes
        await db.refresh(ride)  # Refresh the ride instance after committing

        return {
            "message": "Ride canceled successfully",
            "ride": {
                "ride_id": ride.id,
                "rider_id": ride.rider_id,
                "driver_id": ride.driver_id,
                "status": ride.status,
                "pickup_location": ride.pickup_location,
                "dropoff_location": ride.dropoff_location
            }
        }

    except Exception as e:
        # Rollback in case of an error
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")


# Endpoint to submit a rating for a driver
@router.post("/ride/{ride_id}/rate_driver", status_code=status.HTTP_201_CREATED)
async def rate_driver(ride_id: int, rating_data: RatingRequest, db: Session = Depends(get_async_db
)):
    # Check if the ride exists
    ride = db.query(Ride).filter(Ride.id == ride_id).first()
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    
    # Check if the driver exists
    driver = db.query(Driver).filter(Driver.id == rating_data.driver_id).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    
    # Create the new rating
    new_rating = Rating(
        ride_id=ride_id,
        driver_id=rating_data.driver_id,
        rating=rating_data.rating,
        comment=rating_data.comment
    )
    db.add(new_rating)
    
    # Update the driver's overall rating
    update_driver_rating(driver, rating_data.rating, db)
    
    db.commit()
    
    return {"message": "Driver rated successfully"}


# Display Driver Rating Optional
@router.get("/driver/{driver_id}/profile", status_code=status.HTTP_200_OK)
async def get_driver_profile(driver_id: int, db: Session = Depends(get_async_db)):
    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    
    return {
        "driver_name": driver.name,
        "overall_rating": driver.overall_rating,
        "num_of_ratings": driver.num_of_ratings
    }

# Select Payment Method
@router.post("/riders/{rider_id}/payment-method", status_code=status.HTTP_201_CREATED)
async def create_payment_method(
    rider_id: int,
    request: PaymentMethodRequest,
    db: AsyncSession = Depends(get_async_db)
):
    # Query the Rider from the database
    rider = await db.get(Rider, rider_id)
    if not rider:
        raise HTTPException(status_code=404, detail="Rider not found")

    # Check if the rider already has a payment method
    existing_payment_method = await db.execute(
        select(PaymentMethod).where(PaymentMethod.rider_id == rider_id)
    )
    existing_payment_method = existing_payment_method.scalars().first()

    if existing_payment_method:
        raise HTTPException(
            status_code=400, 
            detail="Rider has already created a payment method"
        )

    # Handle card details based on selected payment method
    if request.payment_method in { PaymentMethodEnum.DEBIT_CARD }:
        if not request.card_number or not request.expiry_date or not request.token:
            raise HTTPException(status_code=400, detail="Card details are required for card payment methods")

        # Create a new payment method with card details
        new_payment_method = PaymentMethod(
            rider_id=rider.id,  # Use rider_id instead of user_id
            payment_type=request.payment_method,
            card_number=request.card_number,
            expiry_date=request.expiry_date,
            token=request.token,
            is_default=True  # Always set the new payment method as default
        )
    else:
        # Create a new payment method for cash or wallet without card details
        new_payment_method = PaymentMethod(
            rider_id=rider.id,  # Use rider_id instead of user_id
            payment_type=request.payment_method,
            is_default=True  # Always set the new payment method as default
        )

    # Set all other payment methods for the rider to is_default=False
    await db.execute(
        update(PaymentMethod)
        .where(PaymentMethod.rider_id == rider.id)  # Use rider_id here as well
        .values(is_default=False)
    )

    # Add the new payment method to the session and commit
    db.add(new_payment_method)
    await db.commit()
    await db.refresh(new_payment_method)

    return {
        "message": "Payment method created and set as default successfully",
        "payment_method_id": new_payment_method.id,
        "payment_type": new_payment_method.payment_type,
        "is_default": new_payment_method.is_default
    }



# Update Payment Method
@router.put("/riders/{rider_id}/payment-method/{payment_method_id}", status_code=status.HTTP_200_OK)
async def update_payment_method(
    rider_id: int,
    payment_method_id: int,
    request: PaymentMethodRequest,
    db: AsyncSession = Depends(get_async_db)
):
    # Query the Rider and Payment Method from the database
    rider = await db.get(Rider, rider_id)
    if not rider:
        raise HTTPException(status_code=404, detail="Rider not found")

    payment_method = await db.get(PaymentMethod, payment_method_id)
    if not payment_method:
        raise HTTPException(status_code=404, detail="Payment method not found")

    # Tokenize the card if it's a card-based payment
    tokenized_card = None
    if request.payment_method in { PaymentMethodEnum.DEBIT_CARD }:
        tokenized_card = tokenize_card(request.card_number)

    # Update the PaymentMethod instance
    if request.payment_method in { PaymentMethodEnum.DEBIT_CARD }:
        payment_method.payment_type = request.payment_method
        payment_method.card_number = tokenized_card
        payment_method.expiry_date = request.expiry_date
        payment_method.token = tokenized_card
    else:
        # For non-card payments, remove card-related fields
        payment_method.payment_type = request.payment_method
        payment_method.card_number = None
        payment_method.expiry_date = None
        payment_method.token = None

    # Set the updated payment method to default if requested
    if request.is_default:
        # Set all other payment methods for the user to is_default=False
        await db.execute(
            update(PaymentMethod)
            .where(PaymentMethod.rider_id == rider.user_id)
            .values(is_default=False)
        )
    
    # Set the current payment method's is_default status
    payment_method.is_default = request.is_default

    # Commit the changes to the database
    await db.commit()
    await db.refresh(payment_method)

    return {
        "message": "Payment method updated successfully",
        "payment_method": {
            "id": payment_method.id,
            "payment_type": payment_method.payment_type,
            "is_default": payment_method.is_default
        }
    }


# Modify Ride Price
@router.put("/rides/{ride_id}/modify_price", response_model=ModifyRideResponse)
def modify_ride_price(
    ride_id: int, 
    request: ModifyRidePriceRequest,
    rider_id: int,  # Rider ID passed as part of the request
    db: Session = Depends(get_async_db)
):
    # Fetch the ride by ride_id
    ride = db.query(Ride).filter(Ride.id == ride_id).first()
    
    # Check if the ride exists
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    
    # Ensure that the rider ID matches the one associated with the ride
    if ride.rider_id != rider_id:
        raise HTTPException(status_code=403, detail="Unauthorized to modify this ride")
    
    # Ensure the ride is in the PENDING state
    if ride.status != RideStatusEnum.PENDING:
        raise HTTPException(status_code=400, detail="Cannot modify price for non-pending rides")
    
    # Check if the new price is greater than the initial price
    if request.new_price <= ride.estimated_price:
        raise HTTPException(status_code=400, detail="New price must be greater than the current estimated price")
    
    # Update the price
    ride.estimated_price = request.new_price  # Use the new price from the request
    
    # Commit the changes
    db.commit()
    db.refresh(ride)
    
    return ride