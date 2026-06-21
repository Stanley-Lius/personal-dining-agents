import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import map_search
from unittest.mock import patch, MagicMock

@patch("map_search.requests.post")
def test_search_google_maps_success(mock_post):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "places": [{
            "displayName": {"text": "Mock BBQ"},
            "formattedAddress": "123 BBQ St.",
            "priceLevel": "PRICE_LEVEL_MODERATE",
            "nationalPhoneNumber": "12345678",
            "googleMapsUri": "http://maps/123",
            "photos": [{"name": "places/123/photos/456"}]
        }]
    }
    mock_post.return_value = mock_response

    result = map_search.search_google_maps("BBQ")
    
    assert result["name"] == "Mock BBQ"
    assert "photo_names" in result
    assert result["photo_names"][0] == "places/123/photos/456"

@patch("map_search.requests.get")
def test_fetch_photo_bytes(mock_get):
    mock_response = MagicMock()
    mock_response.content = b"fake_image_bytes"
    mock_get.return_value = mock_response

    result = map_search.fetch_photo_bytes("places/123/photos/456")
    
    assert result == b"fake_image_bytes"

@patch("map_search.requests.post")
def test_search_google_maps_no_results(mock_post):
    mock_response = MagicMock()
    mock_response.json.return_value = {"places": []}
    mock_post.return_value = mock_response

    result = map_search.search_google_maps("FakeFood")
    
    assert "error" in result
