import logging
import pandas as pd
import io
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Body
from sqlalchemy.engine import Connection
from sqlalchemy import text
from typing import List, Annotated
from fastapi.responses import StreamingResponse
from app.config import config

from app.models import (
    ListaNegraDataRequest, ListaNegraDataResponse, ListaNegraExportRequest,
    StrategySaveRequest, StrategyLoadResponse
)
import app.db_operations as db_ops 
import app.db_user_operations as db_users 
from app.auth_security import get_current_user_email 
from app.database import get_db_session 

logger = logging.getLogger(__name__) 

router = APIRouter(
    prefix="/api/listanegra",
    tags=["Lista Negra"],
    dependencies=[Depends(get_current_user_email)] 
)

def get_b2c_db():
    yield from get_db_session("intranet") 

B2CDBSession = Annotated[Connection, Depends(get_b2c_db)]
CurrentUserEmail = Annotated[str, Depends(get_current_user_email)] 

# --- 1. ENDPOINTS DE DATOS (LISTA NEGRA) ---

@router.get("/listanegras", response_model=List[str])
def get_listanegra_list():
    try:
        json_map = config.get("json_config", {}).get("listanegra_table_map", {})
        return list(json_map.keys())
    except Exception as e:
        logger.error(f"Error al cargar 'listanegra_table_map': {e}")
        return []

@router.get("/columns/{listanegra_key}", response_model=List[str])
def get_listanegra_columns(listanegra_key: str, db: B2CDBSession):
    try:
        return db_ops.obtener_columnas_listanegra(db) 
    except Exception as e:
        logger.error(f"Error columnas LN: {e}", exc_info=True) 
        raise HTTPException(status_code=500, detail="Error al obtener columnas.")

@router.post("/data/{listanegra_key}", response_model=ListaNegraDataResponse)
def get_listanegra_data(
    listanegra_key: str,
    req: ListaNegraDataRequest,
    db: B2CDBSession,
    current_user_email: CurrentUserEmail
):
    try:
        # Auditoría
        try:
            db_users.registrar_accion_db( 
                db_session=db,
                usuario=current_user_email,
                accion="consultar_lista_negra",
                detalles={"filtros": req.filtros, "pagina": req.page}
            )
        except: pass

        total_rows = db_ops.contar_datos_listanegra( 
            db, listanegra_key=listanegra_key, filtros=req.filtros
        )
        
        cols, rows = db_ops.obtener_datos_listanegra( 
            db,
            listanegra_key=listanegra_key, 
            filtros=req.filtros, 
            page=req.page, 
            items_per_page=req.items_per_page,
            sort_field=req.sort_field,
            sort_order=req.sort_order
        )
        
        return ListaNegraDataResponse(
            total_rows=total_rows,
            all_columns=cols or [],
            rows=rows or []
        )
    except Exception as e:
        logger.error(f"Error datos LN: {e}", exc_info=True) 
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/export/{listanegra_key}")
async def export_listanegra_data(
    listanegra_key: str,
    req: ListaNegraExportRequest,
    db: B2CDBSession,
    current_user_email: CurrentUserEmail
):
    try:
        cols, all_data = db_ops.obtener_todos_los_datos_listanegra( 
            db, 
            listanegra_key=listanegra_key,
            filtros=req.filtros,
            sort_field=req.sort_field,
            sort_order=req.sort_order
        )
        
        try:
            db_users.registrar_accion_db( 
                db_session=db,
                usuario=current_user_email,
                accion="exportar_datos_listanegra",
                detalles={"formato": req.formato, "filas": len(all_data)}
            )
        except: pass

        columnas_finales = req.visible_columns if req.visible_columns else cols
        df = pd.DataFrame(all_data)
        if not df.empty: df = df[[c for c in columnas_finales if c in df.columns]]

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        buffer = io.BytesIO()

        if req.formato == "excel":
            df.to_excel(buffer, index=False, engine='openpyxl')
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            filename = f"export_ln_{timestamp}.xlsx"
        else:
            buffer.write(df.to_csv(index=False, encoding='utf-8-sig', sep=';').encode('utf-8-sig'))
            media_type = "text/csv"
            filename = f"export_ln_{timestamp}.csv"
        
        buffer.seek(0)
        return StreamingResponse(buffer, media_type=media_type, headers={"Content-Disposition": f"attachment; filename={filename}"})

    except Exception as e:
        logger.error(f"Error export LN: {e}", exc_info=True) 
        raise HTTPException(status_code=500, detail="Error exportando.")


# --- 2. ENDPOINTS DE ESTRATEGIAS (CONSULTAS) ---

@router.get("/consultas/{listanegra_key}", response_model=List[dict])
def get_consultas_for_lista(listanegra_key: str, db: B2CDBSession):
    """Obtiene la lista de consultas guardadas."""
    try:
        # Usamos la misma DB de intranet donde están las estrategias
        consultas = db_ops.cargar_estrategias_db(db, listanegra_key)
        return [{"id": c["id"], "nombre": c["nombre_estrategia"]} for c in consultas]
    except Exception as e:
        logger.error(f"Error cargar consultas: {e}")
        raise HTTPException(status_code=500, detail="Error al cargar consultas.")

@router.get("/consultas/load/{consulta_id}", response_model=StrategyLoadResponse)
def load_consulta(
    consulta_id: int,
    db: B2CDBSession,
    current_user_email: CurrentUserEmail
):
    try:
        data = db_ops.cargar_una_estrategia_db(db, consulta_id)
        if not data: raise HTTPException(status_code=404, detail="Consulta no encontrada")
        
        try:
            db_users.registrar_accion_db(db, current_user_email, "cargar_consulta_ln", {"id": consulta_id})
        except: pass

        return StrategyLoadResponse(**data)
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Error cargar consulta {consulta_id}: {e}")
        raise HTTPException(status_code=500, detail="Error al cargar.")

@router.post("/consultas/{listanegra_key}")
def save_consulta(
    listanegra_key: str, 
    req: StrategySaveRequest,
    db: B2CDBSession,
    current_user_email: CurrentUserEmail
):
    try:
        # 1. Obtener ID Usuario
        id_usuario = None
        try:
            row = db.execute(text("SELECT id_usuario FROM intranet.dbo.Usuarios WHERE email = :e"), {"e": current_user_email}).fetchone()
            if row: id_usuario = row[0]
        except: pass

        # 2. Verificar Existencia
        if db_ops.estrategia_existe_db(db, req.nombre_estrategia, listanegra_key):
             raise HTTPException(status_code=409, detail="Ya existe una consulta con ese nombre.")

        # 3. Guardar
        db_ops.guardar_estrategia_db(
            db,
            nombre_estrategia=req.nombre_estrategia,
            cliente=listanegra_key, 
            columnas=req.columnas_visibles,
            filtro_columnas=req.filtro_columnas,
            filtros_aplicados=req.filtros_aplicados,
            orden_estado=req.orden_estado,
            usuario_creador=current_user_email,
            id_usuario_creador=id_usuario
        )
        
        try:
            db_users.registrar_accion_db(db, current_user_email, "guardar_consulta_ln", {"nombre": req.nombre_estrategia})
        except: pass

        return {"status": "Consulta guardada"}
            
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Error guardar consulta: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al guardar.")

@router.put("/consultas/{listanegra_key}")
def overwrite_consulta(
    listanegra_key: str, 
    req: StrategySaveRequest,
    db: B2CDBSession,
    current_user_email: CurrentUserEmail
):
    try:
        # 1. Obtener ID Usuario
        id_usuario = None
        try:
            row = db.execute(text("SELECT id_usuario FROM intranet.dbo.Usuarios WHERE email = :e"), {"e": current_user_email}).fetchone()
            if row: id_usuario = row[0]
        except: pass

        success = db_ops.actualizar_estrategia_db(
            db,
            nombre_estrategia=req.nombre_estrategia,
            cliente=listanegra_key,
            columnas=req.columnas_visibles,
            filtro_columnas=req.filtro_columnas,
            filtros_aplicados=req.filtros_aplicados,
            orden_estado=req.orden_estado
        )
        
        if not success: raise HTTPException(status_code=404, detail="Consulta no encontrada.")
        
        try:
            db_users.registrar_accion_db(db, current_user_email, "actualizar_consulta_ln", {"nombre": req.nombre_estrategia})
        except: pass

        return {"status": "Actualizada"}
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Error actualizar consulta: {e}")
        raise HTTPException(status_code=500, detail="Error al actualizar.")