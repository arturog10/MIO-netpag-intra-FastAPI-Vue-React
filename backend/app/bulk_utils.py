import logging
import pandas as pd
import os
import uuid
import csv
from sqlalchemy import text
from sqlalchemy.engine import Connection

logger = logging.getLogger(__name__)

# Ruta compartida (Asegúrate de que sea accesible por SQL Server)
SHARED_BULK_DIR = r"\\192.168.168.96\b2c\IT\CARGAS\DATOS\TMP_ARTURO_ASCANIO"

def bulk_insert_via_csv(
    db_session: Connection, 
    df: pd.DataFrame, 
    target_table: str, 
    task_id: str,
    is_temp_table: bool = False
) -> int:
    """
    Guarda el DataFrame como CSV (separado por pipe |) y ejecuta BULK INSERT.
    """
    if df.empty: return 0

    filename = f"bulk_{task_id}_{uuid.uuid4().hex[:8]}.csv"
    filepath = os.path.join(SHARED_BULK_DIR, filename)
    
    try:
        # 1. Limpieza Preventiva de Datos
        df_clean = df.copy()
        for col in df_clean.select_dtypes(include=['object']):
            df_clean[col] = df_clean[col].astype(str).str.replace('|', '', regex=False) \
                                           .str.replace('\n', ' ', regex=False) \
                                           .str.replace('\r', '', regex=False)

        # 2. Guardar CSV Estricto
        df_clean.to_csv(
            filepath, 
            index=False, 
            sep='|',             
            encoding='utf-8',    
            quoting=csv.QUOTE_NONE, 
            escapechar='\\',      
            lineterminator='\n'   
        )
        
        logger.info(f"Archivo BULK creado: {filepath}")

        # 3. Ejecutar BULK INSERT (Sintaxis Corregida)
        # Usamos f-string simple para evitar errores de indentación en SQL
        sql_query = f"""
            BULK INSERT {target_table}
            FROM '{filepath}'
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
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception as cleanup_error:
            logger.warning(f"No se pudo borrar archivo temporal {filepath}: {cleanup_error}")