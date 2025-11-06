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
# (Necesitarás un archivo similar a traf_operations.py adaptado a FastAPI)
from app.db_traf_operations import get_traf_columns, get_traf_data
# --- Importaciones de Autenticación y Auditoría ---
from app.auth_security import get_current_user_email
from app.database import get_db_session
import app.db_user_operations as db_users
from app.db_operations import _get_table_info # Importa el helper para obtener la db_key

log = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/trazabilidad",
    tags=["Trazabilidad"],
    dependencies=[Depends(get_current_user_email)] # Protege todas las rutas
)

# --- Base de datos en memoria para gestionar tareas ---
# (En producción, esto sería Redis o una tabla de BD)
tasks_db: Dict[str, Dict[str, Any]] = {}

# --- Dependencias de Auditoría ---
def get_audit_db():
    yield from get_db_session("b2c") # Asume que la tabla de auditoría está en 'b2c'

AuditDBSession = Annotated[Connection, Depends(get_audit_db)]
CurrentUserEmail = Annotated[str, Depends(get_current_user_email)]

# --- Modelos Pydantic (DTOs) ---
class TrafQueryRequest(BaseModel):
    sufijo: str
    fecha_desde: str
    fecha_hasta: str
    filtros: Dict[str, Any]
    visible_columns: List[str]

class TrafExportRequest(BaseModel):
    formato: str
    visible_columns: List[str]

# --- Función de Tarea de Fondo (El trabajo de 15 min) ---
def run_traf_query(
    task_id: str, 
    req: TrafQueryRequest, 
    user_email: str
):
    """
    Esta función se ejecuta en segundo plano (10-15 min).
    Usa el método manual de sesión de database.py.
    """
    log.info(f"[Task {task_id}] Iniciando consulta TRAF para {user_email}...")
    
    # --- Lógica para obtener la DB Key de la vista TRAF ---
    try:
        table_key = "traf_masi" if req.sufijo == "MASI" else "traf_disc"
        # Usamos _get_table_info para saber qué db_key usar (ej: "b2c")
        info_tabla = _get_table_info(table_key) 
        db_key_para_traf = info_tabla["db_key"]
    except Exception as e:
        log.error(f"[Task {task_id}] Error al obtener db_key para {table_key}: {e}")
        tasks_db[task_id]["status"] = "error"
        tasks_db[task_id]["error_message"] = f"Configuración de tabla no encontrada para {table_key}"
        return

    # --- Lógica de Sesión Manual (de database.py) ---
    db_gen = get_db_session(db_key_para_traf)
    db_session = None
    
    try:
        db_session = next(db_gen) # Inicia la conexión y transacción
        
        filtros_combinados = req.filtros.copy()
        advanced_fecha_filter = filtros_combinados.get("FECHA")
        if advanced_fecha_filter and (advanced_fecha_filter.get("desde") or advanced_fecha_filter.get("hasta")):
            # Si el usuario llenó un filtro de fecha avanzado, lo respetamos
            # y no hacemos nada.
            pass
        else:
            # Si "FECHA" no existe en los filtros avanzados, O si existe pero está vacío,
            # forzamos el uso de los filtros de fecha principales (obligatorios).
            filtros_combinados["FECHA"] = {
                "operador": "esta_entre", 
                "desde": req.fecha_desde, 
                "hasta": req.fecha_hasta
            }
        
        # 2. Obtiene las columnas (usando la misma sesión)
        # (Adaptamos get_traf_columns para aceptar la sesión)
        columnas_db = get_traf_columns(req.sufijo)
        if not columnas_db:
             raise ValueError("No se pudieron obtener columnas de la vista.")
        
        # Filtra las columnas solicitadas vs las que existen
        columnas_finales = [col for col in req.visible_columns if col in columnas_db]
        if not columnas_finales:
            columnas_finales = columnas_db # Si no se especifica, usa todas
            
        # 3. Ejecuta la consulta larga
        resultados_db = get_traf_data(
            db_session=db_session, # Pasa la sesión activa
            sufijo=req.sufijo,
            filtros=filtros_combinados,
            columnas=columnas_finales,
        )

        # 4. Revisa si la tarea fue cancelada MIENTRAS corría
        if tasks_db[task_id]["status"] == "cancelled":
            log.info(f"[Task {task_id}] Tarea cancelada. Descartando resultados.")
            tasks_db.pop(task_id, None)
            # El 'finally' de abajo hará rollback
            return

        # 5. Almacena resultados y marca como completa
        log.info(f"[Task {task_id}] Consulta completada. {len(resultados_db)} filas.")
        tasks_db[task_id]["status"] = "complete"
        # Guardamos los datos y las columnas usadas (para exportar)
        tasks_db[task_id]["data"] = resultados_db
        tasks_db[task_id]["columns"] = columnas_finales 

        # 6. Llama a next(db_gen) para hacer COMMIT
        try:
            next(db_gen)
        except StopIteration:
                # Esto es normal y esperado.
                # El generador de sesión de database.py termina así.
            pass
    except Exception as e:
        log.error(f"[Task {task_id}] Error en la tarea de fondo: {e}", exc_info=True)
        tasks_db[task_id]["status"] = "error"
        tasks_db[task_id]["error_message"] = str(e)
        # El 'finally' se encargará del rollback
        
    finally:
        # Cierra el generador (hace rollback si hubo error, o cierra si hubo commit)
        if db_session:
            db_gen.close()
            log.info(f"[Task {task_id}] Sesión de DB de tarea cerrada.")        


# --- Endpoint 1: Obtener Columnas ---
@router.get("/columns/{sufijo}", response_model=List[str])
async def get_columns_for_sufijo(sufijo: str):
    """
    Obtiene las columnas para un tipo de consulta (MASI o DISC).
    """
    if sufijo not in ["MASI", "DISC"]:
        raise HTTPException(status_code=400, detail="Sufijo inválido.")
    try:
        # (Asume que get_traf_columns maneja su propia conexión de BD)
        columnas = get_traf_columns(sufijo)
        return columnas
    except Exception as e:
        log.error(f"Error al obtener columnas TRAF: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener columnas.")

# --- Endpoint 2: Iniciar la Consulta (Tarea Larga) ---
@router.post("/start")
async def start_trazabilidad_query(
    req: TrafQueryRequest,
    background_tasks: BackgroundTasks,
    audit_db: AuditDBSession,
    current_user_email: CurrentUserEmail
):
    """
    Inicia la consulta de 15 minutos y devuelve un ID de tarea.
    """
    task_id = str(uuid.uuid4())
    tasks_db[task_id] = {"status": "running", "data": None}

    # 1. Auditoría (lógica de trazabilidad_state.py)
    try:
        filtros_log = req.filtros.copy()
        filtros_log["FECHA"] = {"desde": req.fecha_desde, "hasta": req.fecha_hasta}
        detalles_log = {"sufijo": req.sufijo, "filtros": filtros_log}
        db_users.registrar_accion_db(audit_db, current_user_email, "consulta_traf", detalles_log)
    except Exception as e_audit:
        log.error(f"Error al registrar auditoría (consulta_traf): {e_audit}")

    # 2. Inicia la tarea de fondo
    background_tasks.add_task(run_traf_query, task_id, req, current_user_email)
    
    log.info(f"Tarea {task_id} iniciada por {current_user_email}.")
    return {"task_id": task_id}

# --- Endpoint 3: Consultar Estado de la Tarea (Polling) ---
@router.get("/status/{task_id}")
async def get_task_status(task_id: str):
    """
    El frontend llama a esto cada 5-10 segundos.
    """
    task = tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarea no encontrada.")
    return {"status": task["status"], "error": task.get("error_message")}

# --- Endpoint 4: Cancelar la Tarea ---
@router.post("/cancel/{task_id}")
async def cancel_trazabilidad_query(
    task_id: str,
    audit_db: AuditDBSession,
    current_user_email: CurrentUserEmail
):
    """
    Establece la bandera de cancelación (lógica de trazabilidad_state.py).
    """
    task = tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarea no encontrada.")
    
    if task["status"] == "running":
        tasks_db[task_id]["status"] = "cancelled"
        log.info(f"Cancelación solicitada para la tarea {task_id} por {current_user_email}.")
        
        # Auditoría de cancelación
        try:
            db_users.registrar_accion_db(audit_db, current_user_email, "cancelar_traf", {"task_id": task_id})
        except Exception as e_audit:
            log.error(f"Error al registrar auditoría (cancelar_traf): {e_audit}")
            
        return {"status": "cancellation_requested"}
    
    if task["status"] in ["complete", "error", "cancelled"]:
        tasks_db.pop(task_id, None)
        log.info(f"Tarea {task_id} (estado: {task["status"]}) limpiada de la memoria por {current_user_email}.")
        return {"status": "cleared"}
    
    return {"status": task["status"]}

# --- Endpoint 5: Obtener Resultados (Al finalizar) ---
@router.get("/results/{task_id}", response_model=List[Dict[str, Any]])
async def get_task_results(task_id: str):
    """
    Llamado una vez que /status devuelve 'complete'.
    """
    task = tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarea no encontrada.")
    if task["status"] != "complete":
        raise HTTPException(status_code=400, detail=f"La tarea no está completa. Estado: {task['status']}")
    
    data = task["data"]
    log.info(f"Resultados de {task_id} entregados. La tarea permanece en caché para exportación.")
    return data

# --- Endpoint 6: Exportar (Usa los resultados cacheados) ---
@router.post("/export/{task_id}")
async def export_trazabilidad_data(
    task_id: str,
    req: TrafExportRequest,
    audit_db: AuditDBSession,
    current_user_email: CurrentUserEmail
):
    """
    Genera un Excel/CSV desde los resultados que ya están en memoria.
    NO vuelve a ejecutar la consulta de 15 min.
    """
    task = tasks_db.get(task_id)
    if not task or task["status"] != "complete":
        raise HTTPException(status_code=404, detail="Tarea no encontrada o no completada. Vuelva a consultar.")

    all_data = task["data"]
    if not all_data:
        raise HTTPException(status_code=404, detail="No hay datos para exportar.")

    # Auditoría de Exportación
    try:
        db_users.registrar_accion_db(audit_db, current_user_email, "exportar_traf", {
            "task_id": task_id,
            "formato": req.formato,
            "num_filas": len(all_data)
        })
    except Exception as e_audit:
        log.error(f"Error al registrar auditoría (exportar_traf): {e_audit}")

    # Lógica de Pandas (copiada de data_visor.py)
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
        buffer,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )