# World Explorer — 3D Earth travel simulator

A Render-ready starter project. It opens at the visitor's location (after browser permission), renders a tilted map with satellite imagery and terrain, fetches local weather, shows local time, and can ask Cloudflare Workers AI to generate a sky image matching approximate location/weather/time.

## Files
- `main.py` — FastAPI backend, OpenWeather proxy, Cloudflare sky generation endpoint.
- `index.html` — full-screen MapLibre frontend.
- `requirements.txt` — Python dependencies.

## Render deployment
Create a new GitHub repository, upload these three files to the repository root, then create a Render **Web Service**.

Build command:
```bash
pip install -r requirements.txt
```
Start command:
```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Set these environment variables in Render:
- `OPENWEATHER_API_KEY` — OpenWeather API key for current weather.
- `CLOUDFLARE_ACCOUNT_ID` — Cloudflare account ID.
- `CLOUDFLARE_API_TOKEN` — Cloudflare API token with Workers AI permissions.
- Optional: `CLOUDFLARE_IMAGE_MODEL` (defaults to `@cf/black-forest-labs/flux-1-schnell`).

Check `/api/health` after deployment.

## Controls
- Click `◎` to request current browser geolocation.
- Search a place name, address, or `latitude, longitude` to move the map anywhere on Earth.
- Select walk, car, or plane. Hold `↑ Вперёд` to move the map center in the current camera direction.
- Click `Создать небо` to request a Cloudflare-generated sky.
- Weather is refreshed when the map finishes moving; time is shown using the location's OpenWeather timezone offset.

## Important notes
- Browser geolocation requires HTTPS and explicit user permission.
- The map requests visible map tiles and nearby buffer tiles dynamically; it does not request a fixed number of exactly 16–20 tiles. Actual count depends on viewport size, zoom, device, and tile provider.
- Satellite imagery is provided by Esri World Imagery; terrain elevation tiles use AWS Terrain Tiles (Terrarium); the base vector style comes from OpenFreeMap. Review each provider's terms, attribution, quotas, and production-use requirements before public launch.
- This is a map-based travel simulator, not a photogrammetry/flight simulator. Buildings appear in 3D only where the vector style provides building geometry; satellite images and terrain resolution vary by location. There are no live street-level 3D scans.
- The generated sky is a 2D overlay and can be visually approximate; it is not a physically integrated sky dome. Rain is a visual overlay, not a weather simulation. Cloudflare image generation may incur usage costs and is cached briefly in memory.
- Movement speeds are illustrative. Searching for a place moves the camera directly there; it does not simulate a real flight path or transportation network.
- The base map may have usage limits or service availability changes. For a public commercial service, consider a licensed tile provider.
