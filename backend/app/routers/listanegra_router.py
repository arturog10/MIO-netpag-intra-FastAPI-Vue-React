import logging
import pandas as pd
import io
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Body
from sqlalchemy.engine import Connection
from typing import List, Annotated
from fastapi.responses import StreamingResponse
from app.config import config

# Importaciones de tus archivos
from app.models import (
    ListaNegraDataRequest, ListaNegraDataResponse, ListaNegraExportRequest,
    StrategySaveRequest, StrategyLoadResponse
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

def _get_strategy_connection():
    """Función auxiliar para conectarse a la DB de estrategias"""
    try:
        info = db_ops._get_table_info("tabla_estrategias")
        return info["engine"].connect()
    except Exception as e:
        logger.error(f"Error al obtener conexión para 'tabla_estrategias': {e}")
        raise HTTPException(status_code=500, detail="No se pudo conectar a la DB de estrategias.")

@router.get("/listanegras", response_model=List[str]) # <-- NUEVO ENDPOINT
def get_listanegra_list():
    """
    Obtiene la lista de tablas de lista negra disponibles
    desde config.json (similar a /api/visor/clients).
    """
    try:
        json_map = config["json_config"].get("listanegra_table_map", {})
        return list(json_map.keys())
    except Exception as e:
        logger.error(f"Error al cargar 'listanegra_table_map' del config: {e}")
        return []


@router.get("/columns/{listanegra_key}", response_model=List[str])
def get_listanegra_columns(listanegra_key: str, db: B2CDBSession):
    """
    Obtiene la lista de todas las columnas de Lista Negra
    para poblar los filtros en el frontend.
    """
    try:
        logger.info("Obteniendo columnas de Lista Negra") 
        return db_ops.obtener_columnas_listanegra(db, listanegra_key) 
    except Exception as e:
        logger.error(f"Error al obtener columnas de Lista Negra: {e}", exc_info=True) 
        raise HTTPException(status_code=500, detail="Error al obtener columnas.")


@router.post("/data/{listanegra_key}", response_model=ListaNegraDataResponse)
def get_listanegra_data(
    listanegra_key: str,
    req: ListaNegraDataRequest,
    db: B2CDBSession,
    current_user_email: CurrentUserEmail
):
    """
    Obtiene los datos paginados y filtrados para Lista Negra.
    """
    logger.info(f"Usuario '{current_user_email}' consultando datos de '{listanegra_key}' con filtros: {req.filtros}") 
    
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
            db, listanegra_key=listanegra_key, filtros=req.filtros
        )
        
        # 2. Obtener los datos de la página
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
    except ValueError as e:
        logger.warning(f"Intento de acceso con config no válida (LN): {e}") 
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error al obtener datos de Lista Negra: {e}", exc_info=True) 
        raise HTTPException(status_code=500, detail="Error interno al procesar datos.")

@router.post("/export/{listanegra_key}")
async def export_listanegra_data(
    listanegra_key: str,
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
            listanegra_key=listanegra_key,
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
    
@router.get("/consultas/{listanegra_key}", response_model=List[dict])
def get_consultas_for_lista(listanegra_key: str):
    """Obtiene la lista de consultas (id, nombre) para una lista negra."""
    with _get_strategy_connection() as connection:
        with connection.begin():
            try:
                # Reutilizamos la función de db_ops, pasando la key de la lista como "cliente"
                consultas_tuplas = db_ops.cargar_estrategias_db(connection, listanegra_key)
                return [{"id": id, "nombre": nombre} for id, nombre in consultas_tuplas]
            except Exception as e:
                logger.error(f"Error en endpoint 'cargar_consultas_db': {e}")
                raise HTTPException(status_code=500, detail="Error al cargar consultas.")

@router.get("/consultas/load/{consulta_id}", response_model=StrategyLoadResponse)
def load_consulta(
    consulta_id: int,
    audit_db: B2CDBSession, # Nota: Usamos B2CDBSession que ya definimos
    current_user_email: CurrentUserEmail
):
    """Carga la configuración de una consulta por su ID."""
    with _get_strategy_connection() as connection:
        with connection.begin():
            try:
                data = db_ops.cargar_una_estrategia_db(connection, consulta_id)
                if not data:
                    raise HTTPException(status_code=404, detail="Consulta no encontrada")
                
                try:
                    db_users.registrar_accion_db(
                        audit_db,
                        usuario=current_user_email,
                        accion="cargar_consulta_ln", # Acción específica de LN
                        detalles={"consulta_id": consulta_id}
                    )
                except Exception as e_audit:
                    logger.error(f"Error al registrar auditoría (cargar_consulta_ln): {e_audit}")

                return StrategyLoadResponse(**data)
            except Exception as e:
                logger.error(f"Error en endpoint 'cargar_una_consulta_db': {e}")
                raise HTTPException(status_code=500, detail="Error al cargar la consulta.")

@router.post("/consultas/{listanegra_key}")
def save_consulta(
    listanegra_key: str, 
    req: StrategySaveRequest,
    audit_db: B2CDBSession,
    current_user_email: CurrentUserEmail
):
    """Guarda una NUEVA consulta. Falla si ya existe."""
    id_usuario = db_users.get_user_id_by_email(audit_db, current_user_email)
    
    with _get_strategy_connection() as connection:
        
        # --- INICIO DEL CAMBIO ---
        
        # 1. VERIFICAMOS SI EXISTE ANTES de iniciar la transacción
        try:
            existe = db_ops.estrategia_existe_db(connection, req.nombre_estrategia, listanegra_key)
            if existe:
                # Si existe, lanzamos el 409 y la función termina aquí.
                raise HTTPException(status_code=409, detail="Ya existe una consulta con ese nombre.")
        
        except HTTPException:
            raise # Re-lanzar el 409
        except Exception as e:
            logger.error(f"Error al verificar existencia de consulta: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Error al verificar la consulta.")
        
        connection.commit()
        # 2. SI LLEGA AQUÍ, ES SEGURO GUARDAR. AHORA INICIAMOS LA TRANSACCIÓN.
        with connection.begin():
            try:
                # Ya no necesitamos el 'if existe:' aquí
                success = db_ops.guardar_estrategia_db(
                    connection,
                    nombre=req.nombre_estrategia,
                    cliente=listanegra_key, 
                    columnas=req.columnas_visibles,
                    filtro_columnas=req.filtro_columnas,
                    filtros_aplicados=req.filtros_aplicados,
                    orden_estado=req.orden_estado,
                    id_usuario_creador=id_usuario,
                    usuario_creador=current_user_email
                )
                if not success:
                    raise HTTPException(status_code=500, detail="No se pudo guardar la consulta.")
                
                try:
                    db_users.registrar_accion_db(
                        audit_db,
                        usuario=current_user_email,
                        accion="guardar_consulta_ln",
                        detalles={
                            "lista_key": listanegra_key,
                            "nombre_consulta": req.nombre_estrategia
                        }
                    )
                except Exception as e_audit:
                    logger.error(f"Error al registrar auditoría (guardar_consulta_ln): {e_audit}")

                return {"status": "Consulta guardada con éxito"}
            
            except Exception as e:
                # Este 'except' ahora solo captura errores del 'guardar_estrategia_db' o 'registrar_accion_db'
                logger.error(f"Error en endpoint 'guardar_consulta_db': {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Error al guardar la consulta.")
        
        # --- FIN DEL CAMBIO ---

@router.put("/consultas/{listanegra_key}")
def overwrite_consulta(
    listanegra_key: str, 
    req: StrategySaveRequest,
    audit_db: B2CDBSession,
    current_user_email: CurrentUserEmail
):
    id_usuario = db_users.get_user_id_by_email(audit_db, current_user_email)
    """Actualiza (sobrescribe) una consulta existente."""
    with _get_strategy_connection() as connection:
        with connection.begin():
            try:
                success = db_ops.actualizar_estrategia_db(
                    connection,
                    nombre=req.nombre_estrategia,
                    cliente=listanegra_key, # <-- Guarda la key de la lista como "cliente"
                    columnas=req.columnas_visibles,
                    filtro_columnas=req.filtro_columnas,
                    filtros_aplicados=req.filtros_aplicados,
                    orden_estado=req.orden_estado,
                    id_usuario_creador=id_usuario,
                    usuario_creador=current_user_email
                )
                if not success:
                    raise HTTPException(status_code=404, detail="No se encontró la consulta para actualizar.")
                
                try:
                    db_users.registrar_accion_db(
                        audit_db,
                        usuario=current_user_email,
                        accion="actualizar_consulta_ln",
                        detalles={
                            "lista_key": listanegra_key,
                            "nombre_consulta": req.nombre_estrategia
                        }
                    )
                except Exception as e_audit:
                    logger.error(f"Error al registrar auditoría (actualizar_consulta_ln): {e_audit}")

                return {"status": "Consulta actualizada con éxito"}
            except Exception as e:
                logger.error(f"Error en endpoint 'actualizar_consulta_db': {e}")
                raise HTTPException(status_code=500, detail="Error al actualizar la consulta.")    