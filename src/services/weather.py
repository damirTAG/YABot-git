from __future__ import annotations

import asyncio
import datetime
import html
from dataclasses import dataclass
from itertools import groupby
from typing import Any

import aiohttp

from config.settings import OWM_API_KEY

Node = str | dict[str, Any]
FORECAST_HOURS = frozenset({2, 5, 8, 11, 14, 17, 20, 23})

# city_id -> (display_name, flag_override)
CITY_OVERRIDES: dict[int, tuple[str, str | None]] = {
    1526273: ("Астана", None),
    610613: ("4 энергоблок", "😂"),
}
OWM_BASE = "https://api.openweathermap.org/data/2.5"
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)

WEATHER_BLOCKED_CHAT_IDS = {1825727646}

CITY_ALIASES = {
    "аксай": "аксай, kz",
    "4 энергоблок": "аксай, kz",
}


class WeatherAPIError(Exception):
    pass


class CityNotFoundError(WeatherAPIError):
    pass


@dataclass(frozen=True)
class Forecast:
    dt: datetime.datetime
    temp: float
    description: str

    @property
    def day(self) -> str:
        return self.dt.strftime("%d.%m")

    @property
    def time(self) -> str:
        return self.dt.strftime("%H:%M")


class Weather:
    def __init__(self, weather_data: dict, forecast_data: dict | None = None):
        # Direct indexing on purpose: the handler already validated cod == 200,
        # so a missing key here is a real bug and should raise loudly.
        sys_info = weather_data["sys"]
        main_info = weather_data["main"]

        self.city_id: int = weather_data["id"]
        self.country_code: str | None = sys_info.get("country")

        self.timezone = datetime.timezone(datetime.timedelta(seconds=weather_data["timezone"]))

        self.weather_description: str = weather_data["weather"][0]["description"].capitalize()
        self.temperature: float = round(main_info["temp"], 1)
        self.feels_like: float = round(main_info["feels_like"], 1)
        self.humidity: int = main_info["humidity"]
        self.wind_speed: float = weather_data["wind"]["speed"]

        self.sunrise: str = self._local_time(sys_info["sunrise"])
        self.sunset: str = self._local_time(sys_info["sunset"])

        override = CITY_OVERRIDES.get(self.city_id)
        if override:
            self.city_name, flag = override
            self.flag_emoji = flag if flag is not None else get_flag_emoji(self.country_code)
        else:
            self.city_name = weather_data["name"]
            self.flag_emoji = get_flag_emoji(self.country_code)

        self.forecasts: list[Forecast] = self._parse_forecasts(forecast_data)

    def _local_time(self, unix_ts: int) -> str:
        return datetime.datetime.fromtimestamp(unix_ts, tz=self.timezone).strftime("%H:%M")

    def _parse_forecasts(self, forecast_data: dict | None) -> list[Forecast]:
        if not forecast_data:
            return []

        forecasts = []
        for item in forecast_data.get("list", []):
            dt = datetime.datetime.fromtimestamp(item["dt"], tz=self.timezone)
            if dt.hour in FORECAST_HOURS:
                forecasts.append(
                    Forecast(
                        dt=dt,
                        temp=round(item["main"]["temp"], 1),
                        description=item["weather"][0]["description"].capitalize(),
                    )
                )
        return forecasts

    def _utc_offset_str(self) -> str:
        offset = self.timezone.utcoffset(None)
        hours = int(offset.total_seconds() // 3600)
        return f"UTC{hours:+03d}:00"

    def generate_output(self) -> str:
        now = datetime.datetime.now(self.timezone).strftime("%H:%M (%d.%m.%Y)")
        city = html.escape(self.city_name)
        return (
            f"<b>🏙 Weather in {city} ({self.flag_emoji}):</b>\n"
            f"🌡 Currently: <b>{self.temperature}°C</b> ({self.weather_description})\n"
            f"🫂 Feels like: <b>{self.feels_like}°C</b>\n"
            f"🌬 Wind: <b>{self.wind_speed} m/s</b>\n"
            f"💦 Humidity: <b>{self.humidity}%</b>\n"
            f"⏰ Time: <b>{now}</b>\n"
            f"🌅 Sunrise: <b>{self.sunrise}</b> | 🌇 Sunset: <b>{self.sunset}</b>\n\n"
        )

    def generate_telegraph_content(self) -> list[Node]:
        content: list[Node] = []

        content.append({"tag": "p", "children": [f"📅 Forecast ({self._utc_offset_str()})"]})

        for day, items in groupby(self.forecasts, key=lambda f: f.day):
            content.append({"tag": "h4", "children": [day]})

            ul = {"tag": "ul", "children": []}

            for f in items:
                ul["children"].append(
                    {"tag": "li", "children": [f"🕒 {f.time} | {f.temp}°C | {f.description}"]}
                )

            content.append(ul)

        return content


def get_flag_emoji(country_code: str | None) -> str:
    if not country_code or len(country_code) != 2:
        return ""
    return "".join(chr(127397 + ord(c)) for c in country_code.upper())


async def _fetch_owm(session: aiohttp.ClientSession, endpoint: str, city: str) -> dict:
    params = {"q": city, "appid": OWM_API_KEY, "units": "metric", "lang": "en"}
    async with session.get(f"{OWM_BASE}/{endpoint}", params=params) as resp:
        data = await resp.json()
        if resp.status == 404:
            raise CityNotFoundError(city)
        if resp.status != 200:
            raise WeatherAPIError(f"{endpoint}: {resp.status} {data.get('message')}")
        return data


async def fetch_weather_data(city: str) -> tuple[dict, dict]:
    async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
        return await asyncio.gather(
            _fetch_owm(session, "weather", city),
            _fetch_owm(session, "forecast", city),
        )
