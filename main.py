from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from database import db
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
import logging

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialisation de l'application FastAPI
app = FastAPI(title="PulseBoard API", version="1.0.0")

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Initialisation au démarrage de l'application"""
    try:
        await db.connect()
        logger.info("✅ Database connection established successfully")
    except Exception as e:
        logger.error(f"❌ Failed to connect to database: {e}")
        raise e

@app.on_event("shutdown")
async def shutdown_event():
    """Nettoyage à l'arrêt de l'application"""
    try:
        await db.disconnect()
        logger.info("✅ Database connection closed successfully")
    except Exception as e:
        logger.error(f"❌ Error closing database connection: {e}")

@app.get("/")
async def root():
    """Point d'entrée principal"""
    return {
        "message": "PulseBoard API is running!",
        "version": "1.0.0",
        "status": "active",
        "database": "Neon PostgreSQL"
    }

@app.get("/health")
async def health_check():
    """Vérification de l'état de l'API"""
    try:
        # Test de connexion à la base
        is_connected = await db.test_connection()
        return {
            "status": "healthy",
            "database_connected": is_connected,
            "database_type": "Neon PostgreSQL",
            "timestamp": datetime.now().isoformat() + "Z"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database_connected": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat() + "Z"
        }

@app.get("/api/debug/env")
async def debug_env():
    """Debug des variables d'environnement"""
    database_url = os.getenv("DATABASE_URL")
    return {
        "database_url": database_url[:50] + "..." if database_url else None,
        "database_url_valid": bool(database_url and database_url.startswith("postgresql://")),
        "database_configured": bool(database_url),
        "all_env_vars": [key for key in os.environ.keys() if not key.startswith("_")]
    }

@app.get("/api/debug/database")
async def debug_database():
    """Debug complet de la base de données"""
    try:
        database_url = os.getenv("DATABASE_URL")
        result = {
            "database_url_configured": bool(database_url),
            "database_url_valid": bool(database_url and database_url.startswith("postgresql://")),
            "database_connected": False,
            "database_error": None,
            "tables_count": 0
        }
        
        if not database_url:
            result["database_error"] = "Missing DATABASE_URL environment variable"
            return result
        
        # Test de connexion
        is_connected = await db.test_connection()
        result["database_connected"] = is_connected
        
        if is_connected:
            # Compter les tables
            tables = await db.get_tables_list()
            result["tables_count"] = len(tables) if tables else 0
            result["tables"] = tables
        
        return result
        
    except Exception as e:
        return {
            "database_connected": False,
            "database_error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.get("/api/test")
async def test_api():
    """Test général de l'API"""
    try:
        is_connected = await db.test_connection()
        return {
            "api_status": "working",
            "database_status": "connected" if is_connected else "disconnected",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "api_status": "working",
            "database_status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

# Routes pour les événements
@app.get("/api/events")
async def get_events():
    """Récupère tous les événements"""
    try:
        events = await db.get_all_events()
        return {"events": events}
    except Exception as e:
        logger.error(f"Error fetching events: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/events")
async def create_event(event_data: Dict[str, Any]):
    """Crée un nouvel événement"""
    try:
        # Validation des données requises
        required_fields = ['name', 'city_id', 'event_date']
        for field in required_fields:
            if field not in event_data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        event_id = await db.save_event_data(
            city_id=event_data['city_id'],
            event_data=event_data
        )
        return {"message": "Event created successfully", "event_id": event_id}
    except Exception as e:
        logger.error(f"Error creating event: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/events/city/{city_id}")
async def get_events_by_city(city_id: int):
    """Récupère les événements d'une ville"""
    try:
        events = await db.get_events_by_city(city_id)
        return {"events": events}
    except Exception as e:
        logger.error(f"Error fetching events for city {city_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Routes pour les métriques (données météo)
@app.get("/api/metrics")
async def get_metrics():
    """Récupère toutes les métriques météo"""
    try:
        metrics = await db.get_all_weather_data()
        return {"metrics": metrics}
    except Exception as e:
        logger.error(f"Error fetching metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/metrics")
async def create_metric(metric_data: Dict[str, Any]):
    """Crée une nouvelle métrique météo"""
    try:
        # Validation des données requises
        required_fields = ['city_id', 'temperature', 'humidity']
        for field in required_fields:
            if field not in metric_data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        metric_id = await db.save_weather_data(
            city_id=metric_data['city_id'],
            weather_data=metric_data
        )
        return {"message": "Metric created successfully", "metric_id": metric_id}
    except Exception as e:
        logger.error(f"Error creating metric: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/metrics/city/{city_id}")
async def get_metrics_by_city(city_id: int):
    """Récupère les métriques météo d'une ville"""
    try:
        metrics = await db.get_weather_by_city(city_id)
        return {"metrics": metrics}
    except Exception as e:
        logger.error(f"Error fetching metrics for city {city_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Routes pour les villes
@app.get("/api/cities")
async def get_cities():
    """Récupère toutes les villes"""
    try:
        cities = await db.get_all_cities()
        return {"cities": cities}
    except Exception as e:
        logger.error(f"Error fetching cities: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/cities/{city_name}")
async def get_city_by_name(city_name: str):
    """Récupère une ville par son nom"""
    try:
        city = await db.get_city_by_name(city_name)
        if not city:
            raise HTTPException(status_code=404, detail="City not found")
        return {"city": city}
    except Exception as e:
        logger.error(f"Error fetching city {city_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/cities")
async def create_city(city_data: Dict[str, Any]):
    """Crée une nouvelle ville"""
    try:
        # Validation des données requises
        required_fields = ['name', 'country', 'latitude', 'longitude']
        for field in required_fields:
            if field not in city_data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        city_id = await db.save_city_data(city_data)
        return {"message": "City created successfully", "city_id": city_id}
    except Exception as e:
        logger.error(f"Error creating city: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Routes pour les scores urbains
@app.get("/api/urban-scores")
async def get_urban_scores():
    """Récupère tous les scores urbains"""
    try:
        scores = await db.get_all_urban_scores()
        return {"urban_scores": scores}
    except Exception as e:
        logger.error(f"Error fetching urban scores: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/urban-scores/city/{city_id}")
async def get_urban_score_by_city(city_id: int):
    """Récupère le dernier score urbain d'une ville"""
    try:
        score = await db.get_latest_urban_score(city_id)
        if not score:
            raise HTTPException(status_code=404, detail="No urban score found for this city")
        return {"urban_score": score}
    except Exception as e:
        logger.error(f"Error fetching urban score for city {city_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/urban-scores")
async def create_urban_score(score_data: Dict[str, Any]):
    """Crée un nouveau score urbain"""
    try:
        # Validation des données requises
        required_fields = ['city_id', 'overall_score']
        for field in required_fields:
            if field not in score_data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        score_id = await db.save_urban_score(
            city_id=score_data['city_id'],
            score_data=score_data
        )
        return {"message": "Urban score created successfully", "score_id": score_id}
    except Exception as e:
        logger.error(f"Error creating urban score: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
