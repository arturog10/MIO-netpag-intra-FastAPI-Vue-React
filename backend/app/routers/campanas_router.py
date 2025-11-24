import logging
import os
import pandas as pd
import numpy as np
import zipfile
import io
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.engine import Connection
from sqlalchemy import text
from typing import Annotated
from pydantic import BaseModel

from app.database import get_db_session
from app.auth_security import get_current_user_email
from app.db_plantillas_operations import (
    listar_plantillas_db, 
    cargar_plantilla_db, 
    guardar_plantilla_db, 
    actualizar_plantilla_db
)
import app.db_operations as db_ops 
import app.db_user_operations as db_users # <--- IMPORTANTE: Para registrar auditoría
from app.pipelines.pipeline_campana import ejecutar_pipeline_campana, tasks_db

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/campanas",
    tags=["Campanas"]
)

def get_b2c_db():
    yield from get_db_session("b2c")

B2CSession = Annotated[Connection, Depends(get_b2c_db)]

# --- Modelos para Descarga ---
class ZipDownloadRequest(BaseModel):
    files: list[str]

# --- ENDPOINTS CRUD (Plantillas) ---

@router.get("/plantillas")
async def listar_plantillas(db: B2CSession):
    try:
        return listar_plantillas_db(db)
    except Exception as e:
        logger.error(f"Error al listar plantillas: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@router.get("/plantillas/{id}")
async def obtener_plantilla(id: int, db: B2CSession):
    try:
        p = cargar_plantilla_db(db, id)
        if not p: 
            logger.warning(f"Plantilla {id} no encontrada.")
            raise HTTPException(status_code=404, detail="Plantilla no encontrada")
        return p
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Error al obtener plantilla {id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@router.post("/plantillas")
async def crear_plantilla(req: dict, db: B2CSession, user: str = Depends(get_current_user_email)):
    try:
        id_new = guardar_plantilla_db(db, req, user)
        
        # --- AUDITORÍA ---
        try:
            db_users.registrar_accion_db(
                db, user, "crear_plantilla_campana", 
                {"nombre": req.get("nombre_plantilla"), "id_generado": id_new}
            )
        except Exception as audit_err:
            logger.error(f"Error auditoría crear plantilla: {audit_err}")

        logger.info(f"Plantilla creada con ID {id_new} por {user}")
        return {"id": id_new, "message": "Plantilla creada correctamente"}
    except Exception as e:
        logger.error(f"Error al crear plantilla: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error al guardar: {str(e)}")

@router.put("/plantillas/{id}")
async def editar_plantilla(id: int, req: dict, db: B2CSession, user: str = Depends(get_current_user_email)):
    try:
        # Obtener ID usuario
        user_id = 0
        try:
            user_row = db.execute(text("SELECT id FROM B2C.dbo.Usuarios WHERE email = :email"), {"email": user}).fetchone()
            user_id = user_row[0] if user_row else 0
        except: pass

        nombre = req.get("nombre_plantilla")
        id_estrategia = req.get("id_estrategia_base")
        reglas_val = req.get("reglas_validacion_json")
        reglas_proc = req.get("reglas_procesamiento_json")
        modo = req.get("modo_salida")

        actualizar_plantilla_db(db, id, nombre, id_estrategia, reglas_val, reglas_proc, modo, user_id, user)
        
        # --- AUDITORÍA ---
        try:
            db_users.registrar_accion_db(
                db, user, "editar_plantilla_campana", 
                {"id_plantilla": id, "nuevo_nombre": nombre}
            )
        except Exception as audit_err:
            logger.error(f"Error auditoría editar plantilla: {audit_err}")

        logger.info(f"Plantilla {id} actualizada por {user}")
        return {"message": "Plantilla actualizada correctamente"}
    except Exception as e:
        logger.error(f"Error al actualizar plantilla {id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error al actualizar: {str(e)}")

# --- ENDPOINTS EJECUCIÓN ---

@router.post("/ejecutar/{id_plantilla}")
async def ejecutar_campana(
    id_plantilla: int, 
    background_tasks: BackgroundTasks,
    db: B2CSession, # Inyectamos DB para auditoría
    user: str = Depends(get_current_user_email)
):
    try:
        import uuid
        task_id = str(uuid.uuid4())
        tasks_db[task_id] = {"status": "running", "user_email": user}
        
        # --- AUDITORÍA ---
        try:
            plantilla = cargar_plantilla_db(db, id_plantilla)
            nombre_p = plantilla["nombre_plantilla"] if plantilla else "Desconocida"
            
            db_users.registrar_accion_db(
                db, user, "ejecutar_campana", 
                {"id_plantilla": id_plantilla, "nombre_plantilla": nombre_p, "task_id": task_id}
            )
        except Exception as audit_err:
            logger.error(f"Error auditoría ejecutar: {audit_err}")

        logger.info(f"Iniciando tarea {task_id} para plantilla {id_plantilla} (Usuario: {user})")
        background_tasks.add_task(ejecutar_pipeline_campana, id_plantilla, task_id, "b2c")
        
        return {"task_id": task_id}
    except Exception as e:
        logger.error(f"Error al iniciar ejecución de campaña {id_plantilla}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error al iniciar proceso: {str(e)}")

@router.get("/status/{task_id}")
async def get_status(task_id: str):
    task = tasks_db.get(task_id)
    if not task: raise HTTPException(status_code=404, detail="Tarea no encontrada")
    return task

@router.get("/resultados/{task_id}")
async def get_resultados(task_id: str):
    task = tasks_db.get(task_id)
    if not task: raise HTTPException(status_code=404)
    if task["status"] != "complete": raise HTTPException(status_code=400, detail="No completada")
    return {"resultados": task["data"]}

@router.post("/cancel/{task_id}")
async def cancel_task(
    task_id: str, 
    db: B2CSession,
    user: str = Depends(get_current_user_email)
):
    try:
        task = tasks_db.get(task_id)
        if not task: raise HTTPException(status_code=404, detail="Tarea no encontrada")
        
        if task.get("user_email") != user:
             logger.warning(f"Usuario {user} intentó cancelar tarea {task_id} de {task.get('user_email')}")
        
        task["status"] = "cancelled"
        
        # --- AUDITORÍA ---
        try:
            db_users.registrar_accion_db(
                db, user, "cancelar_campana", 
                {"task_id": task_id}
            )
        except: pass

        logger.info(f"Solicitud de cancelación para tarea {task_id} recibida de {user}")
        return {"message": "Cancelación solicitada"}
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Error al cancelar tarea {task_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# --- DESCARGAS Y PREVIEW (CON AUDITORÍA) ---

@router.post("/download-zip")
async def download_zip(
    req: ZipDownloadRequest, 
    db: B2CSession,
    user: str = Depends(get_current_user_email)
):
    """Genera y descarga un ZIP con auditoría."""
    base_dir = "campanas_generadas"
    
    try:
        # --- AUDITORÍA ---
        try:
            db_users.registrar_accion_db(
                db, user, "descargar_zip_campana", 
                {"cantidad_archivos": len(req.files), "archivos": str(req.files)[:200]}
            )
        except: pass

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for file_rel_path in req.files:
                if ".." in file_rel_path: continue
                full_path = os.path.join(base_dir, file_rel_path)
                if os.path.exists(full_path):
                    zip_file.write(full_path, arcname=os.path.basename(full_path))
        
        zip_buffer.seek(0)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"campana_pack_{timestamp}.zip"
        
        return StreamingResponse(
            zip_buffer, 
            media_type="application/zip", 
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        logger.error(f"Error generando ZIP: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error generando archivo ZIP.")

@router.get("/download-file")
async def download_file(
    file_path: str, 
    db: B2CSession,
    user: str = Depends(get_current_user_email)
):
    """Descarga un archivo individual con auditoría."""
    base_dir = "campanas_generadas"
    if ".." in file_path: raise HTTPException(status_code=400, detail="Ruta inválida")
    
    full_path = os.path.join(base_dir, file_path)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
        
    # --- AUDITORÍA ---
    try:
        db_users.registrar_accion_db(
            db, user, "descargar_archivo_campana", 
            {"archivo": os.path.basename(full_path)}
        )
    except: pass

    return FileResponse(
        path=full_path, 
        filename=os.path.basename(full_path), 
        media_type='application/octet-stream'
    )

@router.get("/check-existing/{id_plantilla}")
async def check_existing_files(id_plantilla: int, db: B2CSession):
    try:
        plantilla = cargar_plantilla_db(db, id_plantilla)
        if not plantilla: raise HTTPException(status_code=404)
        estrategia = db_ops.cargar_una_estrategia_db(db, plantilla["id_estrategia_base"])
        if not estrategia: raise HTTPException(status_code=404)
        cliente = estrategia["codigo_cliente"]
        
        now = datetime.now()
        target_dir = os.path.join("campanas_generadas", cliente, now.strftime("%d%m%Y"))
        
        files = []
        if os.path.exists(target_dir):
             for f in os.listdir(target_dir):
                 if f.endswith(".csv") or f.endswith(".xlsx"):
                     files.append(f"{cliente}/{now.strftime('%d%m%Y')}/{f}")
        return {"files": files}
    except Exception as e:
        logger.error(f"Error check files: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/preview")
async def get_file_preview(file_path: str, user: str = Depends(get_current_user_email)):
    base_dir = "campanas_generadas"
    if ".." in file_path: raise HTTPException(status_code=400)
    full_path = os.path.join(base_dir, file_path)
    if not os.path.exists(full_path): raise HTTPException(status_code=404)

    try:
        df = pd.read_csv(full_path, sep=';', encoding='utf-8-sig', nrows=10)
        df = df.replace({np.nan: None})
        return df.to_dict(orient="records")
    except Exception as e:
        logger.error(f"Error preview: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))