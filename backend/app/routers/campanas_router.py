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
    actualizar_plantilla_db,
    eliminar_plantilla_db
)
import app.db_operations as db_ops 
import app.db_user_operations as db_users
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
async def listar_plantillas(db: B2CSession, user: str = Depends(get_current_user_email)):
    try:
        es_admin = False
        try:
            row = db.execute(text("SELECT rol FROM B2C.dbo.Usuarios WHERE email = :e"), {"e": user}).fetchone()
            if row and row[0] == 'admin': es_admin = True
        except: pass
        
        return listar_plantillas_db(db, es_admin=es_admin)
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
        user_id = 0
        try:
            user_row = db.execute(text("SELECT id_usuario FROM B2C.dbo.Usuarios WHERE email = :email"), {"email": user}).fetchone()
            user_id = user_row[0] if user_row else 0
        except: pass

        nombre = req.get("nombre_plantilla")
        id_estrategia = req.get("id_estrategia_base")
        reglas_val = req.get("reglas_validacion_json")
        reglas_proc = req.get("reglas_procesamiento_json")
        modo = req.get("modo_salida")

        id_new = guardar_plantilla_db(db, nombre, id_estrategia, reglas_val, reglas_proc, modo, user_id, user)
        
        try: db_users.registrar_accion_db(db, user, "crear_plantilla_campana", {"nombre": nombre, "id_generado": id_new})
        except: pass

        logger.info(f"Plantilla creada con ID {id_new} por {user}")
        return {"id": id_new, "message": "Plantilla creada correctamente"}
    except Exception as e:
        logger.error(f"Error al crear plantilla: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error al guardar: {str(e)}")

@router.put("/plantillas/{id}")
async def editar_plantilla(id: int, req: dict, db: B2CSession, user: str = Depends(get_current_user_email)):
    try:
        user_id = 0
        try:
            user_row = db.execute(text("SELECT id_usuario FROM B2C.dbo.Usuarios WHERE email = :email"), {"email": user}).fetchone()
            user_id = user_row[0] if user_row else 0
        except: pass

        nombre = req.get("nombre_plantilla")
        id_estrategia = req.get("id_estrategia_base")
        reglas_val = req.get("reglas_validacion_json")
        reglas_proc = req.get("reglas_procesamiento_json")
        modo = req.get("modo_salida")

        actualizar_plantilla_db(db, id, nombre, id_estrategia, reglas_val, reglas_proc, modo, user_id, user)
        
        try: db_users.registrar_accion_db(db, user, "editar_plantilla_campana", {"id_plantilla": id, "nuevo_nombre": nombre})
        except: pass

        logger.info(f"Plantilla {id} actualizada por {user}")
        return {"message": "Plantilla actualizada correctamente"}
    except Exception as e:
        logger.error(f"Error al actualizar plantilla {id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error al actualizar: {str(e)}")

@router.delete("/plantillas/{id}")
async def eliminar_plantilla(id: int, db: B2CSession, user: str = Depends(get_current_user_email)):
    try:
        row = db.execute(text("SELECT rol, id_usuario FROM B2C.dbo.Usuarios WHERE email = :e"), {"e": user}).fetchone()
        if not row or row[0] != 'admin':
            raise HTTPException(status_code=403, detail="Solo administradores pueden eliminar plantillas.")
        
        user_id = row[1]
        eliminar_plantilla_db(db, id, user_id, user)
        
        try: db_users.registrar_accion_db(db, user, "eliminar_plantilla", {"id_plantilla": id})
        except: pass

        return {"message": "Plantilla eliminada correctamente"}
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Error al eliminar plantilla {id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/plantillas/{id}/estado")
async def cambiar_estado_plantilla(id: int, payload: dict, db: B2CSession, user: str = Depends(get_current_user_email)):
    try:
        from app.db_plantillas_operations import cambiar_estado_plantilla_db
        
        row = db.execute(text("SELECT rol, id_usuario FROM B2C.dbo.Usuarios WHERE email = :e"), {"e": user}).fetchone()
        if not row or row[0] != 'admin':
            raise HTTPException(status_code=403, detail="Solo administradores pueden cambiar el estado.")
        
        user_id = row[1]
        nuevo_estado = payload.get("estado")
        if nuevo_estado not in [0, 1]: raise HTTPException(status_code=400, detail="Estado inválido")

        cambiar_estado_plantilla_db(db, id, nuevo_estado, user_id, user)
        
        try: db_users.registrar_accion_db(db, user, "cambiar_estado_plantilla", {"id_plantilla": id, "nuevo_estado": nuevo_estado})
        except: pass

        return {"message": "Estado actualizado"}
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Error cambiando estado: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# --- ENDPOINTS EJECUCIÓN (CON VALIDACIÓN DE CONCURRENCIA) ---

@router.post("/ejecutar/{id_plantilla}")
async def ejecutar_campana(
    id_plantilla: int, 
    background_tasks: BackgroundTasks, 
    db: B2CSession, 
    user: str = Depends(get_current_user_email)
):
    try:
        # 1. VALIDACIÓN DE CONCURRENCIA
        # Recorremos las tareas en memoria para ver si este usuario ya tiene una corriendo
        for t_id, t_data in tasks_db.items():
            if t_data.get("user_email") == user and t_data.get("status") == "running":
                logger.warning(f"Usuario {user} intentó ejecutar múltiples campañas simultáneamente.")
                raise HTTPException(
                    status_code=409, 
                    detail="Ya tienes una campaña en ejecución. Por favor, espera a que termine para iniciar otra."
                )

        # 2. Inicio de Tarea
        import uuid
        task_id = str(uuid.uuid4())
        tasks_db[task_id] = {"status": "running", "user_email": user, "step": "Iniciando..."}
        
        try:
            p = cargar_plantilla_db(db, id_plantilla)
            n = p["nombre_plantilla"] if p else "Unknown"
            db_users.registrar_accion_db(db, user, "ejecutar_campana", {"id_plantilla": id_plantilla, "nombre": n, "task_id": task_id})
        except: pass
        
        logger.info(f"Iniciando tarea {task_id} usuario {user}")
        background_tasks.add_task(ejecutar_pipeline_campana, id_plantilla, task_id, "b2c")
        
        return {"task_id": task_id}

    except HTTPException: raise
    except Exception as e:
        logger.error(f"Error ejecutar: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

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
async def cancel_task(task_id: str, db: B2CSession, user: str = Depends(get_current_user_email)):
    try:
        task = tasks_db.get(task_id)
        if not task: raise HTTPException(status_code=404)
        if task.get("user_email") != user: logger.warning(f"Usuario {user} intentó cancelar tarea ajena")
        
        task["status"] = "cancelled"
        task["step"] = "Cancelando..." # Feedback visual inmediato
        
        try: db_users.registrar_accion_db(db, user, "cancelar_campana", {"task_id": task_id})
        except: pass
        return {"message": "Cancelado"}
    except Exception as e:
        logger.error(f"Error cancelar: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/download-zip")
async def download_zip(req: ZipDownloadRequest, db: B2CSession, user: str = Depends(get_current_user_email)):
    base_dir = "campanas_generadas"
    try:
        try: db_users.registrar_accion_db(db, user, "descargar_zip_campana", {"archivos": len(req.files)})
        except: pass
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for f_path in req.files:
                if ".." in f_path: continue
                full = os.path.join(base_dir, f_path)
                if os.path.exists(full): zip_file.write(full, arcname=os.path.basename(full))
        zip_buffer.seek(0)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return StreamingResponse(zip_buffer, media_type="application/zip", headers={"Content-Disposition": f"attachment; filename=pack_{timestamp}.zip"})
    except Exception as e:
        logger.error(f"Error ZIP: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error ZIP")

@router.get("/download-file")
async def download_file(file_path: str, db: B2CSession, user: str = Depends(get_current_user_email)):
    base_dir = "campanas_generadas"
    if ".." in file_path: raise HTTPException(status_code=400)
    full = os.path.join(base_dir, file_path)
    if not os.path.exists(full): raise HTTPException(status_code=404)
    try: db_users.registrar_accion_db(db, user, "descargar_archivo_campana", {"archivo": os.path.basename(full)})
    except: pass
    return FileResponse(path=full, filename=os.path.basename(full), media_type='application/octet-stream')

@router.get("/check-existing/{id_plantilla}")
async def check_existing_files(id_plantilla: int, db: B2CSession):
    try:
        p = cargar_plantilla_db(db, id_plantilla)
        if not p: raise HTTPException(status_code=404)
        e = db_ops.cargar_una_estrategia_db(db, p["id_estrategia_base"])
        if not e: raise HTTPException(status_code=404)
        c = e["codigo_cliente"]
        now = datetime.now()
        target = os.path.join("campanas_generadas", c, now.strftime("%d%m%Y"))
        files = []
        if os.path.exists(target):
             for f in os.listdir(target):
                 if f.endswith(".csv") or f.endswith(".xlsx"): files.append(f"{c}/{now.strftime('%d%m%Y')}/{f}")
        return {"files": files}
    except Exception as e:
        logger.error(f"Error check: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/preview")
async def get_file_preview(file_path: str, user: str = Depends(get_current_user_email)):
    base_dir = "campanas_generadas"
    if ".." in file_path: raise HTTPException(status_code=400)
    full = os.path.join(base_dir, file_path)
    if not os.path.exists(full): raise HTTPException(status_code=404)
    try:
        df = pd.read_csv(full, sep=';', encoding='utf-8-sig', nrows=10)
        df = df.replace({np.nan: None})
        return df.to_dict(orient="records")
    except Exception as e:
        logger.error(f"Error preview: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))