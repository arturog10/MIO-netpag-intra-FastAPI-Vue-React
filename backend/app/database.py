import logging
import os
from fastapi import HTTPException
from sqlalchemy import create_engine
from contextlib import contextmanager
from app.config import settings, json_config 

logger = logging.getLogger(__name__)

# --- 1. FUNCIÓN PARA ESCANEAR CONFIG.JSON ---
def _extract_db_keys(data) -> set:
    """
    Recorre recursivamente el diccionario de configuración (json_config)
    y extrae todos los valores únicos de las claves "db_key".
    """
    keys = set()
    if isinstance(data, dict):
        for k, v in data.items():
            if k == "db_key" and isinstance(v, str):
                keys.add(v)
            else:
                keys.update(_extract_db_keys(v))
    elif isinstance(data, list):
        for item in data:
            keys.update(_extract_db_keys(item))
    return keys

# --- 2. INICIALIZACIÓN DINÁMICA DE MOTORES ---
engines = {}

def initialize_engines():
    """
    Crea automáticamente los motores de conexión basados en 
    los 'db_key' encontrados en config.json.
    """
    required_keys = _extract_db_keys(json_config)
    
    if not required_keys:
        logger.warning("No se encontraron 'db_key' en config.json. No se crearán conexiones.")
        return

    logger.info(f"Claves de BD detectadas en config.json: {required_keys}")

    driver = "ODBC+Driver+17+for+SQL+Server"
    
    for db_key in required_keys:
        # Busca nombre de DB en variable de entorno o usa el key por defecto
        env_var_name = f"DB_NAME_{db_key.upper()}"
        db_name = os.getenv(env_var_name, db_key)
        
        connection_string = ""
        
        if settings.SQL_USERNAME and settings.SQL_PASSWORD:
            connection_string = (
                f"mssql+pyodbc://{settings.SQL_USERNAME}:{settings.SQL_PASSWORD}@"
                f"{settings.DB_SERVER}/{db_name}?driver={driver}&timeout=600"
            )
        else: 
            connection_string = (
                f"mssql+pyodbc://@{settings.DB_SERVER}/{db_name}?"
                f"driver={driver}&trusted_connection=yes&timeout=600"
            )
            
        try:
            # --- CAMBIO IMPORTANTE AQUÍ ---
            engines[db_key] = {
                "engine": create_engine(
                    connection_string,
                    pool_pre_ping=True,   # <--- Verifica conexión antes de usarla (Evita error 10054)
                    pool_recycle=1800,    # Recicla conexiones cada 30 min para evitar timeouts del servidor
                    pool_size=10,         # Tamaño del pool
                    max_overflow=20,       # Conexiones extra si el pool se llena
                    fast_executemany=True
                ),
                "default_schema": "dbo" 
            }
            logger.info(f"Motor creado para key '{db_key}' -> DB: '{db_name}'")
        except Exception as e:
            logger.error(f"Fallo al crear motor para '{db_key}': {e}")

# Ejecutar inicialización al importar este archivo
initialize_engines()


# --- 3. GENERADOR DE SESIÓN (Para Endpoints) ---
def get_db_session(db_key: str):
    if db_key not in engines:
        logger.error(f"Se solicitó una clave de DB no configurada: {db_key}")
        raise HTTPException(status_code=500, detail=f"Configuración de DB '{db_key}' no encontrada.")
        
    engine_info = engines[db_key]
    engine = engine_info.get("engine")

    if not engine:
        logger.error(f"Configuración de motor '{db_key}' no tiene un 'engine' válido.")
        raise HTTPException(status_code=500, detail="Error interno del servidor.")

    connection = None
    transaction = None
    
    try:
        connection = engine.connect().execution_options(
            timeout=600,                # Command Timeout: 10 minutos para CONSULTAS
            isolation_level="READ UNCOMMITTED" # Equivalente a NOLOCK global (más velocidad)
        )
        transaction = connection.begin()
        logger.debug(f"Sesión de DB '{db_key}' iniciada (Timeout: 600s)")
        yield connection
        if transaction and transaction.is_active:
            transaction.commit()
            logger.debug(f"Sesión de DB 'commit' para '{db_key}'")
    
    except HTTPException as e_http:
            if transaction and transaction.is_active:
                transaction.rollback()
            raise e_http
    except Exception as e:
        if transaction and transaction.is_active:
            transaction.rollback()
            logger.error(f"Sesión de DB 'rollback' para '{db_key}' debido a error: {e}")
        logger.error(f"Error en la sesión de DB '{db_key}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error de base de datos.")
    finally:
        if connection:
            connection.close()
            logger.debug(f"Sesión de DB cerrada para '{db_key}'")


# --- 4. CONTEXT MANAGER (Para Pipelines) ---
@contextmanager
def get_db_session_context(db_key: str):
    if db_key not in engines:
         raise Exception(f"Clave de DB no configurada: {db_key}")
    
    engine = engines[db_key]["engine"]
    connection = engine.connect().execution_options(
        timeout=600, 
        isolation_level="READ UNCOMMITTED"
    )
    transaction = connection.begin()
    
    try:
        logger.debug(f"Contexto DB '{db_key}' iniciado (Timeout: 600s)")
        yield connection
        if transaction.is_active:
            transaction.commit()
    except Exception as e:
        if transaction.is_active:
            transaction.rollback()
            logger.error(f"Rollback en contexto '{db_key}': {e}")
        raise e
    finally:
        connection.close()