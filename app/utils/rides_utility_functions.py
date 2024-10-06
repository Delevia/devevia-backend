from sqlalchemy.orm import Session
from ..models import Driver
from geopy.distance import geodesic  # Library for calculating distance between two points (latitude, longitude)
from typing import List, Dict
import requests


# Function to calculate the distance between two locations (rider and driver)
def calculate_distance(rider_location: tuple, driver_location: tuple) -> float:
    return geodesic(rider_location, driver_location).kilometers

# Function to find drivers nearby the rider's location
def find_drivers_nearby(rider_location: tuple, db: Session, max_distance: float = 10.0) -> List[Driver]:
    # Get all available drivers
    available_drivers = db.query(Driver).filter(Driver.is_available == True).all()

    # Filter drivers based on proximity (example: within 10 km radius)
    nearby_drivers = []
    for driver in available_drivers:
        driver_location = (driver.latitude, driver.longitude)
        distance = calculate_distance(rider_location, driver_location)
        if distance <= max_distance:
            nearby_drivers.append(driver)

    return nearby_drivers


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


#Function to calculate  
def calculate_estimated_price(pickup_location: str, dropoff_location: str, ride_type: str):
    # Dummy function to calculate price based on location and ride type
    # You can implement actual distance-based calculation here
    if ride_type == "REGULAR":
        return 200  # Static regular price
    elif ride_type == "VIP":
        return 300  # Static VIP price
    

#Tokenize Card
def tokenize_card(card_number: str) -> str:
    # Tokenization logic, here we just mock it by returning the last four digits
    return f"**** **** **** {card_number[-4:]}"

