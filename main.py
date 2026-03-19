from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
from supabase import create_client, Client
import logging

# Configuration des logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# IMPORTANT: Variable app pour Vercel
app = FastAPI(title="PulseBoard API", version="1.0.0")

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase_client = None

def init_supabase():
    global supabase_client
    try:
        if SUPABASE_URL and SUPABASE_KEY:
            # Création simple du client Supabase
            supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
            logger.info("Supabase client initialized successfully")
            return True
        else:
            logger.error("Missing Supabase credentials")
            return False
    except Exception as e:
        logger.error(f"Failed to initialize Supabase: {str(e)}")
        return False

# Initialisation au démarrage
@app.on_event("startup")
async def startup_event():
    init_supabase()

# Route de santé
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "supabase_configured": supabase_client is not None,
        "timestamp": "2024-03-19T14:58:00Z"
    }

# Route de debug Supabase
@app.get("/api/debug/supabase")
async def debug_supabase():
    try:
        # Test de base
        debug_info = {
            "supabase_url": SUPABASE_URL,
            "supabase_key_length": len(SUPABASE_KEY) if SUPABASE_KEY else 0,
            "supabase_key_start": SUPABASE_KEY[:20] + "..." if SUPABASE_KEY else None,
            "url_valid": bool(SUPABASE_URL and SUPABASE_URL.startswith("https://")),
            "supabase_configured": False,
            "realtime_test": "not_attempted",
            "realtime_error": None,
            "error_type": None
        }
        
        # Test de connexion
        if SUPABASE_URL and SUPABASE_KEY:
            try:
                # Création du client
                test_client = create_client(SUPABASE_URL, SUPABASE_KEY)
                
                # Test simple - liste des tables
                result = test_client.table("users").select("*").limit(1).execute()
                
                debug_info["supabase_configured"] = True
                debug_info["realtime_test"] = "success"
                debug_info["table_test"] = "success"
                
            except Exception as e:
                debug_info["realtime_test"] = "failed"
                debug_info["realtime_error"] = str(e)
                debug_info["error_type"] = type(e).__name__
        
        return debug_info
        
    except Exception as e:
        return {
            "error": str(e),
            "error_type": type(e).__name__,
            "supabase_configured": False
        }

# Route principale
@app.get("/")
async def root():
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>PulseBoard API</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .status { padding: 20px; border-radius: 8px; margin: 20px 0; }
            .healthy { background-color: #d4edda; color: #155724; }
            .error { background-color: #f8d7da; color: #721c24; }
        </style>
    </head>
    <body>
        <h1>🚀 PulseBoard API</h1>
        <div class="status healthy">
            <h2>✅ API Active</h2>
            <p>L'API fonctionne correctement !</p>
        </div>
        
        <h3>🔗 Endpoints disponibles :</h3>
        <ul>
            <li><a href="/health">/health</a> - Vérification de santé</li>
            <li><a href="/api/debug/supabase">/api/debug/supabase</a> - Debug Supabase</li>
            <li><a href="/docs">/docs</a> - Documentation API</li>
        </ul>
        
        <div style="margin-top: 40px; padding: 20px; background-color: #f8f9fa; border-radius: 8px;">
            <h3>📊 Configuration :</h3>
            <p><strong>Supabase URL:</strong> """ + (SUPABASE_URL or "❌ Non configurée") + """</p>
            <p><strong>Supabase Key:</strong> """ + ("✅ Configurée" if SUPABASE_KEY else "❌ Non configurée") + """</p>
        </div>
    </body>
    </html>
    """)

# Route pour les données utilisateurs
@app.get("/api/users")
async def get_users():
    if not supabase_client:
        raise HTTPException(status_code=500, detail="Supabase not configured")
    
    try:
        result = supabase_client.table("users").select("*").execute()
        return {"users": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
