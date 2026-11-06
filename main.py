from pathlib import Path
from typing import Any, Dict

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import database


STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI()

app.mount("/static", StaticFiles(directory = STATIC_DIR), name = "static")


@app.post("/metrics")
async def receive_metrics(request: Request) -> Dict[str, Any]:

    try:
    
        data = await request.json()
    
    except Exception:
        raise HTTPException(status_code = 400, detail = "Invalid JSON")

    
    server_name = (data.get("server_name") or "").strip()
    
    if not server_name:
        raise HTTPException(status_code = 400, detail = "Missing server_name")

    
    required_keys = ("cpu", "memory", "swap", "storage", "network", "uptime")
    
    for key in required_keys:
        
        if key not in data:
            
            raise HTTPException(
                status_code = 400,
                detail = f"Missing required field: {key}"
            )


    try:
        server_id = database.get_or_create_server(server_name)
        
        database.insert_metrics(server_id, data)
    

    except Exception as exception:
        raise HTTPException(status_code = 500, detail = f"Database error: {exception}")

    
    return {"status": "ok", "server_id": server_id}


@app.get("/servers")
async def list_servers() -> list:
    
    return database.list_servers()


@app.get("/servers/{server_id}/metrics")
async def server_metrics(server_id: int) -> Dict[str, Any]:

    metrics = database.get_latest_metrics(server_id)
    
    if not metrics:
        raise HTTPException(status_code = 404, detail = "No metrics for this server yet")
    
    return metrics


@app.get("/metrics")
async def all_latest_metrics() -> list:
    return database.get_all_latest_metrics()


@app.post("/admin/cleanup")
async def cleanup_metrics(keep: int = 500) -> Dict[str, Any]:

    deleted = database.cleanup_old_metrics(keep_per_server = keep)
    
    return {"deleted": deleted, "keep_per_server": keep}


@app.get("/")
async def root():

    index_path = STATIC_DIR / "index.html"
    
    return FileResponse(index_path)


if __name__ == "__main__":
    
    print("Starting HostMetrics...")
    
    uvicorn.run(
        "main:app",
        host = "0.0.0.0",
        port = 8000
    )