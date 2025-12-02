import logging
import pandas as pd
import os
import uuid
import csv
import platform  # <--- Para detectar si estamos en Windows o Linux
from sqlalchemy import text
from sqlalchemy.engine import Connection

logger = logging.getLogger(__name__)

# --- CONFIGURACIÓN DE RUTAS DUALES ---

# 1. Ruta para que SQL Server (Windows) encuentre el archivo
# Esta ruta debe ser accesible desde el servidor de base de datos.
SQL_READ_PATH_BASE = r"\\192.168.168.96\b2c\IT\CARGAS\DATOS\TMP_ARTURO_ASCANIO"

# 2. Ruta para que Python (Linux/Windows) escriba el archivo
if platform.system() == "Windows":
    # Desarrollo local en Windows: Usamos la misma ruta UNC (o una letra de unidad si la tienes mapeada)
    PYTHON_WRITE_PATH_BASE = SQL_READ_PATH_BASE
else:
    # Producción en Linux: Usamos el punto de montaje local
    # IMPORTANTE: Asegúrate de montar //192.168.168.96/b2c en /mnt/cargas_netpag
    # La ruta relativa dentro del share es /IT/CARGAS/DATOS/TMP_ARTURO_ASCANIO
    PYTHON_WRITE_PATH_BASE = "/mnt/cargas_netpag/IT/CARGAS/DATOS/TMP_ARTURO_ASCANIO"

def bulk_insert_via_csv(
    db_session: Connection, 
    df: pd.DataFrame, 
    target_table: str, 
    task_id: str,
    is_temp_table: bool = False
) -> int:
    """
    Guarda el DataFrame como CSV en la carpeta compartida y ejecuta BULK INSERT.
    Maneja rutas diferentes para Linux (escritura) y Windows (lectura SQL).
    """
    if df.empty: return 0

    # Generar nombre único
    filename = f"bulk_{task_id}_{uuid.uuid4().hex[:8]}.csv"
    
    # 1. Definir rutas completas
    path_escritura = os.path.join(PYTHON_WRITE_PATH_BASE, filename) # Ruta Linux
    path_lectura_sql = os.path.join(SQL_READ_PATH_BASE, filename)   # Ruta Windows UNC

    try:
        # 2. Verificar directorio de escritura
        os.makedirs(os.path.dirname(path_escritura), exist_ok=True)

        # 3. Limpieza y Guardado del CSV (Usando ruta de escritura)
        df_clean = df.copy()
        for col in df_clean.select_dtypes(include=['object']):
            df_clean[col] = df_clean[col].astype(str).str.replace('|', '', regex=False) \
                                           .str.replace('\n', ' ', regex=False) \
                                           .str.replace('\r', '', regex=False)

        df_clean.to_csv(
            path_escritura,   # <--- Python escribe aquí (Linux local mount)
            index=False, 
            sep='|',             
            encoding='utf-8',    
            quoting=csv.QUOTE_NONE, 
            escapechar='\\',      
            lineterminator='\n'   
        )
        
        logger.info(f"Archivo escrito en: {path_escritura}")
        logger.info(f"SQL leerá desde: {path_lectura_sql}")

        # 4. Ejecutar BULK INSERT (Usando ruta de lectura Windows)
        sql_query = f"""
            BULK INSERT {target_table}
            FROM '{path_lectura_sql}' 
            WITH (
                FIELDTERMINATOR = '|',
                ROWTERMINATOR = '0x0a',
                FIRSTROW = 2,
                CODEPAGE = '65001',
                TABLOCK
            );
        """
        
        db_session.execute(text(sql_query))
        
        count = len(df)
        logger.info(f"BULK INSERT exitoso en {target_table}. Filas: {count}")
        return count

    except Exception as e:
        logger.error(f"Error en carga BULK: {e}")
        raise e
    finally:
        # 5. Limpieza (Usando ruta de escritura que es la que controla Python)
        try:
            if os.path.exists(path_escritura):
                os.remove(path_escritura)
        except Exception as cleanup_error:
            logger.warning(f"No se pudo borrar archivo temporal {path_escritura}: {cleanup_error}")