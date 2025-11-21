import json
import logging
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    # --- 1. Seguridad (Leídas del .env) ---
    # Al declararlas aquí, Pydantic las busca automáticamente en el archivo .env
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # --- 2. Credenciales Globales de SQL Server ---
    DB_SERVER: str
    SQL_USERNAME: Optional[str] = None
    SQL_PASSWORD: Optional[str] = None
    
    # Configuración para leer .env y ignorar variables extra
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore" 
    )

# Instancia de configuración global (Carga el .env aquí)
try:
    settings = Settings()
except Exception as e:
    logger.error(f"Error cargando configuración (verifique su archivo .env): {e}")
    # Valores por defecto inseguros para que no crashee si falta algo, pero avise
    class FallbackSettings:
        SECRET_KEY = "ERROR_NO_SECRET_KEY"
        ALGORITHM = "HS256"
        ACCESS_TOKEN_EXPIRE_MINUTES = 60
        DB_SERVER = "localhost"
        SQL_USERNAME = None
        SQL_PASSWORD = None
    settings = FallbackSettings()

# Carga del JSON de configuración (Tu mapa de tablas)
def load_json_config() -> dict:
    try:
        # Intenta ruta relativa directa
        path = "config.json"
        if not os.path.exists(path):
            # Intenta ruta absoluta basada en el archivo actual
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            path = os.path.join(base_dir, "config.json")
            
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error al cargar 'config.json': {e}")
        return {}

json_config = load_json_config()

# Objeto exportado para compatibilidad con el resto de tu app
config = {
    "settings": settings,
    "json_config": json_config,
    # --- IMPORTANTE: Mapeo para auth_security.py ---
    # auth_security.py busca estas llaves en minúsculas dentro de este diccionario
    "secret_key": settings.SECRET_KEY,
    "algorithm": settings.ALGORITHM,
    "access_token_expire_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES
}