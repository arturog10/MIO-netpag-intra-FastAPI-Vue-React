# En: app/db_traf_operations.py
import logging
from sqlalchemy import text, select, and_, column
from sqlalchemy.engine import Connection
from typing import List, Dict, Any

# --- Importamos los helpers estándar de TU proyecto ---
from app.db_operations import (
    _get_reflected_table, 
    _get_table_info, 
    construir_where_dinamico
)

logger = logging.getLogger(__name__)

def _get_traf_table_key(sufijo: str) -> str:
    """Devuelve la clave del config.json basada en el sufijo."""
    return "traf_masi" if sufijo == "MASI" else "traf_disc"

def get_traf_columns(sufijo: str) -> list[str]:
    """
    Obtiene los nombres de las columnas de la vista TRAF correspondiente.
    Esta función NO necesita una sesión, ya que usa la reflexión.
    """
    if not sufijo:
        return []
    
    try:
        table_key = _get_traf_table_key(sufijo)
        # _get_reflected_table usa el engine del config para reflejar
        tabla = _get_reflected_table(table_key)
        return [c.name for c in tabla.columns]
    except Exception as e:
        logger.error(f"No se pudo obtener la estructura de la vista para {sufijo}. Error: {e}")
        return []

def get_traf_data(db_session: Connection, sufijo: str, filtros: dict, columnas: list[str]) -> list[dict]:
    """
    Consulta la vista TRAF unificada usando la sesión inyectada.
    """
    if not sufijo or not columnas:
        return []

    try:
        table_key = _get_traf_table_key(sufijo)
        # Obtenemos la tabla reflejada (esto es rápido, es metadata)
        tabla = _get_reflected_table(table_key)
            
        # 1. Construimos la lista de columnas a seleccionar
        cols_to_select = [column(c.strip()) for c in columnas]

        # 2. Usamos el helper estándar de tu proyecto
        where_clauses, params = construir_where_dinamico(filtros, tabla)
        
        # 3. Construimos la consulta seleccionando las columnas explícitas
        stmt = select(*cols_to_select).select_from(tabla)
        
        # 4. (¡ESTA ES LA CORRECCIÓN!) Usamos 'and_()' para aplicar los filtros
        if where_clauses:
            stmt = stmt.where(and_(*where_clauses))

        # Aplicamos el orden por defecto
        if len(tabla.c) > 0:
             stmt = stmt.order_by(tabla.c[0])

        logger.info(f"Ejecutando consulta en la vista TRAF: {stmt} con parámetros: {params}")
        
        # Ejecutamos la consulta en la sesión que nos pasó el router
        result = db_session.execute(stmt, params)
        
        # Convertimos a dicts
        keys = result.keys()
        return [dict(zip(keys, row)) for row in result]
    
    except Exception as e:
        logger.error(f"Error al ejecutar la consulta en la vista TRAF. Error: {e}", exc_info=True)
        # Lanzamos la excepción para que el router la atrape y marque la tarea como 'error'
        raise e