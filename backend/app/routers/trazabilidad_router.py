import logging
import uuid
import asyncio
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.engine import Connection
from typing import Annotated, Dict, Any, List
from pydantic import BaseModel
import pandas as pd
import io
from datetime import datetime

# --- Importaciones de Lógica de BD ---
from app.db_traf_operations import get_traf_columns, get_traf_data
# --- Importaciones de Autenticación y Auditoría ---
from app.auth_security import get_current_user_email
from app.database import get_db_session, get_db_session_context # <--- 1. IMPORTAR CONTEXT MANAGER
import app.db_user_operations as db_users
from app.db_operations import _get_table_info 

log = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/trazabilidad",
    tags=["Trazabilidad"],
    dependencies=[Depends(get_current_user_email)] 
)

# --- Base de datos en memoria para gestionar tareas ---
tasks_db: Dict[str, Dict[str, Any]] = {}

# --- Dependencias de Auditoría ---
def get_audit_db():
    yield from get_db_session("intranet") 

AuditDBSession = Annotated[Connection, Depends(get_audit_db)]
CurrentUserEmail = Annotated[str, Depends(get_current_user_email)]

# --- Modelos Pydantic ---
class TrafQueryRequest(BaseModel):
    sufijo: str
    fecha_desde: str
    fecha_hasta: str
    filtros: Dict[str, Any]
    visible_columns: List[str]

class TrafExportRequest(BaseModel):
    formato: str
    visible_columns: List[str]

# --- Función de Tarea de Fondo (ACTUALIZADA) ---
def run_traf_query(
    task_id: str, 
    req: TrafQueryRequest, 
    user_email: str
):
    """
    Esta función se ejecuta en segundo plano.
    AHORA usa 'get_db_session_context' para manejo seguro de conexiones.
    """
    log.info(f"[Task {task_id}] Iniciando consulta TRAF para {user_email}...")
    
    # 1. Obtener la DB Key
    try:
        table_key = "traf_masi" if req.sufijo == "MASI" else "traf_disc"
        info_tabla = _get_table_info(table_key) 
        db_key_para_traf = info_tabla["db_key"]
    except Exception as e:
        log.error(f"[Task {task_id}] Error config: {e}")
        tasks_db[task_id]["status"] = "error"
        tasks_db[task_id]["error_message"] = f"Configuración no encontrada: {e}"
        return

    try:
        # --- 2. USO DEL CONTEXT MANAGER (Más seguro y limpio) ---
        with get_db_session_context(db_key_para_traf) as db_session:
            
            # Preparar filtros
            filtros_combinados = req.filtros.copy()
            advanced_fecha = filtros_combinados.get("FECHA")
            if not (advanced_fecha and (advanced_fecha.get("desde") or advanced_fecha.get("hasta"))):
                filtros_combinados["FECHA"] = {
                    "operador": "esta_entre", 
                    "desde": req.fecha_desde, 
                    "hasta": req.fecha_hasta
                }
            
            # Obtener columnas (usando la sesión actual si fuera necesario, aunque get_traf_columns usa reflection)
            # Nota: get_traf_columns en tu código actual no recibe sesión, usa reflection directa. 
            # Si la modificamos para usar sesión, se la pasamos aquí.
            columnas_db = get_traf_columns(req.sufijo)
            
            # Filtrar columnas
            columnas_finales = [col for col in req.visible_columns if col in columnas_db]
            if not columnas_finales:
                columnas_finales = columnas_db 

            # Ejecutar consulta
            resultados_db = get_traf_data(
                db_session=db_session, # Pasamos la sesión gestionada por el context manager
                sufijo=req.sufijo,
                filtros=filtros_combinados,
                columnas=columnas_finales,
            )

            # Chequeo de cancelación
            if tasks_db.get(task_id, {}).get("status") == "cancelled":
                log.info(f"[Task {task_id}] Tarea cancelada. Abortando.")
                tasks_db.pop(task_id, None)
                return # El context manager cerrará la conexión automáticamente

            # Guardar resultados
            log.info(f"[Task {task_id}] Consulta completada. {len(resultados_db)} filas.")
            tasks_db[task_id]["status"] = "complete"
            tasks_db[task_id]["data"] = resultados_db
            tasks_db[task_id]["columns"] = columnas_finales 

    except Exception as e:
        log.error(f"[Task {task_id}] Error en tarea de fondo: {e}", exc_info=True)
        tasks_db[task_id]["status"] = "error"
        tasks_db[task_id]["error_message"] = str(e)
        # No necesitamos cerrar manual, el 'with' se encarga


# --- Endpoints ---

@router.get("/columns/{sufijo}", response_model=List[str])
async def get_columns_for_sufijo(sufijo: str):
    if sufijo not in ["MASI", "DISC"]:
        raise HTTPException(status_code=400, detail="Sufijo inválido.")
    try:
        columnas = get_traf_columns(sufijo)
        return columnas
    except Exception as e:
        log.error(f"Error al obtener columnas TRAF: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener columnas.")

@router.post("/start")
async def start_trazabilidad_query(
    req: TrafQueryRequest,
    background_tasks: BackgroundTasks,
    audit_db: AuditDBSession,
    current_user_email: CurrentUserEmail
):
    task_id = str(uuid.uuid4())
    tasks_db[task_id] = {"status": "running","user": current_user_email}

    try:
        filtros_log = req.filtros.copy()
        filtros_log["FECHA"] = {"desde": req.fecha_desde, "hasta": req.fecha_hasta}
        db_users.registrar_accion_db(audit_db, current_user_email, "consulta_traf", {"sufijo": req.sufijo, "filtros": filtros_log})
    except Exception as e_audit:
        log.error(f"Error auditoría: {e_audit}")

    background_tasks.add_task(run_traf_query, task_id, req, current_user_email)
    
    log.info(f"Tarea {task_id} iniciada por {current_user_email}.")
    return {"task_id": task_id}

@router.get("/status/{task_id}")
async def get_task_status(task_id: str):
    task = tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarea no encontrada.")
    return {"status": task["status"], "error": task.get("error_message")}

@router.post("/cancel/{task_id}")
async def cancel_trazabilidad_query(
    task_id: str,
    audit_db: AuditDBSession,
    current_user_email: CurrentUserEmail
):
    task = tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarea no encontrada.")
    
    if task["status"] == "running":
        tasks_db[task_id]["status"] = "cancelled"
        log.info(f"Cancelación solicitada para {task_id}")
        try:
            db_users.registrar_accion_db(audit_db, current_user_email, "cancelar_traf", {"task_id": task_id})
        except: pass
        return {"status": "cancellation_requested"}
    
    if task["status"] in ["complete", "error", "cancelled"]:
        tasks_db.pop(task_id, None)
        return {"status": "cleared"}
    
    return {"status": task["status"]}

@router.get("/results/{task_id}", response_model=List[Dict[str, Any]])
async def get_task_results(task_id: str):
    task = tasks_db.get(task_id)
    if not task: raise HTTPException(status_code=404, detail="Tarea no encontrada.")
    if task["status"] != "complete":
        raise HTTPException(status_code=400, detail=f"La tarea no está completa.")
    return task["data"]

@router.post("/export/{task_id}")
async def export_trazabilidad_data(
    task_id: str,
    req: TrafExportRequest,
    audit_db: AuditDBSession,
    current_user_email: CurrentUserEmail
):
    task = tasks_db.get(task_id)
    if not task or task["status"] != "complete":
        raise HTTPException(status_code=404, detail="Tarea no encontrada o incompleta.")

    all_data = task["data"]
    if not all_data:
        raise HTTPException(status_code=404, detail="No hay datos.")

    try:
        db_users.registrar_accion_db(audit_db, current_user_email, "exportar_traf", {
            "task_id": task_id, "formato": req.formato, "num_filas": len(all_data)
        })
    except: pass

    df = pd.DataFrame(all_data)[req.visible_columns]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    buffer = io.BytesIO()

    if req.formato == "excel":
        df.to_excel(buffer, index=False, engine='openpyxl')
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"export_traf_{timestamp}.xlsx"
    else:
        buffer.write(df.to_csv(index=False, encoding='utf-8', sep=';').encode('utf-8'))
        media_type = "text/csv"
        filename = f"export_traf_{timestamp}.csv"
    
    buffer.seek(0)
    
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        buffer, media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )