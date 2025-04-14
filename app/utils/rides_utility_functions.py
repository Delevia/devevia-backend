from sqlalchemy.orm import Session
from ..models import Driver, Ride
from geopy.distance import geodesic  # Library for calculating distance between two points (latitude, longitude)
from typing import List, Dict
import requests
from ..enums import RideStatusEnum
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
import math
from app.utils.connection_manager import driver_connection_manager
from app.utils.rides_schemas import RideResponse
from math import radians, cos, sin, asin, sqrt
from sqlalchemy.sql import text
import json
import logging

# connection_manager.py

logging.basicConfig(level=logging.INFO)

# active_drivers = {}

MAX_SEARCH_RADIUS = 10  

# WebSocket system to send notifications:
# async def send_websocket_notification(driver_id, data):
#     if driver_id in active_drivers:
#         await active_drivers[driver_id].send_text(json.dumps(data))


# Function to calculate the distance between two locations (rider and driver)
def calculate_distance(rider_location: tuple, driver_location: tuple) -> float:
    return geodesic(rider_location, driver_location).kilometers


# Function to categorize drivers by rating
def categorize_drivers_by_rating(nearby_drivers: List[Driver]) -> Dict[str, List[Driver]]:
    group_1 = [driver for driver in nearby_drivers if 100 >= driver.rating >= 70]
    group_2 = [driver for driver in nearby_drivers if 69 >= driver.rating >= 40]
    group_3 = [driver for driver in nearby_drivers if driver.rating < 40]
    
    return {"group_1": group_1, "group_2": group_2, "group_3": group_3}


def get_distance_matrix(pickup_location, driver_location, api_key):
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": f"{pickup_location[0]},{pickup_location[1]}",
        "destinations": f"{driver_location[0]},{driver_location[1]}",
        "key": api_key
    }
    response = requests.get(url, params=params)
    data = response.json()

    if data["rows"]:
        distance_info = data["rows"][0]["elements"][0]
        distance_km = distance_info["distance"]["value"] / 1000
        return distance_km
    return None


# Function to update the driver's overall rating
def update_driver_rating(driver: Driver, new_rating: float, db: Session):
    if driver.num_of_ratings == 0:
        # First rating
        driver.overall_rating = new_rating
        driver.num_of_ratings = 1
    else:
        # Calculate new average rating
        total_rating = driver.overall_rating * driver.num_of_ratings
        total_rating += new_rating
        driver.num_of_ratings += 1
        driver.overall_rating = total_rating / driver.num_of_ratings

    db.commit()


def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great-circle distance between two points on Earth using the Haversine formula.
    Returns distance in kilometers.
    """
    R = 6371  # Radius of the Earth in kilometers

    # Convert latitude and longitude from degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = R * c  # Distance in kilometers
    return distance


#Function to calculate  
def calculate_estimated_price(pickup_location, dropoff_location, ride_type):
    """
    Calculate ride cost based on actual distance between pickup and dropoff coordinates.
    """
    # Extract coordinates
    lat1, lon1 = pickup_location.latitude, pickup_location.longitude
    lat2, lon2 = dropoff_location.latitude, dropoff_location.longitude

    # Calculate distance (in km)
    distance_km = haversine_distance(lat1, lon1, lat2, lon2)

    # Pricing per km
    base_fare = 500  # Flat base fare for short trips
    standard_rate_per_km = 200  # Cost per km for STANDARD
    vip_rate_per_km = 300  # Cost per km for VIP

    # Calculate price based on ride type
    if ride_type == "STANDARD":
        estimated_price = base_fare + (standard_rate_per_km * distance_km)
    elif ride_type == "VIP":
        estimated_price = base_fare + (vip_rate_per_km * distance_km)
    else:
        raise ValueError("Invalid ride type")

    return round(estimated_price, 2)  # Round to 2 decimal places

    

#Tokenize Card
def tokenize_card(card_number: str) -> str:
    # Tokenization logic, here we just mock it by returning the last four digits
    return f"**** **** **** {card_number[-4:]}"



# --- Helper to filter rides by proximity ---
async def get_rides_within_radius(db: AsyncSession, driver_location: tuple, radius_km: float = 10.0):
    pending_rides_query = await db.execute(
        select(Ride).filter(Ride.status == RideStatusEnum.PENDING)
    )
    pending_rides = pending_rides_query.scalars().all()

    nearby_rides = []
    for ride in pending_rides:
        pickup_coords = (ride.pickup_latitude, ride.pickup_longitude)
        distance = geodesic(driver_location, pickup_coords).km
        if distance <= radius_km:
            nearby_rides.append({
                "id": ride.id,
                "pickup_location": ride.pickup_location,
                "dropoff_location": ride.dropoff_location,
                "estimated_price": ride.estimated_price,
                "pickup_lat": ride.pickup_latitude,
                "pickup_lng": ride.pickup_longitude,
                "distance_km": round(distance, 2)
            })

    return nearby_rides




def get_rides_within_radius(rides, driver_latitude, driver_longitude, radius_km=10):
    def haversine(lat1, lon1, lat2, lon2):
        R = 6371  # Earth radius in kilometers
        d_lat = math.radians(lat2 - lat1)
        d_lon = math.radians(lon2 - lon1)
        a = (math.sin(d_lat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(d_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c  # Distance in km

    nearby_rides = []
    for ride in rides:
        pickup = Ride.pickup_location
        # Assuming pickup_location is a tuple of (latitude, longitude)
        ride_distance = haversine(driver_latitude, driver_longitude, pickup[0], pickup[1])
        if ride_distance <= radius_km:
            nearby_rides.append(ride)
    return nearby_rides



# Haversine distance helper
def haversine(lat1, lon1, lat2, lon2):
    # convert decimal degrees to radians 
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    # haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 6371  
    return c * r





# async def notify_ride_taken(ride_id: int):
#     await driver_connection_manager.broadcast({
#         "event": "RIDE_TAKEN",
#         "ride_id": ride_id
#     })  



def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371  # Earth's radius in km
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c



# Find nearby Drivers
async def find_nearby_drivers(pickup_lat: float, pickup_lon: float, db: AsyncSession) -> List[Driver]:
    """Find nearby drivers who are online and presumed to be connected via WebSocket."""
    
    logging.info(f"🔍 Looking for drivers near ({pickup_lat}, {pickup_lon})...")

    result = await db.execute(
        select(Driver.id, Driver.latitude, Driver.longitude).where(Driver.is_online == True)
    )
    online_drivers = result.fetchall()

    logging.info(f"📡 Found {len(online_drivers)} online drivers.")
    nearby_drivers = []

    for driver_data in online_drivers:
        driver_id, latitude, longitude = driver_data
        logging.info(f"🚖 Checking Driver {driver_id}...")

        # Since the driver is marked as online, assume they are connected to WebSocket
        # No need to check WebSocket connection anymore

        # Validate coordinates
        if latitude is None or longitude is None:
            logging.warning(f"❌ Driver {driver_id} has no valid location data.")
            continue

        # Calculate distance
        distance = haversine(pickup_lat, pickup_lon, latitude, longitude)
        logging.info(f"📏 Driver {driver_id} is {distance:.2f} km away.")

        if distance <= MAX_SEARCH_RADIUS:
            logging.info(f"✅ Driver {driver_id} is within range.")
            nearby_drivers.append(driver_id)  # Collect only driver ID here
        else:
            logging.info(f"❌ Driver {driver_id} is too far.")

    logging.info(f"✅ {len(nearby_drivers)} drivers are nearby and connected.")
    return nearby_drivers


async def notify_new_ride(ride: Ride, db: AsyncSession):
    """Notify nearby drivers of a new ride request."""
    nearby_drivers = await find_nearby_drivers(ride.pickup_latitude, ride.pickup_longitude, db)
    logging.info(f"📡 Nearby Drivers to notify: {nearby_drivers}")
    logging.info(f"🔌 Active WebSocket connections: {list(driver_connection_manager.active_connections.keys())}")

    # Prepare the ride request message
    ride_message = {
        "event": "new_ride_request",
        "ride_id": ride.id,
        "pickup": {"lat": ride.pickup_latitude, "lng": ride.pickup_longitude},
        "dropoff": {"lat": ride.dropoff_latitude, "lng": ride.dropoff_longitude}
    }

    # Iterate over all active WebSocket connections
    for driver_id, websocket in driver_connection_manager.active_connections.items():
        # Check if the driver is online and nearby
        if driver_id in nearby_drivers:
            result = await db.execute(select(Driver).where(Driver.id == driver_id))
            driver = result.scalar()

            if driver and driver.is_online:
                try:
                    # Send the ride request notification to the connected driver
                    await websocket.send_json(ride_message)
                    logging.info(f"📣 Sent ride request to Driver {driver_id}")
                except Exception as e:
                    logging.warning(f"⚠️ Failed to notify Driver {driver_id}: {e}")
            else:
                logging.warning(f"🚫 Driver {driver_id} is either offline or not eligible.")
        else:
            logging.warning(f"❌ Driver {driver_id} is not in the nearby drivers list.")

