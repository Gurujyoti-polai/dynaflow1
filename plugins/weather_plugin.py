import os
import httpx
from core.plugins.base import PluginBase
from typing import Dict, Any

class Plugin(PluginBase):
    @property
    def name(self) -> str:
        return "weather"

    @property
    def description(self) -> str:
        return "Fetch weather data from OpenWeather API"

    def execute(self, action: str, config: Dict[str, Any], mode: str = "real") -> Dict[str, Any]:
        city = config.get("city", "London")
        api_key = config.get("api_key", os.getenv("OPENWEATHER_API_KEY"))

        if mode == "mock":
            return {"status": "success", "mock": True, "temperature": 25, "city": city}

        if not api_key:
            return {"error": "Missing OPENWEATHER_API_KEY"}

        try:
            url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
            response = httpx.get(url)
            response.raise_for_status()
            data = response.json()

            return {
                "status": "success",
                "city": city,
                "temperature": data["main"]["temp"],
                "description": data["weather"][0]["description"],
            }
        except Exception as e:
            return {"error": str(e)}

    def get_available_actions(self) -> Dict[str, str]:
        return {"get_current": "Get current weather for a city"}
