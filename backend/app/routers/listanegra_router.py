import logging
import pandas as pd
import io
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Body
from sqlalchemy.engine import Connection
from typing import List, Annotated
from fastapi.responses import StreamingResponse

# Importaciones de tus archivos
from app.models import (
    ListaNegraDataRequest, ListaNegraDataResponse, ListaNegraExportRequest
)
import app.db_operations as db_ops 
import app.db_user_operations as db_users 
from app.auth_security import get_current_user_email 
from app.database import get_db_session 

# Configura el logger para este archivo
logger = logging.getLogger(__name__) 

router = APIRouter(
    prefix="/api/listanegra",
    tags=["Lista Negra"],
    dependencies=[Depends(get_current_user_email)] 
)

# --- Dependencias de DB y Auditoría ---
# Tu config.json [file 1] muestra que 'lista_negra' y 'tabla_auditoria' están en la db_key 'b2c'
def get_b2c_db():
    yield from get_db_session("b2c") 

B2CDBSession = Annotated[Connection, Depends(get_b2c_db)]
CurrentUserEmail = Annotated[str, Depends(get_current_user_email)] 


@router.get("/columns", response_model=List[str])
def get_listanegra_columns(db: B2CDBSession):
    """
    Obtiene la lista de todas las columnas de Lista Negra
    para poblar los filtros en el frontend.
    """
    try:
        logger.info("Obteniendo columnas de Lista Negra") 
        return db_ops.obtener_columnas_listanegra(db) 
    except Exception as e:
        logger.error(f"Error al obtener columnas de Lista Negra: {e}", exc_info=True) 
        raise HTTPException(status_code=500, detail="Error al obtener columnas.")


@router.post("/data", response_model=ListaNegraDataResponse)
def get_listanegra_data(
    req: ListaNegraDataRequest,
    db: B2CDBSession,
    current_user_email: CurrentUserEmail
):
    """
    Obtiene los datos paginados y filtrados para Lista Negra.
    """
    logger.info(f"Usuario '{current_user_email}' consultando datos de Lista Negra con filtros: {req.filtros}") 
    
    try:
        # --- AUDITORÍA ---
        db_users.registrar_accion_db( 
            db_session=db,
            usuario=current_user_email,
            accion="consultar_lista_negra",
            detalles={"filtros": req.filtros, "pagina": req.page}
        )

        # 1. Contar el total
        total_rows = db_ops.contar_datos_listanegra( 
            db, filtros=req.filtros
        )
        
        # 2. Obtener los datos de la página
        cols, rows = db_ops.obtener_datos_listanegra( 
            db, 
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
    except ValueError as e:
        logger.warning(f"Intento de acceso con config no válida (LN): {e}") 
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error al obtener datos de Lista Negra: {e}", exc_info=True) 
        raise HTTPException(status_code=500, detail="Error interno al procesar datos.")

@router.post("/export")
async def export_listanegra_data(
    req: ListaNegraExportRequest,
    db: B2CDBSession,
    current_user_email: CurrentUserEmail
):
    """
    Obtiene TODOS los datos filtrados de Lista Negra y
    los devuelve como un archivo Excel o CSV.
    """
    logger.info(f"Usuario '{current_user_email}' solicitando exportación ({req.formato}) de Lista Negra.") 
    
    try:
        # 1. Obtener los datos de la DB
        logger.info(f"Iniciando exportación de Lista Negra...") 
        cols, all_data = db_ops.obtener_todos_los_datos_listanegra( 
            db, 
            filtros=req.filtros,
            sort_field=req.sort_field,
            sort_order=req.sort_order
        )
        if not all_data:
            logger.warning("No se encontraron datos para exportar con esos filtros.") 
            raise HTTPException(status_code=404, detail="No se encontraron datos para exportar con esos filtros.")
        
        # 2. Registrar la auditoría
        try:
            db_users.registrar_accion_db( 
                db_session=db,
                usuario=current_user_email,
                accion="exportar_datos_listanegra",
                detalles={
                    "formato": req.formato,
                    "num_filas": len(all_data),
                    "columnas_exportadas": req.visible_columns,
                    "filtros_aplicados": req.filtros
                }
            )
        except Exception as e_audit:
            logger.error(f"Error al registrar auditoría (exportar_datos_listanegra): {e_audit}") 
            # No detenemos la exportación si la auditoría falla

        # 3. Procesamiento con Pandas
        logger.info(f"Procesando {len(all_data)} filas de Lista Negra con Pandas...") 
        
        columnas_disponibles = cols if cols else all_data[0].keys()
        columnas_finales = [col for col in req.visible_columns if col in columnas_disponibles]
        
        if not columnas_finales:
             columnas_finales = list(columnas_disponibles)

        df = pd.DataFrame(all_data)[columnas_finales]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        buffer = io.BytesIO()

        if req.formato == "excel":
            df.to_excel(buffer, index=False, engine='openpyxl')
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            filename = f"exportacion_listanegra_{timestamp}.xlsx"
        else: # Asumir CSV
            buffer.write(df.to_csv(index=False, encoding='utf-8', sep=';').encode('utf-8'))
            media_type = "text/csv"
            filename = f"exportacion_listanegra_{timestamp}.csv"
        
        buffer.seek(0)
        logger.info(f"Exportación de Lista Negra lista: {filename}") 
        
        return StreamingResponse(
            buffer,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        logger.error(f"Error en la exportación de Lista Negra: {e}", exc_info=True) 
        raise HTTPException(status_code=500, detail=f"Error al generar el archivo: {e}")