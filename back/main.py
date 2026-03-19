
import os
import asyncio
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
import httpx

# Import Supabase
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError as e:
    SUPABASE_AVAILABLE = False
    SUPABASE_IMPORT_ERROR = str(e)

app = FastAPI(title="PulseBoard API", version="1.0.0")

# CORS
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

# Variables globales
supabase_client = None
supabase_error = None

# Initialisation Supabase
if SUPABASE_AVAILABLE and SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Supabase client créé avec succès")
    except Exception as e:
        supabase_error = str(e)
        print(f"❌ Erreur création client Supabase: {e}")
else:
    if not SUPABASE_AVAILABLE:
        supabase_error = f"Supabase non disponible: {SUPABASE_IMPORT_ERROR}"
    else:
        supabase_error = "Variables d'environnement manquantes"

# Models
class Task(BaseModel):
    id: Optional[int] = None
    title: str
    description: Optional[str] = None
    status: str = "todo"
    priority: str = "medium"
    assigned_to: Optional[str] = None
    due_date: Optional[str] = None
    created_at: Optional[str] = None

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assigned_to: Optional[str] = None
    due_date: Optional[str] = None

# Routes principales
@app.get("/")
async def root():
    return {"message": "PulseBoard API is running!", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "supabase_configured": supabase_client is not None,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

# Routes de debug
@app.get("/api/debug/env")
async def debug_env():
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
    result = {
        "supabase_url": SUPABASE_URL,
        "supabase_key_length": len(SUPABASE_KEY) if SUPABASE_KEY else 0,
        "supabase_key_start": SUPABASE_KEY[:20] + "..." if SUPABASE_KEY else None,
        "url_valid": bool(SUPABASE_URL and SUPABASE_URL.startswith("https://")),
        "supabase_configured": supabase_client is not None,
        "supabase_available": SUPABASE_AVAILABLE,
        "supabase_error": supabase_error
    }
    
    # Test de connexion
    if supabase_client:
        try:
            # Test simple
            response = supabase_client.table("tasks").select("*").limit(1).execute()
            result["connection_test"] = "success"
            result["table_accessible"] = True
        except Exception as e:
            result["connection_test"] = "failed"
            result["connection_error"] = str(e)
            result["table_accessible"] = False
    
    return result

# Routes des tâches
@app.get("/api/tasks", response_model=List[Task])
async def get_tasks():
    if not supabase_client:
        raise HTTPException(status_code=503, detail="Supabase non configuré")
    
    try:
        response = supabase_client.table("tasks").select("*").execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur récupération tâches: {str(e)}")

@app.post("/api/tasks", response_model=Task)
async def create_task(task: Task):
    if not supabase_client:
        raise HTTPException(status_code=503, detail="Supabase non configuré")
    
    try:
        task_data = task.dict(exclude={'id', 'created_at'})
        response = supabase_client.table("tasks").insert(task_data).execute()
        return response.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur création tâche: {str(e)}")

@app.get("/api/tasks/{task_id}", response_model=Task)
async def get_task(task_id: int):
    if not supabase_client:
        raise HTTPException(status_code=503, detail="Supabase non configuré")
    
    try:
        response = supabase_client.table("tasks").select("*").eq("id", task_id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Tâche non trouvée")
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur récupération tâche: {str(e)}")

@app.put("/api/tasks/{task_id}", response_model=Task)
async def update_task(task_id: int, task_update: TaskUpdate):
    if not supabase_client:
        raise HTTPException(status_code=503, detail="Supabase non configuré")
    
    try:
        update_data = {k: v for k, v in task_update.dict().items() if v is not None}
        if not update_data:
            raise HTTPException(status_code=400, detail="Aucune donnée à mettre à jour")
        
        response = supabase_client.table("tasks").update(update_data).eq("id", task_id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Tâche non trouvée")
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur mise à jour tâche: {str(e)}")

@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: int):
    if not supabase_client:
        raise HTTPException(status_code=503, detail="Supabase non configuré")
    
    try:
        response = supabase_client.table("tasks").delete().eq("id", task_id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Tâche non trouvée")
        return {"message": "Tâche supprimée avec succès"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur suppression tâche: {str(e)}")

# Route de test
@app.get("/api/test")
async def test_api():
    return {
        "status": "API fonctionnelle",
        "supabase": "configuré" if supabase_client else "non configuré",
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
