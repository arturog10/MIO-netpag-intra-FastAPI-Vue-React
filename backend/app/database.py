import logging
from fastapi import HTTPException
from app.config import config

# Obtenemos el diccionario de motores (engines)
engines = config.get("engines", {})
logger = logging.getLogger(__name__)

def get_db_session(db_key: str):
    """
    Generador de dependencia de FastAPI para obtener una sesión
    de base de datos basada en la db_key.
    
    Esto es lo que reemplaza a tu antiguo 'get_db()'.
    
    Uso en FastAPI:
        @app.get("/endpoint")
        def my_endpoint(db: Connection = Depends(lambda: get_db_session("mi_db"))):
            ...
    
    Uso en scripts (como create_admin.py):
        db_gen = get_db_session("mi_db")
        db = next(db_gen)
        try:
            # ... operaciones con db ...
            next(db_gen)  # Ejecuta commit
        except:
            db_gen.close()  # Ejecuta rollback
    """
    if db_key not in engines:
        logger.error(f"Se solicitó una clave de DB no configurada: {db_key}")
        raise HTTPException(status_code=500, detail=f"Configuración de DB '{db_key}' no encontrada.")
        
    engine_info = engines[db_key]
    engine = engine_info.get("engine")

    if not engine:
        logger.error(f"Configuración de motor '{db_key}' no tiene un 'engine' válido.")
        raise HTTPException(status_code=500, detail="Error interno del servidor.")

    # Abre la conexión
    connection = None
    transaction = None
    
    try:
        connection = engine.connect()
        transaction = connection.begin()
        
        logger.debug(f"Sesión de DB iniciada para '{db_key}'")
        
        # Entrega la conexión al endpoint/script
        yield connection
        
        # Si llegamos aquí, todo salió bien - hacer commit
        if transaction and transaction.is_active:
            transaction.commit()
            logger.debug(f"Sesión de DB 'commit' para '{db_key}'")
    
    except HTTPException as e_http:
            # Si el error ya es un HTTPException (como nuestro 409),
            # hacemos rollback pero VOLVEMOS A LANZAR EL ERROR ORIGINAL (409).
            if transaction and transaction.is_active:
                transaction.rollback()
                logger.warning(f"Sesión de DB 'rollback' para '{db_key}' debido a HTTPException: {e_http.detail}")
            # Re-lanzamos el 409 (o el error HTTP que sea)
            raise e_http
                    
    except Exception as e:
        # Si algo falló, hacer rollback
        if transaction and transaction.is_active:
            transaction.rollback()
            logger.error(f"Sesión de DB 'rollback' para '{db_key}' debido a error: {e}")
        
        logger.error(f"Error en la sesión de DB '{db_key}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error de base de datos.")
        
    finally:
        # Cerrar la conexión
        if connection:
            connection.close()
            logger.debug(f"Sesión de DB cerrada para '{db_key}'")