import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import httpx
from datetime import datetime
import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import logging

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="PulseBoard", version="1.0.0")

# Configuration des templates
templates = Jinja2Templates(directory="templates")

# Configuration Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Client Supabase global
supabase_client = None

def init_supabase():
    """Initialise le client Supabase de manière sécurisée"""
    global supabase_client
    try:
        if not SUPABASE_URL or not SUPABASE_KEY:
            logger.error("Variables Supabase manquantes")
            return False
            
        from supabase import create_client
        
        # Création du client SANS paramètres problématiques
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Test simple de connexion
        result = supabase_client.table("pulse_data").select("*").limit(1).execute()
        logger.info("Supabase connecté avec succès")
        return True
        
    except Exception as e:
        logger.error(f"Erreur Supabase: {str(e)}")
        supabase_client = None
        return False

# Initialisation au démarrage
supabase_configured = init_supabase()

# Modèles Pydantic
class PulseData(BaseModel):
    timestamp: str
    heart_rate: int
    blood_pressure_systolic: int
    blood_pressure_diastolic: int
    temperature: float
    oxygen_saturation: int

class HealthMetrics(BaseModel):
    avg_heart_rate: float
    avg_temperature: float
    avg_oxygen_saturation: float
    latest_blood_pressure: Dict[str, int]
    total_readings: int

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Page principale du dashboard"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/health")
async def health_check():
    """Endpoint de vérification de santé"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "supabase_configured": supabase_configured,
        "version": "1.0.0"
    }

@app.get("/api/debug/supabase")
async def debug_supabase():
    """Debug détaillé de Supabase"""
    try:
        debug_info = {
            "supabase_url": SUPABASE_URL,
            "supabase_key_length": len(SUPABASE_KEY) if SUPABASE_KEY else 0,
            "supabase_key_start": SUPABASE_KEY[:20] + "..." if SUPABASE_KEY else None,
            "url_valid": bool(SUPABASE_URL and SUPABASE_URL.startswith("https://")),
            "supabase_configured": supabase_configured
        }
        
        # Test de connexion en temps réel
        if supabase_client:
            try:
                result = supabase_client.table("pulse_data").select("*").limit(1).execute()
                debug_info["connection_test"] = "success"
                debug_info["table_accessible"] = True
            except Exception as e:
                debug_info["connection_test"] = "failed"
                debug_info["connection_error"] = str(e)
                debug_info["error_type"] = type(e).__name__
        else:
            debug_info["connection_test"] = "no_client"
            
        return debug_info
        
    except Exception as e:
        return {
            "error": str(e),
            "error_type": type(e).__name__,
            "supabase_configured": False
        }

@app.post("/api/pulse")
async def add_pulse_data(data: PulseData):
    """Ajouter des données de pouls"""
    if not supabase_configured or not supabase_client:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    
    try:
        # Insérer les données
        result = supabase_client.table("pulse_data").insert({
            "timestamp": data.timestamp,
            "heart_rate": data.heart_rate,
            "blood_pressure_systolic": data.blood_pressure_systolic,
            "blood_pressure_diastolic": data.blood_pressure_diastolic,
            "temperature": data.temperature,
            "oxygen_saturation": data.oxygen_saturation
        }).execute()
        
        return {"status": "success", "data": result.data}
        
    except Exception as e:
        logger.error(f"Erreur insertion: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/pulse/latest")
async def get_latest_pulse_data(limit: int = 10):
    """Récupérer les dernières données de pouls"""
    if not supabase_configured or not supabase_client:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    
    try:
        result = supabase_client.table("pulse_data")\
            .select("*")\
            .order("timestamp", desc=True)\
            .limit(limit)\
            .execute()
        
        return {"status": "success", "data": result.data}
        
    except Exception as e:
        logger.error(f"Erreur récupération: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/metrics")
async def get_health_metrics():
    """Calculer et retourner les métriques de santé"""
    if not supabase_configured or not supabase_client:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    
    try:
        # Récupérer toutes les données
        result = supabase_client.table("pulse_data").select("*").execute()
        data = result.data
        
        if not data:
            return {"status": "no_data", "metrics": None}
        
        # Calculer les métriques
        total_readings = len(data)
        avg_heart_rate = sum(item["heart_rate"] for item in data) / total_readings
        avg_temperature = sum(item["temperature"] for item in data) / total_readings
        avg_oxygen_saturation = sum(item["oxygen_saturation"] for item in data) / total_readings
        
        # Dernière tension artérielle
        latest_bp = {
            "systolic": data[0]["blood_pressure_systolic"],
            "diastolic": data[0]["blood_pressure_diastolic"]
        }
        
        metrics = HealthMetrics(
            avg_heart_rate=round(avg_heart_rate, 1),
            avg_temperature=round(avg_temperature, 1),
            avg_oxygen_saturation=round(avg_oxygen_saturation, 1),
            latest_blood_pressure=latest_bp,
            total_readings=total_readings
        )
        
        return {"status": "success", "metrics": metrics.dict()}
        
    except Exception as e:
        logger.error(f"Erreur métriques: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/pulse/chart-data")
async def get_chart_data(hours: int = 24):
    """Récupérer les données pour les graphiques"""
    if not supabase_configured or not supabase_client:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    
    try:
        result = supabase_client.table("pulse_data")\
            .select("*")\
            .order("timestamp", desc=True)\
            .limit(hours * 6)\  # Approximativement 6 mesures par heure
            .execute()
        
        return {"status": "success", "data": result.data}
        
    except Exception as e:
        logger.error(f"Erreur données graphique: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Gestion des erreurs globales
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=404,
        content={"error": "Endpoint not found", "path": str(request.url.path)}
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception):
    logger.error(f"Erreur interne: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
