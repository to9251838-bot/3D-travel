import os
import time
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

APP_TITLE = "World Explorer"
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "").strip()
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
CLOUDFLARE_IMAGE_MODEL = os.getenv(
    "CLOUDFLARE_IMAGE_MODEL", "@cf/black-forest-labs/flux-1-schnell"
).strip()

app = FastAPI(title=APP_TITLE)
_sky_cache: dict[str, tuple[float, dict]] = {}


class SkyRequest(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    weather: str = Field(default="clear sky", max_length=160)
    period: str = Field(default="day", max_length=20)


@app.get("/", response_class=HTMLResponse)
async def home():
    try:
        with open("index.html", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise HTTPException(500, "index.html is missing from the repository root")


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "openweather_configured": bool(OPENWEATHER_API_KEY),
        "cloudflare_configured": bool(CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN),
        "cloudflare_model": CLOUDFLARE_IMAGE_MODEL,
    }


@app.get("/api/weather")
async def weather(lat: float = Query(ge=-90, le=90), lon: float = Query(ge=-180, le=180)):
    if not OPENWEATHER_API_KEY:
        raise HTTPException(503, "Добавьте OPENWEATHER_API_KEY в Environment на Render")
    url = "https://api.openweathermap.org/data/2.5/weather"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                url,
                params={"lat": lat, "lon": lon, "appid": OPENWEATHER_API_KEY, "units": "metric", "lang": "ru"},
            )
        if response.status_code != 200:
            print("OpenWeather error:", response.status_code, response.text[:500])
            raise HTTPException(502, "OpenWeather не смог получить погоду для этой точки")
        data = response.json()
        w = (data.get("weather") or [{}])[0]
        return {
            "name": data.get("name") or "Точка на карте",
            "lat": lat,
            "lon": lon,
            "temp": round(data.get("main", {}).get("temp", 0)),
            "feels_like": round(data.get("main", {}).get("feels_like", 0)),
            "description": w.get("description", "неизвестно"),
            "icon": w.get("icon", "01d"),
            "weather_id": w.get("id", 800),
            "humidity": data.get("main", {}).get("humidity"),
            "wind": data.get("wind", {}).get("speed"),
            "timezone": data.get("timezone", 0),
            "sunrise": data.get("sys", {}).get("sunrise"),
            "sunset": data.get("sys", {}).get("sunset"),
            "observed_at": int(time.time()),
        }
    except httpx.TimeoutException:
        raise HTTPException(504, "OpenWeather не ответил вовремя")


@app.post("/api/sky")
async def generate_sky(request: SkyRequest):
    if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_API_TOKEN:
        raise HTTPException(503, "Добавьте CLOUDFLARE_ACCOUNT_ID и CLOUDFLARE_API_TOKEN в Render Environment")

    period = request.period.lower()
    if period not in {"dawn", "day", "dusk", "night", "morning", "evening"}:
        period = "day"

    # Reuse a recent result for nearby points with the same weather/time, to avoid repeated AI charges.
    cache_key = f"{round(request.lat, 1)}:{round(request.lon, 1)}:{request.weather.lower()}:{period}"
    cached = _sky_cache.get(cache_key)
    if cached and time.time() - cached[0] < 3600:
        return {**cached[1], "cached": True}

    prompt = (
        "Create a beautiful photorealistic ultra-wide cinematic sky panorama to composite above a real 3D map. "
        f"Atmosphere and weather: {request.weather}. Local time of day: {period}. "
        f"Approximate geographic coordinates: {request.lat:.3f}, {request.lon:.3f}. "
        "Natural physically plausible clouds, atmospheric haze and lighting, realistic sky gradient, broad distant horizon. "
        "Only sky and distant atmospheric horizon: no foreground, no buildings, no mountains, no people, no text, no logos. "
        "Wide landscape composition, seamless-looking horizon, high realism."
    )
    endpoint = (
        f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}"
        f"/ai/run/{CLOUDFLARE_IMAGE_MODEL}"
    )
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(
                endpoint,
                headers={"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}", "Content-Type": "application/json"},
                json={"prompt": prompt, "steps": 4},
            )
        if response.status_code != 200:
            try:
                body = response.json()
                detail = (body.get("errors") or [{}])[0].get("message") or str(body)[:400]
            except Exception:
                detail = response.text[:400]
            print(f"Cloudflare Workers AI error {response.status_code}: {detail}")
            if response.status_code in (401, 403):
                raise HTTPException(502, "Cloudflare отклонил токен. Проверьте API Token и доступ к Workers AI.")
            raise HTTPException(502, f"Cloudflare не смог сгенерировать небо (HTTP {response.status_code})")
        body = response.json()
        result = body.get("result") or {}
        image_data = result.get("image") if isinstance(result, dict) else None
        if not image_data:
            print("Unexpected Cloudflare response:", str(body)[:500])
            raise HTTPException(502, "Cloudflare вернул ответ без изображения")
        payload = {
            "ok": True,
            "image": "data:image/jpeg;base64," + image_data,
            "model": CLOUDFLARE_IMAGE_MODEL,
            "cached": False,
        }
        _sky_cache[cache_key] = (time.time(), payload)
        return payload
    except HTTPException:
        raise
    except httpx.TimeoutException:
        raise HTTPException(504, "Генерация неба заняла слишком много времени")
    except Exception as exc:
        print("Cloudflare request failed:", repr(exc))
        raise HTTPException(502, "Не удалось связаться с Cloudflare Workers AI")
