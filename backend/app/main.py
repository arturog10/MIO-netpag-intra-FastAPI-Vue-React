import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware # IMPORTANTE para frontend
from .logging_config import setup_logging
from app.config import config

# --- Importamos nuestros routers ---
from .routers import (data_visor,auth_router, admin_router,trazabilidad_router, listanegra_router, campanas_router)


# =======================================================
setup_logging()
# =======================================================

log = logging.getLogger(__name__)
app = FastAPI()

# --- Configurar CORS ---
# Esto es VITAL para que tu frontend (ej: localhost:5173) 
# se comunique con tu backend (ej: localhost:8000).
origins = [
    "http://localhost",
    "http://localhost:5173",  # Puerto por defecto de Vite (Vue/React)
    "http://localhost:3000",  # Puerto por defecto de create-react-app
    "http://localhost:80",  # Puerto por defecto de create-react-app
    "http://192.168.168.35:8080",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Incluimos las rutas del visor ---
app.include_router(data_visor.router)
app.include_router(auth_router.router)
app.include_router(admin_router.router)
app.include_router(trazabilidad_router.router)
app.include_router(listanegra_router.router)
app.include_router(campanas_router.router)




# --- Tus rutas de prueba (puedes mantenerlas) ---
@app.get("/")
def read_root():
    log.info("Accediendo a la ruta raíz /")
    return {"message": "¡Hola desde FastAPI con logging!"}

@app.get("/test-db")
def test_database_connection():
    # ... (tu código de prueba de conexión) ...
    log.info("Iniciando prueba de conexión...")
    results = {}
    # ... (etc) ...
    return {"status": "Prueba completada", "resultados": results}