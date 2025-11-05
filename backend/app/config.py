import os
import json
import logging
from dotenv import load_dotenv
from sqlalchemy import create_engine

# Carga las variables desde el archivo .env
load_dotenv()
logger = logging.getLogger(__name__)

# --- INICIO LÓGICA DE CONEXIÓN MÚLTIPLE ---

db_server = os.getenv("DB_SERVER")
db_user = os.getenv("SQL_USERNAME")
db_password = os.getenv("SQL_PASSWORD")

# Un diccionario para guardar nuestros motores de conexión
engines = {}

# Iteramos para buscar conexiones (DB_KEY_1, DB_KEY_2, etc.)
i = 1
while True:
    db_key = os.getenv(f"DB_KEY_{i}")
    db_name = os.getenv(f"DB_NAME_{i}")
    db_dialect = os.getenv(f"DB_DIALECT_{i}")

    # Si no encontramos más claves, paramos
    if not all([db_key, db_name, db_dialect]):
        break

    connection_string = None
    default_schema = "dbo" # Por defecto para mssql

    if db_dialect == "mssql":
        driver = "ODBC+Driver+17+for+SQL+Server"
        if db_user and db_password:
            connection_string = (
                f"mssql+pyodbc://{db_user}:{db_password}@{db_server}/"
                f"{db_name}?driver={driver}&timeout=600"
            )
        else: # Autenticación Windows
            connection_string = (
                f"mssql+pyodbc://@{db_server}/{db_name}?"
                f"driver={driver}&trusted_connection=yes&timeout=600"
            )
    
    elif db_dialect == "postgresql":
        connection_string = (
            f"postgresql+psycopg2://{db_user}:{db_password}@{db_server}/{db_name}"
        )
        default_schema = "public"

    if connection_string:
        # Creamos el motor y lo guardamos en el diccionario
        engines[db_key] = {
            "engine": create_engine(connection_string),
            "default_schema": default_schema
        }
        logger.info(f"Conexión '{db_key}' creada para la base de datos '{db_name}'")
    else:
        logger.error(f"No se pudo crear la conexión para la clave '{db_key}'")

    i += 1

# --- FIN LÓGICA DE CONEXIÓN ---

def load_json_config() -> dict:
    """Carga la configuración de mapeo de tablas desde el archivo config.json."""
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error al cargar 'config.json': {e}", exc_info=True)
        return {}

# Cargamos la configuración del JSON
json_config = load_json_config()

# --- EXPORTACIÓN DE VARIABLES ---
config = {
    "engines": engines, # Exporta el diccionario de motores
    "json_config": json_config, # Exporta el JSON cargado
    "secret_key": os.getenv("SECRET_KEY"),
    "algorithm": os.getenv("ALGORITHM", "HS256")
}