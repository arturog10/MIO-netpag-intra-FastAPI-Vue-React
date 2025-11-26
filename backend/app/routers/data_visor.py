import logging
import json
import pandas as pd
import io
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.engine import Connection
from sqlalchemy import text
from typing import List, Annotated

from app.config import config
from app.database import get_db_session
from app.auth_security import get_current_user_email
from app.models import (
    DataRequest, DataResponse, 
    StrategySaveRequest, StrategyLoadResponse, 
    ExportRequest, VisorDataRequest
)
import app.db_operations as db_ops
import app.db_user_operations as db_users

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/visor",
    tags=["Visor de Datos"],
    dependencies=[Depends(get_current_user_email)]
)

# --- Dependencias ---
def get_b2c_db():
    yield from get_db_session("b2c")

B2CSession = Annotated[Connection, Depends(get_b2c_db)]
CurrentUser = Annotated[str, Depends(get_current_user_email)]

# --- 1. CLIENTES ---
@router.get("/clients", response_model=List[str])
def get_client_list():
    json_conf = config.get("json_config", {})
    return list(json_conf.get("cliente_table_map", {}).keys())

# --- 2. DATOS ---
@router.post("/data/{client_code}", response_model=DataResponse)
def get_data_for_client(client_code: str, req: DataRequest):
    """Obtiene datos paginados para el visor."""
    try:
        info_tabla = db_ops._get_table_info("cliente_table_map", client_code)
        db_gen = get_db_session(info_tabla["db_key"])
        db_session = next(db_gen)
        
        try:
            total_rows = db_ops.contar_datos_cliente(db_session, client_code, req.filtros)
            cols, rows = db_ops.obtener_datos_cliente(
                db_session, 
                client_code, 
                filtros=req.filtros, 
                page=req.page, 
                items_per_page=req.items_per_page,
                sort_field=req.sort_field,
                sort_order=req.sort_order
            )
            
            if not cols:
                # Fallback si no hay datos
                tabla = db_ops._get_reflected_table("cliente_table_map", client_code)
                cols = [c.name for c in tabla.columns]

            return DataResponse(
                total_rows=total_rows,
                all_columns=cols,
                rows=rows
            )
        finally:
            db_gen.close()
    except Exception as e:
        logger.error(f"Error getting data for {client_code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- 3. ESTRATEGIAS ---

@router.get("/strategies/{client_code}")
def get_strategies_for_client(client_code: str, db: B2CSession):
    """Lista las estrategias guardadas para un cliente."""
    try:
        return db_ops.cargar_estrategias_db(db, client_code)
    except Exception as e:
        logger.error(f"Error loading strategies: {e}")
        raise HTTPException(status_code=500, detail="Error al cargar estrategias.")

@router.get("/strategies/load/{strategy_id}", response_model=StrategyLoadResponse)
def load_strategy(strategy_id: int, db: B2CSession, user: CurrentUser):
    """Carga una estrategia específica."""
    try:
        data = db_ops.cargar_una_estrategia_db(db, strategy_id)
        if not data:
            raise HTTPException(status_code=404, detail="Estrategia no encontrada")
        
        # Auditoría de lectura
        try:
            db_users.registrar_accion_db(db, user, "cargar_estrategia", {"id": strategy_id})
        except: pass

        return StrategyLoadResponse(**data)
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Error loading strategy {strategy_id}: {e}")
        raise HTTPException(status_code=500, detail="Error al cargar la estrategia.")

@router.post("/strategies/{client_code}")
def save_strategy(
    client_code: str, 
    req: StrategySaveRequest,
    db: B2CSession,
    user: CurrentUser
):
    """Guarda una NUEVA estrategia."""
    try:
        # 1. Verificar nombre duplicado
        if db_ops.estrategia_existe_db(db, req.nombre_estrategia, client_code):
             raise HTTPException(status_code=409, detail="Ya existe una estrategia con ese nombre.")

        # 2. Obtener ID de usuario (CORRECCIÓN IMPORTANTE)
        id_usuario = None
        try:
            row = db.execute(text("SELECT id_usuario FROM B2C.dbo.Usuarios WHERE email = :e"), {"e": user}).fetchone()
            if row: id_usuario = row[0]
        except Exception as e:
            logger.warning(f"No se pudo obtener ID usuario: {e}")

        # 3. Guardar en BD
        db_ops.guardar_estrategia_db(
            db,
            nombre_estrategia=req.nombre_estrategia,
            cliente=client_code,
            columnas=req.columnas_visibles,
            filtro_columnas=req.filtro_columnas,
            filtros_aplicados=req.filtros_aplicados,
            orden_estado=req.orden_estado,
            usuario_creador=user,
            id_usuario_creador=id_usuario # <--- Pasamos el ID correcto
        )
        
        # 4. Auditoría
        try:
            db_users.registrar_accion_db(db, user, "guardar_estrategia", {"nombre": req.nombre_estrategia, "cliente": client_code})
        except: pass

        return {"status": "Estrategia guardada con éxito"}
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Error saving strategy: {e}")
        raise HTTPException(status_code=500, detail="Error al guardar la estrategia.")

@router.put("/strategies/{client_code}")
def overwrite_strategy(
    client_code: str,
    req: StrategySaveRequest,
    db: B2CSession,
    user: CurrentUser
):
    """Actualiza una estrategia existente por nombre."""
    try:
        success = db_ops.actualizar_estrategia_db(
            db,
            nombre_estrategia=req.nombre_estrategia,
            cliente=client_code,
            columnas=req.columnas_visibles,
            filtro_columnas=req.filtro_columnas,
            filtros_aplicados=req.filtros_aplicados,
            orden_estado=req.orden_estado
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="No se encontró la estrategia para actualizar.")

        try:
            db_users.registrar_accion_db(db, user, "actualizar_estrategia", {"nombre": req.nombre_estrategia})
        except: pass

        return {"status": "Estrategia actualizada con éxito"}
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Error updating strategy: {e}")
        raise HTTPException(status_code=500, detail="Error al actualizar la estrategia.")

@router.delete("/strategies/{strategy_id}")
def delete_strategy(strategy_id: int, db: B2CSession, user: CurrentUser):
    """Elimina (logicamente) una estrategia."""
    try:
        db_ops.eliminar_estrategia_db(db, strategy_id)
        try:
            db_users.registrar_accion_db(db, user, "eliminar_estrategia", {"id": strategy_id})
        except: pass
        return {"status": "Estrategia eliminada"}
    except Exception as e:
        logger.error(f"Error deleting strategy: {e}")
        raise HTTPException(status_code=500, detail="Error al eliminar.")

# --- 4. EXPORTACIÓN ---
@router.post("/export/{client_code}")
def export_data(
    client_code: str,
    req: ExportRequest,
    audit_db: B2CSession,
    user: CurrentUser
):
    """Genera Excel/CSV de los datos filtrados."""
    try:
        info_tabla = db_ops._get_table_info("cliente_table_map", client_code)
        db_gen = get_db_session(info_tabla["db_key"])
        db_session = next(db_gen)
        
        try:
            cols_db, all_data = db_ops.obtener_todos_los_datos_filtrados(db_session, client_code, req.filtros)
        finally:
            db_gen.close()

        # Filtrar columnas
        columnas_finales = req.visible_columns if req.visible_columns else cols_db
        df = pd.DataFrame(all_data)
        if not df.empty:
            # Intersección segura de columnas
            cols_existentes = [c for c in columnas_finales if c in df.columns]
            df = df[cols_existentes]

        # Generar archivo
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        buffer = io.BytesIO()

        if req.formato == "excel":
            df.to_excel(buffer, index=False, engine='openpyxl')
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            filename = f"export_{client_code}_{timestamp}.xlsx"
        else:
            buffer.write(df.to_csv(index=False, encoding='utf-8-sig', sep=';').encode('utf-8-sig'))
            media_type = "text/csv"
            filename = f"export_{client_code}_{timestamp}.csv"
        
        buffer.seek(0)
        
        try:
            db_users.registrar_accion_db(audit_db, user, "exportar_datos", {"cliente": client_code, "formato": req.formato})
        except: pass

        return StreamingResponse(
            buffer, 
            media_type=media_type, 
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        logger.error(f"Error export: {e}")
        raise HTTPException(status_code=500, detail=str(e))