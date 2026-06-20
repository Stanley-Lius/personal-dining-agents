import os
from dotenv import load_dotenv
load_dotenv(override=True)
import googlemaps
from typing import Dict, Any, List, Optional
import time

# --- Cache to save API Costs ---
# We use simple in-memory dictionaries to cache identical queries during a single agent session.
# Keys are tuples of function arguments, Values are API responses.
PLACES_CACHE: Dict[str, List[Dict[str, Any]]] = {}
DISTANCE_CACHE: Dict[str, Dict[str, Any]] = {}

def get_gmaps_client() -> googlemaps.Client:
    """Initialize the Google Maps client from environment variable."""
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_MAPS_API_KEY environment variable is not set.")
    # googlemaps library handles rate limiting and retries automatically
    return googlemaps.Client(key=api_key)

def search_nearby_restaurants(location: str, keyword: str, radius_meters: int = 5000, open_now: bool = True) -> List[Dict[str, Any]]:
    """
    Search for restaurants using Google Maps Places API based on specific constraints.
    
    Args:
        location (str): The latitude/longitude or address string.
        keyword (str): Search term (e.g., 'BBQ', 'Japanese', 'Vegetarian').
        radius_meters (int): Search radius in meters. Default is 5000.
        open_now (bool): Whether to only return places that are currently open. Default is True.
        
    Returns:
        A list of dictionaries containing restaurant details (name, address, rating, price_level, place_id).
    """
    cache_key = f"{location}_{keyword}_{radius_meters}_{open_now}"
    if cache_key in PLACES_CACHE:
        print(f"[CACHE HIT] Returning cached results for '{keyword}' near '{location}'.")
        return PLACES_CACHE[cache_key]

    print(f"[API CALL] Fetching nearby restaurants for '{keyword}' near '{location}'...")
    gmaps = get_gmaps_client()
    
    # We use places() for text search which is often more flexible than places_nearby() for specific concepts like 'Japanese BBQ'
    # We pass the location and radius to bias the results
    try:
        response = gmaps.places(
            query=keyword,
            location=location,
            radius=radius_meters,
            open_now=open_now,
            type="restaurant"
        )
        
        results = []
        for place in response.get("results", [])[:5]: # Return top 5 matches
            results.append({
                "place_id": place.get("place_id"),
                "name": place.get("name"),
                "address": place.get("formatted_address"),
                "rating": place.get("rating", "N/A"),
                "price_level": place.get("price_level", "N/A"), # 0-4 scale
                "types": place.get("types", [])
            })
            
        PLACES_CACHE[cache_key] = results
        return results
    except Exception as e:
        print(f"Error fetching places: {e}")
        return []

def get_route_duration(origin: str, destination: str, mode: str = "driving") -> Optional[Dict[str, Any]]:
    """
    Calculate the travel time and distance between an origin and destination.
    
    Args:
        origin (str): Starting location (lat/lng or address).
        destination (str): Target restaurant location or place_id.
        mode (str): Travel mode (driving, walking, bicycling, transit). Default is 'driving'.
        
    Returns:
        Dictionary with 'distance_text', 'duration_text', 'duration_value_seconds', or None if failed.
    """
    cache_key = f"{origin}_{destination}_{mode}"
    if cache_key in DISTANCE_CACHE:
        print(f"[CACHE HIT] Returning cached route from '{origin}' to '{destination}'.")
        return DISTANCE_CACHE[cache_key]
        
    print(f"[API CALL] Calculating route from '{origin}' to '{destination}' via {mode}...")
    gmaps = get_gmaps_client()
    
    try:
        response = gmaps.distance_matrix(
            origins=[origin],
            destinations=[destination],
            mode=mode
        )
        
        if response["status"] == "OK":
            row = response["rows"][0]
            element = row["elements"][0]
            if element["status"] == "OK":
                result = {
                    "distance_text": element["distance"]["text"],
                    "duration_text": element["duration"]["text"],
                    "duration_value_seconds": element["duration"]["value"]
                }
                DISTANCE_CACHE[cache_key] = result
                return result
            else:
                print(f"Route not found: {element['status']}")
                return None
        else:
            print(f"Distance Matrix API error: {response['status']}")
            return None
            
    except Exception as e:
        print(f"Error calculating route: {e}")
        return None

# --- Example Usage for Testing ---
if __name__ == "__main__":
    # To test this locally, you must set GOOGLE_MAPS_API_KEY environment variable.
    # e.g., $env:GOOGLE_MAPS_API_KEY="AIza..." (Windows PowerShell)
    try:
        print("Testing Places Search...")
        places = search_nearby_restaurants(location="25.033964, 121.564468", keyword="烤肉", radius_meters=3000)
        for p in places:
            print(f"- {p['name']} (Rating: {p['rating']}, Price: {p['price_level']})")
            
        if places:
            print("\nTesting Route Calculation...")
            route = get_route_duration(origin="25.033964, 121.564468", destination=f"place_id:{places[0]['place_id']}")
            print(route)
            
    except ValueError as e:
        print(f"Skipping API test: {e}")
