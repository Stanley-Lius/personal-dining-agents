import os
from dotenv import load_dotenv
load_dotenv(override=True)
import requests
import logging
import math
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

def search_google_maps(text_query: str) -> Dict[str, Any]:
    """
    Searches Google Maps for restaurants using the Places API (New).
    
    Args:
        text_query: The natural language search query (e.g., "vegetarian restaurants near Taichung Park").
        
    Returns:
        A dictionary containing the top restaurant's details: name, address, priceLevel, 
        reviews, phone number, opening hours, googleMapsUri, and a list of photo names.
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        logger.error("GOOGLE_MAPS_API_KEY not set.")
        return {"error": "Missing API Key"}
        
    url = "https://places.googleapis.com/v1/places:searchText"
    
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.priceLevel,places.reviews,places.nationalPhoneNumber,places.regularOpeningHours,places.googleMapsUri,places.photos,places.rating,places.userRatingCount"
    }
    
    payload = {
        "textQuery": text_query,
        "maxResultCount": 5
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        places = data.get("places", [])
        if not places:
            return {"error": "No restaurants found."}
            
        # Compare and find the best match out of the 5
        best_place = None
        best_score = -1.0
        
        for place in places:
            rating = place.get("rating", 0.0)
            count = place.get("userRatingCount", 0)
            # Bayesian-like heuristic: rating * log10(count + 1)
            score = rating * math.log10(count + 1)
            
            if score > best_score:
                best_score = score
                best_place = place
                
        if not best_place:
            best_place = places[0]
        
        # Format the response
        result = {
            "name": best_place.get("displayName", {}).get("text", "Unknown"),
            "address": best_place.get("formattedAddress", "Unknown"),
            "price_level": best_place.get("priceLevel", "Unknown"),
            "rating": best_place.get("rating", "Unknown"),
            "user_rating_count": best_place.get("userRatingCount", "Unknown"),
            "phone_number": best_place.get("nationalPhoneNumber", "Unknown"),
            "google_maps_uri": best_place.get("googleMapsUri", "Unknown"),
            "opening_hours": best_place.get("regularOpeningHours", {}).get("weekdayDescriptions", []),
            "reviews": [rev.get("text", {}).get("text", "") for rev in best_place.get("reviews", [])[:3]], # top 3 reviews
            "photo_names": [photo.get("name") for photo in best_place.get("photos", [])[:5]] # get top 5 photo references
        }
        return result
    except Exception as e:
        logger.error(f"Places API New failed: {e}")
        return {"error": str(e)}

def fetch_photo_bytes(photo_name: str) -> bytes:
    """
    Downloads the actual image bytes of a Google Maps photo.
    
    Args:
        photo_name: The resource name of the photo (e.g., "places/ChIJxyz/photos/AbCdef").
        
    Returns:
        The raw bytes of the JPEG image, or None if failed.
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        logger.error("GOOGLE_MAPS_API_KEY not set.")
        return None
        
    url = f"https://places.googleapis.com/v1/{photo_name}/media?maxWidthPx=800&key={api_key}"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.content
    except Exception as e:
        logger.error(f"Failed to fetch photo {photo_name}: {e}")
        return None
