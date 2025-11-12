import logging
import json
import pandas as pd
import io
from datetime import datetime
# --- NUEVO: Importaciones para dependencias y auditoría ---
from fastapi import APIRouter, HTTPException, Body, Depends
from sqlalchemy.engine import Connection
from typing import List, Annotated
# --- FIN NUEVO ---
from fastapi.responses import StreamingResponse

from app.config import config
from app.models import (
    DataRequest, DataResponse, StrategySaveRequest, 
    StrategyLoadResponse, ExportRequest
)
import app.db_operations as db_ops

# --- NUEVO: Importaciones de DB de usuarios y seguridad ---
import app.db_user_operations as db_users # Para la función de auditoría
from app.auth_security import get_current_user_email # Para obtener el usuario
from app.database import get_db_session # Para la sesión de la DB de auditoría
# --- FIN NUEVO ---


log = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/visor",
    tags=["Visor de Datos"],
    # --- NUEVO: Protegemos todas las rutas del visor ---
    # Esto asegura que solo usuarios logueados puedan usarlas.
    dependencies=[Depends(get_current_user_email)]
)

# --- NUEVO: Dependencias para la Auditoría ---
def get_audit_db():
    """
    Dependencia para obtener la sesión de BD donde está
    la 'tabla_auditoria' (asumimos que es 'b2c').
    """
    yield from get_db_session("b2c")

# Alias para inyección de dependencias
AuditDBSession = Annotated[Connection, Depends(get_audit_db)]
CurrentUserEmail = Annotated[str, Depends(get_current_user_email)]
# --- FIN NUEVO ---


# --- Endpoint de Datos Principal ---
# (No auditamos las vistas de datos, solo las acciones)
@router.post("/data/{client_code}", response_model=DataResponse)
def get_data_for_client(client_code: str, req: DataRequest):
    """
    Obtiene los datos paginados y filtrados para un cliente.
    """
    try:
        # ... (Tu lógica de obtención de datos no cambia) ...
        info = db_ops._get_table_info("cliente_table_map", client_code)
        engine = info["engine"]
        with engine.connect() as connection:
            with connection.begin():
                total_rows = db_ops.contar_datos_cliente(
                    connection, client_code, filtros=req.filtros
                )
                cols, rows = db_ops.obtener_datos_cliente(
                    connection, 
                    client_code, 
                    filtros=req.filtros, 
                    page=req.page, 
                    items_per_page=req.items_per_page,
                    sort_field=req.sort_field,
                    sort_order=req.sort_order
                )
                if not cols:
                    tabla = db_ops._get_reflected_table("cliente_table_map", client_code)
                    cols = [c.name for c in tabla.columns]
                return DataResponse(
                    total_rows=total_rows,
                    all_columns=cols or [],
                    rows=rows or []
                )
    except ValueError as e:
        log.warning(f"Intento de acceso con config no válida: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        log.error(f"Error al obtener datos para '{client_code}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno al procesar datos.")


# --- Endpoint de Clientes ---
# (No se audita)
@router.get("/clients", response_model=List[str])
def get_client_list():
    try:
        json_map = config["json_config"].get("cliente_table_map", {})
        return list(json_map.keys())
    except Exception as e:
        log.error(f"Error al cargar 'cliente_table_map' del config: {e}")
        return []

# --- Endpoints de Estrategias ---

def _get_strategy_connection():
    """Función auxiliar para conectarse a la DB de estrategias"""
    try:
        info = db_ops._get_table_info("tabla_estrategias")
        return info["engine"].connect()
    except Exception as e:
        log.error(f"Error al obtener conexión para 'tabla_estrategias': {e}")
        raise HTTPException(status_code=500, detail="No se pudo conectar a la DB de estrategias.")

# (Listar estrategias no se audita)
@router.get("/strategies/{client_code}", response_model=List[dict])
def get_strategies_for_client(client_code: str):
    """Obtiene la lista de estrategias (id, nombre) para un cliente."""
    with _get_strategy_connection() as connection:
        with connection.begin():
            try:
                estrategias_tuplas = db_ops.cargar_estrategias_db(connection, client_code)
                return [{"id": id, "nombre": nombre} for id, nombre in estrategias_tuplas]
            except Exception as e:
                log.error(f"Error en endpoint 'cargar_estrategias_db': {e}")
                raise HTTPException(status_code=500, detail="Error al cargar estrategias.")

@router.get("/strategies/load/{strategy_id}", response_model=StrategyLoadResponse)
def load_strategy(
    strategy_id: int,
    # --- NUEVO: Inyectamos dependencias de auditoría ---
    audit_db: AuditDBSession,
    current_user_email: CurrentUserEmail
):
    """Carga la configuración de una estrategia por su ID."""
    with _get_strategy_connection() as connection:
        with connection.begin():
            try:
                data = db_ops.cargar_una_estrategia_db(connection, strategy_id)
                if not data:
                    raise HTTPException(status_code=404, detail="Estrategia no encontrada")
                
                # --- NUEVO: Registro de auditoría ---
                try:
                    db_users.registrar_accion_db(
                        audit_db,
                        usuario=current_user_email,
                        accion="cargar_estrategia",
                        detalles={
                            "strategy_id": strategy_id
                        }
                    )
                except Exception as e_audit:
                    log.error(f"Error al registrar auditoría (cargar_estrategia): {e_audit}")
                # --- FIN NUEVO ---

                return StrategyLoadResponse(**data)
            except Exception as e:
                log.error(f"Error en endpoint 'cargar_una_estrategia_db': {e}")
                raise HTTPException(status_code=500, detail="Error al cargar la estrategia.")

@router.post("/strategies/{client_code}")
def save_strategy(
    client_code: str, 
    req: StrategySaveRequest,
    # --- NUEVO: Inyectamos dependencias de auditoría ---
    audit_db: AuditDBSession,
    current_user_email: CurrentUserEmail
):
    id_usuario = db_users.get_user_id_by_email(audit_db, current_user_email)
    """Guarda una NUEVA estrategia. Falla si ya existe."""
    with _get_strategy_connection() as connection:
        with connection.begin():
            try:
                existe = db_ops.estrategia_existe_db(connection, req.nombre_estrategia, client_code)
                if existe:
                    raise HTTPException(status_code=409, detail="Ya existe una estrategia con ese nombre.")
                
                success = db_ops.guardar_estrategia_db(
                    connection,
                    nombre=req.nombre_estrategia,
                    cliente=client_code,
                    columnas=req.columnas_visibles,
                    filtro_columnas=req.filtro_columnas,
                    filtros_aplicados=req.filtros_aplicados,
                    orden_estado=req.orden_estado,
                    id_usuario_creador=id_usuario,       
                    usuario_creador=current_user_email
                )
                if not success:
                    raise HTTPException(status_code=500, detail="No se pudo guardar la estrategia.")
                
                # --- NUEVO: Registro de auditoría ---
                try:
                    db_users.registrar_accion_db(
                        audit_db,
                        usuario=current_user_email,
                        accion="guardar_estrategia",
                        detalles={
                            "cliente": client_code,
                            "nombre_estrategia": req.nombre_estrategia
                        }
                    )
                except Exception as e_audit:
                    log.error(f"Error al registrar auditoría (guardar_estrategia): {e_audit}")
                # --- FIN NUEVO ---

                return {"status": "Estrategia guardada con éxito"}
            except HTTPException:
                raise
            except Exception as e:
                log.error(f"Error en endpoint 'guardar_estrategia_db': {e}")
                raise HTTPException(status_code=500, detail="Error al guardar la estrategia.")

@router.put("/strategies/{client_code}")
def overwrite_strategy(
    client_code: str, 
    req: StrategySaveRequest,
    # --- NUEVO: Inyectamos dependencias de auditoría ---
    audit_db: AuditDBSession,
    current_user_email: CurrentUserEmail
):
    id_usuario = db_users.get_user_id_by_email(audit_db, current_user_email)
    """Actualiza (sobrescribe) una estrategia existente."""
    with _get_strategy_connection() as connection:
        with connection.begin():
            try:
                success = db_ops.actualizar_estrategia_db(
                    connection,
                    nombre=req.nombre_estrategia,
                    cliente=client_code,
                    columnas=req.columnas_visibles,
                    filtro_columnas=req.filtro_columnas,
                    filtros_aplicados=req.filtros_aplicados,
                    orden_estado=req.orden_estado,
                    id_usuario_creador=id_usuario,
                    usuario_creador=current_user_email                    
                )
                if not success:
                    raise HTTPException(status_code=404, detail="No se encontró la estrategia para actualizar.")
                
                # --- NUEVO: Registro de auditoría ---
                try:
                    db_users.registrar_accion_db(
                        audit_db,
                        usuario=current_user_email,
                        accion="actualizar_estrategia",
                        detalles={
                            "cliente": client_code,
                            "nombre_estrategia": req.nombre_estrategia
                        }
                    )
                except Exception as e_audit:
                    log.error(f"Error al registrar auditoría (actualizar_estrategia): {e_audit}")
                # --- FIN NUEVO ---

                return {"status": "Estrategia actualizada con éxito"}
            except Exception as e:
                log.error(f"Error en endpoint 'actualizar_estrategia_db': {e}")
                raise HTTPException(status_code=500, detail="Error al actualizar la estrategia.")


# --- Endpoint de Exportación ---
@router.post("/export/{client_code}")
async def export_data(
    client_code: str, 
    req: ExportRequest,
    # --- NUEVO: Inyectamos dependencias de auditoría ---
    audit_db: AuditDBSession,
    current_user_email: CurrentUserEmail
):
    """
    Obtiene TODOS los datos filtrados y los devuelve como un
    archivo Excel o CSV para descargar.
    """
    try:
        info = db_ops._get_table_info("cliente_table_map", client_code)
        engine = info["engine"]

        with engine.connect() as connection:
            with connection.begin():
                log.info(f"Iniciando exportación para {client_code}...")
                cols, all_data = db_ops.obtener_todos_los_datos_filtrados(
                    connection, client_code, filtros=req.filtros
                )
                if not all_data:
                    raise HTTPException(status_code=404, detail="No se encontraron datos para exportar con esos filtros.")
        
        # --- NUEVO: Registro de auditoría ---
        # Lo registramos aquí, después de obtener los datos y antes de enviarlos.
        try:
            db_users.registrar_accion_db(
                audit_db,
                usuario=current_user_email,
                accion="exportar_datos",
                detalles={
                    "cliente": client_code,
                    "formato": req.formato,
                    "num_filas": len(all_data),
                    "columnas_exportadas": req.visible_columns,
                    "filtros_aplicados": req.filtros
                }
            )
        except Exception as e_audit:
            log.error(f"Error al registrar auditoría (exportar_datos): {e_audit}")
        # --- FIN NUEVO ---

        # --- Procesamiento de Pandas (fuera de la conexión de DB) ---
        log.info(f"Procesando {len(all_data)} filas con Pandas...")
        
        columnas_disponibles = cols if cols else all_data[0].keys()
        columnas_finales = [col for col in req.visible_columns if col in columnas_disponibles]
        
        if not columnas_finales:
             raise HTTPException(status_code=400, detail="Las columnas visibles seleccionadas no son válidas.")

        df = pd.DataFrame(all_data)[columnas_finales]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        buffer = io.BytesIO()

        if req.formato == "excel":
            # ... (tu lógica de Excel) ...
            df.to_excel(buffer, index=False, engine='openpyxl')
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            filename = f"exportacion_{timestamp}.xlsx"
        else:
            # ... (tu lógica de CSV) ...
            buffer.write(df.to_csv(index=False, encoding='utf-8', sep=';').encode('utf-8'))
            media_type = "text/csv"
            filename = f"exportacion_{timestamp}.csv"
        
        buffer.seek(0)
        log.info(f"Exportación lista: {filename}")
        
        return StreamingResponse(
            buffer,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        log.error(f"Error en la exportación: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error al generar el archivo: {e}")