import logging
from sqlalchemy import text, select, and_, column, table
from sqlalchemy.engine import Connection
from typing import List, Dict, Any

# Importamos los motores para el Plan B
from app.database import engines

from app.db_operations import (
    _get_reflected_table, 
    _get_table_info, 
    construir_where_dinamico
)

logger = logging.getLogger(__name__)

def _get_traf_table_key(sufijo: str) -> str:
    return "traf_masi" if sufijo == "MASI" else "traf_disc"

def get_traf_columns(sufijo: str) -> list[str]:
    """
    Obtiene columnas. Si es una Vista y falla la reflexión,
    usa un SELECT TOP 0 directo (Fallback).
    """
    if not sufijo: return []
    
    table_key = _get_traf_table_key(sufijo)
    
    try:
        # INTENTO 1: Reflexión (Ideal para tablas)
        tabla = _get_reflected_table(table_key)
        return [c.name for c in tabla.columns]
    except Exception as e:
        logger.warning(f"Reflexión falló para {sufijo} (posible Vista): {e}")
        
        # INTENTO 2: Fallback consulta directa (Ideal para Vistas)
        try:
            info = _get_table_info(table_key)
            db_key = info["db_key"]
            table_name = info["table"]
            
            engine_info = engines.get(db_key)
            if not engine_info: raise ValueError(f"Motor {db_key} no iniciado")
            
            # Usamos una conexión rápida solo para leer headers
            with engine_info["engine"].connect() as conn:
                # SELECT TOP 0 es instantáneo y devuelve los nombres de columna
                res = conn.execute(text(f"SELECT TOP 0 * FROM {table_name}"))
                return list(res.keys())
                
        except Exception as e2:
            logger.error(f"Fallo total obteniendo columnas {sufijo}: {e2}")
            return []

def get_traf_data(db_session: Connection, sufijo: str, filtros: dict, columnas: list[str]) -> list[dict]:
    """
    Consulta datos TRAF. Soporta Vistas donde la reflexión falla.
    """
    if not sufijo or not columnas: return []
    table_key = _get_traf_table_key(sufijo)
    
    # 1. Obtener Objeto Tabla (Reflejado o Genérico)
    tabla_obj = None
    es_reflejada = False
    
    try:
        tabla_obj = _get_reflected_table(table_key)
        es_reflejada = True
    except Exception:
        # Si falla la reflexión, creamos una referencia genérica
        # Esto permite construir la query sin validar tipos estrictos
        info = _get_table_info(table_key)
        tabla_obj = table(info["table"])
        logger.info(f"Usando modo Vista (Sin reflexión) para: {info['table']}")

    try:
        # 2. Construir Columnas
        cols_to_select = []
        for c in columnas:
            c_clean = c.strip()
            if es_reflejada and c_clean in tabla_obj.c:
                cols_to_select.append(tabla_obj.c[c_clean])
            else:
                # Columna genérica si no tenemos metadata
                cols_to_select.append(column(c_clean))

        # 3. Construir Filtros
        # Pasamos tabla_obj solo si es reflejada para que aproveche tipos de datos
        # Si no es reflejada, construir_where_dinamico usará lógica genérica (string/numérico)
        where_clauses, params = construir_where_dinamico(
            filtros, 
            tabla_obj if es_reflejada else None
        )
        
        # 4. Armar Query
        stmt = select(*cols_to_select).select_from(tabla_obj)
        
        # Hint NOLOCK para SQL Server (Vital para vistas pesadas)
        stmt = stmt.with_hint(tabla_obj, 'WITH (NOLOCK)')
        
        if where_clauses:
            stmt = stmt.where(and_(*where_clauses))

        # Orden por defecto (solo si tenemos metadata de columnas)
        if es_reflejada and len(tabla_obj.c) > 0:
             stmt = stmt.order_by(tabla_obj.c[0])

        logger.info(f"Query TRAF: {stmt} | Params: {params}")
        
        # 5. Ejecutar
        result = db_session.execute(stmt, params)
        keys = result.keys()
        return [dict(zip(keys, row)) for row in result]

    except Exception as e:
        logger.error(f"Error ejecutando consulta TRAF: {e}", exc_info=True)
        raise e