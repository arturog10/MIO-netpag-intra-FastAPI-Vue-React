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
from app import db_operations 
from app.auth_security import get_current_user_email, get_current_admin_user # <-- 1. IMPORTAR ADMIN USER
from app.database import get_db_session

# Importar la lógica del pipeline

from app.pipelines.pipeline_campana import ejecutar_pipeline_campana, tasks_db


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/campanas",
    tags=["Campanas"],
    # dependencies=[Depends(get_current_user_email)] # <-- QUITAMOS LA DEPENDENCIA GLOBAL (algunas rutas requieren admin)
)

# --- Dependencias de DB ---
def get_b2c_db():
    yield from get_db_session("b2c") 

B2CDBSession = Annotated[Connection, Depends(get_b2c_db)]
CurrentUserEmail = Annotated[str, Depends(get_current_user_email)] 
CurrentAdminUser = Annotated[str, Depends(get_current_admin_user)] # <-- 2. NUEVA ANOTACIÓN

# --- ENDPOINTS DE GESTIÓN DE PLANTILLAS ---

@router.get("/plantillas", response_model=List[dict])
def get_plantillas_list(db: B2CDBSession, current_user: str = Depends(get_current_user_email)): # Visible para todos
    """Obtiene la lista de todas las plantillas guardadas."""
    try:
        return db_plantillas.listar_plantillas_db(db)
    except Exception as e:
        logger.error(f"Error al listar plantillas: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al obtener plantillas.")

@router.get("/plantillas/{id_plantilla}")
def get_plantilla_detail(id_plantilla: int, db: B2CDBSession, current_user: str = Depends(get_current_user_email)): # Visible para todos
    plantilla = db_plantillas.cargar_plantilla_db(db, id_plantilla)
    if not plantilla:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    return plantilla

# --- RUTAS PROTEGIDAS SOLO PARA ADMIN ---

@router.post("/plantillas")
def save_plantilla(
    req: PlantillaSaveRequest,
    db: B2CDBSession,
    current_user_email: CurrentAdminUser # <-- 3. SOLO ADMIN PUEDE GUARDAR
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

@router.put("/plantillas/{id_plantilla}")
def update_plantilla(
    id_plantilla: int,
    req: PlantillaSaveRequest,
    db: B2CDBSession,
    current_user_email: CurrentAdminUser # <-- 4. SOLO ADMIN PUEDE EDITAR
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

# --- ENDPOINTS DE EJECUCIÓN ASÍNCRONA (Disponibles para todos) ---

@router.post("/ejecutar/{id_plantilla}")
async def ejecutar_campana(
    id_plantilla: int,
    background_tasks: BackgroundTasks,
    current_user_email: CurrentUserEmail # <-- 5. CUALQUIER USUARIO PUEDE EJECUTAR
):
    """Inicia la ejecución asíncrona de un pipeline de campaña."""
    task_id = str(uuid.uuid4())
    tasks_db[task_id] = {"status": "running", "data": None}
    
    db_key_b2c = "b2c" 
    
    background_tasks.add_task(ejecutar_pipeline_campana, id_plantilla, task_id, db_key_b2c)
    
    logger.info(f"Tarea de campaña {task_id} iniciada por {current_user_email}.")
    return {"task_id": task_id}

@router.get("/status/{task_id}")
async def get_task_status(task_id: str, current_user: str = Depends(get_current_user_email)):
    """Sondea el estado de una tarea de campaña en ejecución."""
    task = tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarea no encontrada.")
    return {"status": task["status"], "error": task.get("error_message")}

@router.get("/resultados/{task_id}")
async def get_task_results(task_id: str, current_user: str = Depends(get_current_user_email)):
    """Obtiene los resultados (lista de archivos) de una tarea completada."""
    task = tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarea no encontrada.")
    if task["status"] != "complete":
        raise HTTPException(status_code=400, detail=f"La tarea no está completa. Estado: {task['status']}")
    
    return {"resultados": task["data"]}

@router.post("/cancel/{task_id}")
async def cancel_campana_task(
    task_id: str,
    audit_db: B2CDBSession,
    current_user_email: CurrentUserEmail
):
    """
    Intenta cancelar una tarea en ejecución o limpia una tarea completada/errónea.
    """
    task = tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarea no encontrada.")
    
    status = task.get("status")

    if status == "running":
        tasks_db[task_id]["status"] = "cancelled"
        logger.info(f"Cancelación solicitada para la tarea {task_id} por {current_user_email}.")
        
        # Auditoría de cancelación
        try:
            db_users.registrar_accion_db(audit_db, current_user_email, "cancelar_campana", {"task_id": task_id})
        except Exception as e_audit:
            logger.error(f"Error al registrar auditoría (cancelar_campana): {e_audit}")
            
        return {"status": "cancellation_requested"}
    
    if status in ["complete", "error", "cancelled"]:
        # Si la tarea ya terminó o ya está cancelada, esta llamada la limpia de memoria
        tasks_db.pop(task_id, None)
        logger.info(f"Tarea {task_id} (estado: {status}) limpiada de la memoria por {current_user_email}.")
        return {"status": "cleared"}
    
    return {"status": status}