from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
import logging

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

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

# Client Supabase global
supabase: Optional[Client] = None

def init_supabase():
    """Initialise le client Supabase"""
    global supabase
    try:
        if SUPABASE_URL and SUPABASE_KEY:
            # AUCUN PARAMETRE PROXY - JUSTE URL ET KEY
            supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            logger.info("✅ Supabase client initialized successfully")
            return True
        else:
            logger.warning("❌ Supabase credentials not found")
            return False
    except Exception as e:
        logger.error(f"❌ Failed to initialize Supabase: {e}")
        return False

# Initialisation au démarrage
init_supabase()

@app.get("/")
async def root():
    """Point d'entrée principal"""
    return {
        "message": "PulseBoard API is running!",
        "version": "1.0.0",
        "status": "active"
    }

@app.get("/health")
async def health_check():
    """Vérification de l'état de l'API"""
    return {
        "status": "healthy",
        "supabase_configured": supabase is not None,
        "timestamp": datetime.now().isoformat() + "Z"
    }

@app.get("/api/debug/env")
async def debug_env():
    """Debug des variables d'environnement"""
    return {
        "supabase_url": SUPABASE_URL[:50] + "..." if SUPABASE_URL else None,
        "supabase_key_length": len(SUPABASE_KEY) if SUPABASE_KEY else 0,
        "supabase_key_start": SUPABASE_KEY[:20] + "..." if SUPABASE_KEY else None,
        "url_valid": bool(SUPABASE_URL and SUPABASE_URL.startswith("https://")),
        "key_valid": bool(SUPABASE_KEY and len(SUPABASE_KEY) > 100),
        "all_env_vars": list(os.environ.keys())
    }

@app.get("/api/debug/supabase")
async def debug_supabase():
    """Debug complet de Supabase"""
    try:
        result = {
            "supabase_url": SUPABASE_URL,
            "supabase_key_length": len(SUPABASE_KEY) if SUPABASE_KEY else 0,
            "supabase_key_start": SUPABASE_KEY[:20] + "..." if SUPABASE_KEY else None,
            "url_valid": bool(SUPABASE_URL and SUPABASE_URL.startswith("https://")),
            "supabase_configured": False,
            "supabase_available": False,
            "supabase_error": None
        }
        
        if not SUPABASE_URL or not SUPABASE_KEY:
            result["supabase_error"] = "Missing SUPABASE_URL or SUPABASE_KEY"
            return result
        
        # Test de création du client Supabase - SANS PROXY
        test_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        result["supabase_available"] = True
        result["supabase_configured"] = True
        
        return result
        
    except Exception as e:
        result["supabase_error"] = str(e)
        return result

@app.get("/api/test")
async def test_api():
    """Test général de l'API"""
    return {
        "api_status": "working",
        "supabase_status": "configured" if supabase else "not_configured",
        "timestamp": datetime.now().isoformat()
    }

# Routes pour les événements
@app.get("/api/events")
async def get_events():
    """Récupère tous les événements"""
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")
    
    try:
        response = supabase.table("events").select("*").execute()
        return {"events": response.data}
    except Exception as e:
        logger.error(f"Error fetching events: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/events")
async def create_event(event_data: Dict[str, Any]):
    """Crée un nouvel événement"""
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")
    
    try:
        response = supabase.table("events").insert(event_data).execute()
        return {"message": "Event created successfully", "data": response.data}
    except Exception as e:
        logger.error(f"Error creating event: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Routes pour les métriques
@app.get("/api/metrics")
async def get_metrics():
    """Récupère toutes les métriques"""
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")
    
    try:
        response = supabase.table("metrics").select("*").execute()
        return {"metrics": response.data}
    except Exception as e:
        logger.error(f"Error fetching metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/metrics")
async def create_metric(metric_data: Dict[str, Any]):
    """Crée une nouvelle métrique"""
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")
    
    try:
        response = supabase.table("metrics").insert(metric_data).execute()
        return {"message": "Metric created successfully", "data": response.data}
    except Exception as e:
        logger.error(f"Error creating metric: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
