import requests
import logging
from datetime import datetime
from typing import Dict, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NOAAWeatherClient:
    """
    Fetch real weather data from NOAA API
    No API key required!
    """
    
    def __init__(self):
        # NOAA API endpoint
        self.points_url = "https://api.weather.gov/points"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "(Climate Intelligence Platform, contact@example.com)"
        })
        
        # Define major US cities with coordinates
        self.locations = {
            "New York": {"lat": 40.7128, "lon": -74.0060},
            "Los Angeles": {"lat": 34.0522, "lon": -118.2437},
            "Chicago": {"lat": 41.8781, "lon": -87.6298},
            "Houston": {"lat": 29.7604, "lon": -95.3698},
            "Phoenix": {"lat": 33.4484, "lon": -112.0742},
            "Philadelphia": {"lat": 39.9526, "lon": -75.1652},
            "San Antonio": {"lat": 29.4241, "lon": -98.4936},
            "San Diego": {"lat": 32.7157, "lon": -117.1611},
            "Dallas": {"lat": 32.7767, "lon": -96.7970},
            "San Jose": {"lat": 37.3382, "lon": -121.8863},
            "Miami": {"lat": 25.7617, "lon": -80.1918},
            "Seattle": {"lat": 47.6062, "lon": -122.3321},
            "Denver": {"lat": 39.7392, "lon": -104.9903},
            "Boston": {"lat": 42.3601, "lon": -71.0589},
            "Las Vegas": {"lat": 36.1699, "lon": -115.1398}
        }
        
        logger.info(f"✅ NOAA Weather Client initialized with {len(self.locations)} locations")

    def get_weather_for_location(self, location: str) -> Optional[Dict]:
        """
        Get real weather data for a specific location
        
        Args:
            location: City name (e.g., "New York")
        
        Returns:
            Dict with weather data or None if error
        """
        
        if location not in self.locations:
            logger.error(f"❌ Location '{location}' not found. Available: {list(self.locations.keys())}")
            return None
        
        coords = self.locations[location]
        lat = coords["lat"]
        lon = coords["lon"]
        
        try:
            # Step 1: Get grid point for the location
            logger.info(f"📍 Fetching weather for {location}...")
            points_response = self.session.get(
                f"{self.points_url}/{lat},{lon}",
                timeout=10
            )
            points_response.raise_for_status()
            points_data = points_response.json()
            
            # Step 2: Get forecast URL from points
            if "properties" not in points_data:
                logger.error(f"❌ Invalid response from NOAA")
                return None
            
            forecast_url = points_data["properties"]["forecast"]
            
            # Step 3: Get actual forecast data
            forecast_response = self.session.get(forecast_url, timeout=10)
            forecast_response.raise_for_status()
            forecast_data = forecast_response.json()
            
            # Step 4: Extract first period (current conditions)
            if "properties" not in forecast_data or "periods" not in forecast_data["properties"]:
                logger.error(f"❌ No forecast data available")
                return None
            
            period = forecast_data["properties"]["periods"][0]
            
            # Step 5: Parse weather data
            weather_data = self._parse_forecast(period, location)
            
            if weather_data:
                logger.info(f"✅ Got real data for {location}: "
                           f"Temp: {weather_data['temperature']}°F, "
                           f"Humidity: {weather_data['humidity']}%, "
                           f"Wind: {weather_data['wind_speed']} mph")
            
            return weather_data
            
        except requests.exceptions.Timeout:
            logger.error(f"❌ Timeout connecting to NOAA for {location}")
            return None
        except requests.exceptions.ConnectionError:
            logger.error(f"❌ Connection error with NOAA")
            return None
        except Exception as e:
            logger.error(f"❌ Error fetching weather for {location}: {e}")
            return None

    def _parse_forecast(self, period: Dict, location: str) -> Optional[Dict]:
        """
        Parse NOAA forecast data and extract key metrics
        
        Args:
            period: Forecast period from NOAA
            location: Location name
        
        Returns:
            Cleaned weather dictionary
        """
        
        try:
            temperature = period.get("temperature", 70)
            wind_speed = period.get("windSpeed", "0 mph")
            
            # Parse wind speed (format: "12 mph")
            wind_value = float(wind_speed.split()[0]) if wind_speed else 0
            
            # Get humidity (if available)
            relative_humidity = period.get("relativeHumidity", {}).get("value", 50)
            if relative_humidity is None:
                relative_humidity = 50
            
            # Get precipitation (if available)
            precipitation = 0.0  # NOAA doesn't always provide this in forecast
            
            # Get pressure (if available)
            pressure = period.get("barometricPressure", {}).get("value", 1013)
            if pressure is None:
                pressure = 1013
            
            # Convert hectopascals to millibars if needed
            if pressure and pressure > 100:  # hectopascals
                pressure = pressure / 100
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "location": location,
                "temperature": float(temperature),
                "humidity": float(relative_humidity),
                "wind_speed": float(wind_value),
                "pressure": float(pressure),
                "precipitation": float(precipitation),
                "forecast_text": period.get("shortForecast", ""),
                "is_daytime": period.get("isDaytime", True)
            }
            
        except Exception as e:
            logger.error(f"❌ Error parsing forecast: {e}")
            return None

    def get_all_locations_weather(self) -> Dict[str, Dict]:
        """
        Get weather for all configured locations
        
        Returns:
            Dict with location names as keys and weather data as values
        """
        all_weather = {}
        
        for location in self.locations.keys():
            weather = self.get_weather_for_location(location)
            if weather:
                all_weather[location] = weather
        
        logger.info(f"✅ Successfully fetched weather for {len(all_weather)} locations")
        return all_weather


if __name__ == "__main__":
    # Test the client
    client = NOAAWeatherClient()
    
    # Get weather for one location
    weather = client.get_weather_for_location("New York")
    if weather:
        print(f"\n📊 Real Weather Data from NOAA:")
        for key, value in weather.items():
            print(f"  {key}: {value}")
    
    # Get weather for all locations
    print(f"\n📍 Fetching weather for all locations...")
    all_weather = client.get_all_locations_weather()
    print(f"✅ Got real data for {len(all_weather)} cities!")
