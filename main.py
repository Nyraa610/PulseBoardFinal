import asyncio, os, pickle, random
from datetime import datetime

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from supabase import create_client

load_dotenv()

# app
app = FastAPI(title="PulseBoard API", version="1.0.0")

# middleware pour front, enleve stv
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Servir les fichiers statiques du frontend
if os.path.exists("front"):
    app.mount("/static", StaticFiles(directory="front"), name="static")

    @app.get("/")
    async def serve_frontend():
        """Servir le frontend PulseBoard"""
        return FileResponse('front/index.html')

# constants
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
db = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

OWM = os.getenv("OPENWEATHER_API_KEY")
AGENDA = os.getenv("OPENAGENDA_API_KEY")

# les villes, chaque endpoint le support auto, peut etre, probablement.
CITIES = {
    "paris": {"lat": 48.8566, "lon": 2.3522},
    "lyon": {"lat": 45.7640, "lon": 4.8357},
    "bordeaux": {"lat": 44.8378, "lon": -0.5792},
    "marseille": {"lat": 43.2965, "lon": 5.3698},
    "lille": {"lat": 50.6292, "lon": 3.0573},
}

# pour le model ML, change a ton plaisir frr
# MODEL désactivé temporairement (nécessite numpy)
MODEL = None

# helpeurs

def city_or_404(city: str) -> str:
    """Reject unknown cities before any API call is made."""
    c = city.lower()
    if c not in CITIES:
        raise HTTPException(404, f"'{city}' not supported. Try: {list(CITIES)}")
    return c


async def save_to_db(city: str, data_type: str, data: dict):
    """Sauvegarde les données en base Supabase"""
    if not db:
        print("⚠️ Supabase non configuré")
        return None
    
    try:
        result = db.table('pulse_data').insert({
            'city': city,
            'data_type': data_type,
            'data': data,
            'timestamp': datetime.utcnow().isoformat()
        }).execute()
        print(f"✅ Sauvegardé: {city} - {data_type}")
        return result
    except Exception as e:
        print(f"❌ Erreur DB: {e}")
        return None


def weather_score(cur: dict) -> float:
    """Convert current weather into a 0-100 score. 18-24C is ideal."""
    t = cur["temp"]
    if 18 <= t <= 24:
        ts = 100
    elif 10 <= t <= 30:
        ts = 70
    elif 0 <= t <= 35:
        ts = 40
    else:
        ts = 20

    desc = cur["description"].lower()
    bad = ["rain", "pluie", "orage", "thunder", "snow", "neige", "fog", "brouillard"]
    mid = ["cloud", "nuage", "overcast", "couvert"]
    cs = 30 if any(w in desc for w in bad) else 65 if any(w in desc for w in mid) else 100

    return round(ts * 0.6 + cs * 0.4, 1)


def air_score(aqi: int) -> float:
    """Lower AQI = better air = higher score."""
    if aqi <= 50:  return 100.0
    if aqi <= 100: return 75.0
    if aqi <= 150: return 50.0
    if aqi <= 200: return 25.0
    return 10.0


def event_score(events: list) -> float:
    """5 events = full score, scales linearly below that."""
    return min(len(events) * 20, 100)


def aqi_label(aqi: int) -> dict:
    """Return color, label, and health advice for a given AQI value."""
    if aqi <= 50:  return {"color": "green", "label": "Bon", "advice": "Parfait pour les activites outdoor"}
    if aqi <= 100: return {"color": "yellow", "label": "Modere",
                           "advice": "Acceptable, personnes sensibles soyez prudentes"}
    if aqi <= 150: return {"color": "orange", "label": "Mauvais", "advice": "Evitez le sport intensif en exterieur"}
    return {"color": "red", "label": "Dangereux", "advice": "Restez a l'interieur"}


# endpoints

@app.get("/health")
def health():
    """Render pings this to check the server is alive."""
    return {
        "status": "ok", 
        "time": datetime.utcnow().isoformat(),
        "supabase": "connected" if db else "not configured"
    }


@app.get("/api/debug/db")
async def test_db():
    """Test de connexion DB et affichage des données récentes"""
    if not db:
        return {"status": "error", "error": "Supabase not configured"}
    
    try:
        result = db.table('pulse_data').select('*').order('timestamp', desc=True).limit(10).execute()
        return {
            "status": "connected",
            "recent_data": result.data,
            "count": len(result.data),
            "supabase_url": SUPABASE_URL
        }
    except Exception as e:
        return {
            "status": "error", 
            "error": str(e)
        }


@app.get("/api/dashboard/{city}")
async def get_dashboard(city: str):
    """
    Endpoint consolidé pour récupérer toutes les données du dashboard
    """
    city = city_or_404(city)

    try:
        # Récupération parallèle de toutes les données
        weather, air, events, score, prediction = await asyncio.gather(
            get_weather(city),
            get_air(city),
            get_events(city),
            get_score(city),
            get_predict(city),
            return_exceptions=True
        )

        # Gestion des erreurs individuelles
        if isinstance(weather, Exception):
            weather = {"error": str(weather)}
        if isinstance(air, Exception):
            air = {"error": str(air)}
        if isinstance(events, Exception):
            events = {"events": [], "error": str(events)}
        if isinstance(score, Exception):
            score = {"score": 0, "error": str(score)}
        if isinstance(prediction, Exception):
            prediction = {"error": str(prediction)}

        dashboard_data = {
            "city": city,
            "weather": weather,
            "air": air,
            "events": events,
            "score": score,
            "prediction": prediction,
            "updated_at": datetime.utcnow().isoformat()
        }

        # Sauvegarde du dashboard complet
        await save_to_db(city, 'dashboard', dashboard_data)

        return dashboard_data
    except Exception as e:
        raise HTTPException(500, f"Dashboard error: {str(e)}")


@app.get("/api/weather/{city}")
async def get_weather(city: str):
    """Current conditions and 24h forecast from OpenWeatherMap."""
    city = city_or_404(city)
    coords = CITIES[city]

    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(
            "https://api.openweathermap.org/data/2.5/forecast",
            params={
                "lat": coords["lat"], "lon": coords["lon"],
                "appid": OWM, "units": "metric", "lang": "fr", "cnt": 8,
            },
        )
    if r.status_code != 200:
        raise HTTPException(502, f"OpenWeatherMap error: {r.text}")

    raw = r.json()["list"]
    cur = raw[0]

    weather_data = {
        "city": city,
        "current": {
            "temp": round(cur["main"]["temp"], 1),
            "feels_like": round(cur["main"]["feels_like"], 1),
            "humidity": cur["main"]["humidity"],
            "wind_speed": round(cur["wind"]["speed"] * 3.6, 1),  # m/s to km/h
            "pressure": cur["main"]["pressure"],
            "visibility": 15,  # Default value as OWM doesn't provide this in forecast
            "description": cur["weather"][0]["description"],
            "icon": cur["weather"][0]["icon"],
        },
        "forecast_24h": [
            {
                "time": slot["dt_txt"],
                "temp": round(slot["main"]["temp"], 1),
                "feels_like": round(slot["main"]["feels_like"], 1),
                "humidity": slot["main"]["humidity"],
                "icon": slot["weather"][0]["icon"],
                "description": slot["weather"][0]["description"],
            }
            for slot in raw
        ],
        "updated_at": datetime.utcnow().isoformat(),
    }

    # Sauvegarde en DB
    await save_to_db(city, 'weather', weather_data)
    
    return weather_data


@app.get("/api/air/{city}")
async def get_air(city: str):
    """AQI, PM2.5, NO2, color and health advice from OWM Air Pollution API."""
    city = city_or_404(city)
    coords = CITIES[city]

    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(
            "https://api.openweathermap.org/data/2.5/air_pollution",
            params={"lat": coords["lat"], "lon": coords["lon"], "appid": OWM},
        )
    if r.status_code != 200:
        raise HTTPException(502, f"Air Pollution API error: {r.text}")

    entry = r.json()["list"][0]
    components = entry["components"]

    # si on utilize OWM, ils utilizent un truc de 1-5, map le dans l'intervalle standard 0-500
    aqi = {1: 20, 2: 60, 3: 110, 4: 175, 5: 280}.get(entry["main"]["aqi"], 100)
    meta = aqi_label(aqi)

    air_data = {
        "city": city,
        "aqi": aqi,
        "label": meta["label"],
        "color": meta["color"],
        "advice": meta["advice"],
        "pm25": round(components.get("pm2_5", 0), 2),
        "no2": round(components.get("no2", 0), 2),
        "o3": round(components.get("o3", 0), 2),
        "updated_at": datetime.utcnow().isoformat(),
    }

    # Sauvegarde en DB
    await save_to_db(city, 'air', air_data)
    
    return air_data


@app.get("/api/events/{city}")
async def get_events(city: str):
    """Next 5 public events from OpenAgenda. Returns empty list if API is down."""
    city = city_or_404(city)

    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(
            "https://api.openagenda.com/v2/events",
            params={
                "key": AGENDA, "search[city]": city.capitalize(),
                "size": 5, "sort": "timingsWithFeatured.asc",
            },
        )

    # pas fatal, peut-etre, probablement, j'espere, maybe
    if r.status_code != 200:
        events_data = {"city": city, "events": [], "warning": "OpenAgenda unavailable",
                      "updated_at": datetime.utcnow().isoformat()}
        await save_to_db(city, 'events', events_data)
        return events_data

    events = []
    for item in r.json().get("events", [])[:5]:
        title = item.get("title", {})
        title = (title.get("fr") or title.get("en") or "Evenement") if isinstance(title, dict) else title
        location = item.get("location", {})
        events.append({
            "id": item.get("uid"),
            "name": title,
            "date": (item.get("firstTiming") or {}).get("begin", ""),
            "location": location.get("name", ""),
            "category": (item.get("keywords") or ["Autre"])[0],
        })

    events_data = {"city": city, "events": events, "updated_at": datetime.utcnow().isoformat()}
    
    # Sauvegarde en DB
    await save_to_db(city, 'events', events_data)
    
    return events_data


@app.get("/api/score/{city}")
async def get_score(city: str):
    """
    Urban score = weather x 0.4 + air x 0.4 + events x 0.2.
    All three sources are fetched in parallel for speed.
    """
    city = city_or_404(city)

    weather, air, events = await asyncio.gather(
        get_weather(city),
        get_air(city),
        get_events(city),
    )

    ws = weather_score(weather["current"])
    as_ = air_score(air["aqi"])
    es = event_score(events["events"])
    total = round(ws * 0.4 + as_ * 0.4 + es * 0.2, 1)

    score_data = {
        "city": city,
        "score": total,
        "label": "Excellent" if total >= 80 else "Bon" if total >= 60 else "Moyen" if total >= 40 else "Mauvais",
        "breakdown": {
            "weather": {"score": ws, "weight": 0.4},
            "air_quality": {"score": as_, "weight": 0.4},
            "events": {"score": es, "weight": 0.2},
        },
        "formula": "score = weather x 0.4 + air x 0.4 + events x 0.2",
        "updated_at": datetime.utcnow().isoformat(),
    }

    # Sauvegarde en DB
    await save_to_db(city, 'score', score_data)
    
    return score_data


@app.get("/api/predict/{city}")
async def get_predict(city: str):
    """
    AQI prediction for the next 6 hours.
    Uses simple estimation since ML model requires numpy.
    """
    city = city_or_404(city)
    air = await get_air(city)
    cur = air["aqi"]

    # Prédiction simplifiée sans numpy ni ML
    predicted = round(cur * (1 + random.uniform(-0.08, 0.08)), 1)
    confidence = 60
    
    forecast, val = [], predicted
    for h in range(1, 7):
        val = max(0, round(val + random.uniform(-4, 4), 1))
        forecast.append({"hour": f"+{h}h", "aqi": val})

    meta = aqi_label(int(predicted))

    prediction_data = {
        "city": city,
        "current_aqi": cur,
        "predicted_aqi_6h": round(predicted, 1),
        "forecast": forecast,
        "confidence": confidence,
        "color": meta["color"],
        "label": meta["label"],
        "model": "fallback",
        "updated_at": datetime.utcnow().isoformat(),
    }

    # Sauvegarde en DB
    await save_to_db(city, 'prediction', prediction_data)
    
    return prediction_data


# Point d'entrée pour Vercel/autres plateformes
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
