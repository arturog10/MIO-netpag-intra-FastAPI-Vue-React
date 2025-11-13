import logging
import uuid
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.engine import Connection
from typing import List, Annotated
from pydantic import BaseModel

# Importaciones de nuestro proyecto
from app.models import PlantillaSaveRequest, PlantillaResponse, GruposUnicosRequest
from app import db_plantillas_operations as db_plantillas
from app import db_user_operations as db_users
from app import db_operations # Necesario para buscar grupos únicos
from app.auth_security import get_current_user_email
from app.database import get_db_session

# Importar la lógica del pipeline
from app.pipeline_campana import ejecutar_pipeline_campana, tasks_db

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/campanas",
    tags=["Campanas"],
    dependencies=[Depends(get_current_user_email)] 
)

# --- Dependencias de DB ---
def get_b2c_db():
    yield from get_db_session("b2c") 

B2CDBSession = Annotated[Connection, Depends(get_b2c_db)]
CurrentUserEmail = Annotated[str, Depends(get_current_user_email)] 

# --- ENDPOINTS DE GESTIÓN DE PLANTILLAS ---

@router.get("/plantillas", response_model=List[dict])
def get_plantillas_list(db: B2CDBSession):
    """Obtiene la lista de todas las plantillas guardadas."""
    try:
        return db_plantillas.listar_plantillas_db(db)
    except Exception as e:
        logger.error(f"Error al listar plantillas: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al obtener plantillas.")

@router.post("/plantillas")
def save_plantilla(
    req: PlantillaSaveRequest,
    db: B2CDBSession,
    current_user_email: CurrentUserEmail
):
    """Guarda una NUEVA plantilla de campaña."""
    try:
        # Verificar si ya existe
        existe = db_plantillas.plantilla_existe_db(db, req.nombre_plantilla)
        if existe:
            raise HTTPException(status_code=409, detail="Ya existe una plantilla con ese nombre.")
            
        id_usuario = db_users.get_user_id_by_email(db, current_user_email)
        
        success = db_plantillas.guardar_plantilla_db(
            db_session=db,
            nombre_plantilla=req.nombre_plantilla,
            id_estrategia_base=req.id_estrategia_base,
            reglas_validacion_json=req.reglas_validacion_json,
            reglas_procesamiento_json=req.reglas_procesamiento_json,
            modo_salida=req.modo_salida,
            id_usuario_creador=id_usuario,
            usuario_creador=current_user_email
        )
        if not success:
            raise HTTPException(status_code=500, detail="No se pudo guardar la plantilla.")
            
        return {"status": "Plantilla guardada con éxito"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al guardar plantilla: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno al guardar la plantilla.")

# (Aquí irían los endpoints PUT para actualizar y DELETE para borrar)

# --- ENDPOINTS DE EJECUCIÓN ASÍNCRONA (Como Trazabilidad) ---

@router.post("/ejecutar/{id_plantilla}")
async def ejecutar_campana(
    id_plantilla: int,
    background_tasks: BackgroundTasks,
    current_user_email: CurrentUserEmail
):
    """Inicia la ejecución asíncrona de un pipeline de campaña."""
    task_id = str(uuid.uuid4())
    tasks_db[task_id] = {"status": "running", "data": None}
    
    # Obtenemos la db_key de la conexión 'b2c' para pasarla a la tarea
    db_key_b2c = "b2c" 
    
    background_tasks.add_task(ejecutar_pipeline_campana, id_plantilla, task_id, db_key_b2c)
    
    logger.info(f"Tarea de campaña {task_id} iniciada por {current_user_email}.")
    return {"task_id": task_id}

@router.get("/status/{task_id}")
async def get_task_status(task_id: str):
    """Sondea el estado de una tarea de campaña en ejecución."""
    task = tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarea no encontrada.")
    return {"status": task["status"], "error": task.get("error_message")}

@router.get("/resultados/{task_id}")
async def get_task_results(task_id: str):
    """Obtiene los resultados (lista de archivos) de una tarea completada."""
    task = tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarea no encontrada.")
    if task["status"] != "complete":
        raise HTTPException(status_code=400, detail=f"La tarea no está completa. Estado: {task['status']}")
    
    return {"resultados": task["data"]}

@router.put("/plantillas/{id_plantilla}")
def update_plantilla(
    id_plantilla: int,
    req: PlantillaSaveRequest,
    db: B2CDBSession,
    current_user_email: CurrentUserEmail
):
    """Actualiza una plantilla existente."""
    try:
        id_usuario = db_users.get_user_id_by_email(db, current_user_email)
        
        success = db_plantillas.actualizar_plantilla_db(
            db_session=db,
            id_plantilla=id_plantilla,
            nombre_plantilla=req.nombre_plantilla,
            id_estrategia_base=req.id_estrategia_base,
            reglas_validacion_json=req.reglas_validacion_json,
            reglas_procesamiento_json=req.reglas_procesamiento_json,
            modo_salida=req.modo_salida,
            id_usuario_creador=id_usuario,
            usuario_creador=current_user_email
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="No se encontró la plantilla para actualizar.")
            
        return {"status": "Plantilla actualizada con éxito"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al actualizar plantilla: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno al actualizar la plantilla.")
    
@router.get("/plantillas/{id_plantilla}")
def get_plantilla_detail(id_plantilla: int, db: B2CDBSession):
    plantilla = db_plantillas.cargar_plantilla_db(db, id_plantilla)
    if not plantilla:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    return plantilla    