import logging
from typing import Optional, List
from sqlalchemy import (
    select, func, insert, update
)
from sqlalchemy.engine import Connection

# Importamos los helpers genéricos del archivo db_operations
from app.db_operations import _get_reflected_table

logger = logging.getLogger(__name__)

# --- OPERACIONES DE PLANTILLAS DE CAMPAÑAS ---

def listar_plantillas_db(db_session: Connection) -> List[dict]:
    """
    Obtiene una lista de todas las plantillas de campañas guardadas.
    No trae las reglas JSON para que la carga sea rápida.
    """
    try:
        tabla = _get_reflected_table("tabla_plantillas_campanas")
        
        # Seleccionamos solo los campos necesarios para la lista
        stmt = select(
            tabla.c.id, 
            tabla.c.nombre_plantilla, 
            tabla.c.fecha_creacion, 
            tabla.c.usuario_creador
        ).order_by(tabla.c.nombre_plantilla)
        
        result = db_session.execute(stmt).fetchall()
        logger.info(f"Se encontraron {len(result)} plantillas de campañas.")
        return [dict(row._mapping) for row in result]
    except Exception as e:
        logger.error(f"Error al CARGAR LISTA de plantillas de campañas: {e}", exc_info=True)
        raise e

def cargar_plantilla_db(db_session: Connection, id_plantilla: int) -> Optional[dict]:
    """
    Carga todos los datos de una plantilla específica, incluyendo las reglas JSON.
    """
    try:
        tabla = _get_reflected_table("tabla_plantillas_campanas")
        
        # Seleccionamos todos los campos
        stmt = select(tabla).where(tabla.c.id == id_plantilla)
        result = db_session.execute(stmt).fetchone()
        
        if result:
            logger.info(f"Cargando datos de la plantilla ID: {id_plantilla}")
            return dict(result._mapping)
        
        logger.warning(f"No se encontró la plantilla con ID: {id_plantilla}")
        return None
    except Exception as e:
        logger.error(f"Error al CARGAR UNA plantilla (ID {id_plantilla}): {e}", exc_info=True)
        raise e

def guardar_plantilla_db(db_session: Connection, nombre_plantilla: str, id_estrategia_base: int, 
                           reglas_validacion_json: str, reglas_procesamiento_json: str, 
                           modo_salida: str, id_usuario_creador: Optional[int], 
                           usuario_creador: Optional[str]) -> bool:
    """
    Guarda una nueva plantilla de campaña en la base de datos.
    """
    try:
        tabla = _get_reflected_table("tabla_plantillas_campanas")
        
        stmt = insert(tabla).values(
            nombre_plantilla=nombre_plantilla,
            id_estrategia_base=id_estrategia_base,
            reglas_validacion_json=reglas_validacion_json,
            reglas_procesamiento_json=reglas_procesamiento_json,
            modo_salida=modo_salida,
            id_usuario_creador=id_usuario_creador,
            usuario_creador=usuario_creador
            # fecha_creacion usa el DEFAULT de SQL
        )
        
        db_session.execute(stmt)
        logger.info(f"Plantilla '{nombre_plantilla}' guardada con éxito por {usuario_creador}.")
        return True
    except Exception as e:
        logger.error(f"Error al GUARDAR la plantilla '{nombre_plantilla}': {e}", exc_info=True)
        raise e

def actualizar_plantilla_db(db_session: Connection, id_plantilla: int, nombre_plantilla: str, id_estrategia_base: int, 
                             reglas_validacion_json: str, reglas_procesamiento_json: str, 
                             modo_salida: str, id_usuario_creador: Optional[int], 
                             usuario_creador: Optional[str]) -> bool:
    """
    Actualiza una plantilla de campaña existente por su ID.
    """
    try:
        tabla = _get_reflected_table("tabla_plantillas_campanas")
        
        stmt = update(tabla).where(
            tabla.c.id == id_plantilla
        ).values(
            nombre_plantilla=nombre_plantilla,
            id_estrategia_base=id_estrategia_base,
            reglas_validacion_json=reglas_validacion_json,
            reglas_procesamiento_json=reglas_procesamiento_json,
            modo_salida=modo_salida,
            id_usuario_creador=id_usuario_creador, # Actualiza quién fue el último en modificar
            usuario_creador=usuario_creador
        )
        
        result = db_session.execute(stmt)
        if result.rowcount == 0:
            logger.warning(f"Se intentó actualizar la plantilla ID {id_plantilla}, pero no se encontró.")
            return False
            
        logger.info(f"Plantilla '{nombre_plantilla}' (ID {id_plantilla}) actualizada por {usuario_creador}.")
        return True
    except Exception as e:
        logger.error(f"Error al ACTUALIZAR la plantilla ID {id_plantilla}: {e}", exc_info=True)
        raise e

# --- ESTA ES LA FUNCIÓN QUE FALTABA O NO SE ESTABA LEYENDO ---
def plantilla_existe_db(db_session: Connection, nombre: str) -> bool:
    """
    Verifica si ya existe una plantilla con el mismo nombre.
    """
    try:
        tabla = _get_reflected_table("tabla_plantillas_campanas")
        stmt = select(func.count()).select_from(tabla).where(
            tabla.c.nombre_plantilla == nombre
        )
        result = db_session.execute(stmt).scalar_one_or_none()
        return (result or 0) > 0
    except Exception as e:
        logger.error(f"Error al CHEQUEAR plantilla '{nombre}': {e}", exc_info=True)
        raise e