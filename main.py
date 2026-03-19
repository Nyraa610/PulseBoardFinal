
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
from supabase import create_client, Client
import logging

# Configuration des logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="PulseBoard API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Variables d'environnement
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAGENDA_API_KEY = os.getenv("OPENAGENDA_API_KEY")

# Client Supabase global
supabase: Client = None

def init_supabase():
    """Initialise le client Supabase"""
    global supabase
    try:
        if not SUPABASE_URL or not SUPABASE_KEY:
            logger.error(f"Variables manquantes - URL: {bool(SUPABASE_URL)}, KEY: {bool(SUPABASE_KEY)}")
            return False
            
        logger.info(f"Tentative de connexion à Supabase: {SUPABASE_URL}")
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Test de connexion simple
        logger.info("Test de connexion Supabase...")
        result = supabase.table("test").select("*").limit(1).execute()
        logger.info(f"Test Supabase réussi: {len(result.data) if result.data else 0} résultats")
        return True
        
    except Exception as e:
        logger.error(f"Erreur Supabase: {str(e)}")
        logger.error(f"Type d'erreur: {type(e).__name__}")
        return False

# Initialisation au démarrage
supabase_connected = init_supabase()

@app.get("/")
async def root():
    return {"message": "PulseBoard API is running"}

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "supabase": "connected" if supabase_connected else "disconnected",
        "openagenda": "configured" if OPENAGENDA_API_KEY else "not configured"
    }

@app.get("/api/debug/supabase")
async def debug_supabase():
    """Debug détaillé de Supabase"""
    debug_info = {
        "supabase_url": SUPABASE_URL,
        "supabase_key_length": len(SUPABASE_KEY) if SUPABASE_KEY else 0,
        "supabase_key_start": SUPABASE_KEY[:20] + "..." if SUPABASE_KEY else None,
        "url_valid": bool(SUPABASE_URL and SUPABASE_URL.startswith("https://")),
        "supabase_configured": supabase_connected
    }
    
    # Test de connexion en temps réel
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            logger.info("Test de connexion Supabase en temps réel...")
            test_client = create_client(SUPABASE_URL, SUPABASE_KEY)
            
            # Test simple
            result = test_client.table("test").select("*").limit(1).execute()
            debug_info["realtime_test"] = "success"
            debug_info["realtime_data"] = len(result.data) if result.data else 0
            
        except Exception as e:
            debug_info["realtime_test"] = "failed"
            debug_info["realtime_error"] = str(e)
            debug_info["error_type"] = type(e).__name__
    
    return debug_info

@app.get("/api/debug/openagenda")
async def debug_openagenda():
    """Debug OpenAgenda"""
    if not OPENAGENDA_API_KEY:
        return {"error": "OpenAgenda API key not configured"}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://public.openagenda.com/v2/events",
                params={
                    "key": OPENAGENDA_API_KEY,
                    "q": "concert",
                    "size": 5
                },
                timeout=10.0
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "status": "success",
                    "total_events": data.get("total", 0),
                    "events_returned": len(data.get("events", [])),
                    "sample_event": data.get("events", [{}])[0].get("title", {}) if data.get("events") else None
                }
            else:
                return {
                    "status": "error",
                    "status_code": response.status_code,
                    "response": response.text[:500]
                }
                
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__
        }

@app.get("/api/events")
async def get_events(city: str = "Paris"):
    """Récupère les événements"""
    if not supabase_connected:
        raise HTTPException(status_code=500, detail="Supabase not connected")
    
    if not OPENAGENDA_API_KEY:
        raise HTTPException(status_code=500, detail="OpenAgenda API key not configured")
    
    try:
        # Récupération depuis OpenAgenda
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://public.openagenda.com/v2/events",
                params={
                    "key": OPENAGENDA_API_KEY,
                    "q": city,
                    "size": 20
                },
                timeout=10.0
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=500, detail=f"OpenAgenda API error: {response.status_code}")
            
            data = response.json()
            events = data.get("events", [])
            
            return {
                "total": len(events),
                "events": events[:10]  # Limite à 10 événements
            }
            
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des événements: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
