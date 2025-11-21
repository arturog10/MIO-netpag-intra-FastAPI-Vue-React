import logging
import pandas as pd
import os
import uuid
from sqlalchemy import text
from sqlalchemy.engine import Connection

logger = logging.getLogger(__name__)

# Ruta compartida accesible por Python (para escribir) y por SQL Server (para leer)
# Asegúrate de que esta ruta sea correcta y tenga permisos de escritura
SHARED_BULK_DIR = r"\\192.168.168.96\b2c\IT\CARGAS\DATOS\TMP_ARTURO_ASCANIO"

def bulk_insert_via_csv(
    db_session: Connection, 
    df: pd.DataFrame, 
    target_table: str, 
    task_id: str,
    is_temp_table: bool = False
) -> int:
    """
    Guarda el DataFrame como CSV y ejecuta BULK INSERT en SQL Server.
    Es órdenes de magnitud más rápido que to_sql.
    """
    if df.empty: return 0

    # 1. Generar nombre de archivo único
    filename = f"bulk_{task_id}_{uuid.uuid4().hex[:8]}.csv"
    filepath = os.path.join(SHARED_BULK_DIR, filename)
    
    # Ruta escapada para SQL (si hay espacios o caracteres raros)
    # Para SQL Server, las rutas de red suelen funcionar directas si el servicio tiene permisos.
    
    try:
        # 2. Guardar CSV (Sin índice, con encabezado para saltarlo luego)
        # Usamos utf-8-sig para compatibilidad total
        df.to_csv(filepath, index=False, sep=';', encoding='utf-8-sig')
        logger.info(f"Archivo BULK temporal creado: {filepath}")

        # 3. Ejecutar BULK INSERT
        # FIRSTROW=2 salta el encabezado
        sql_bulk = text(f"""
            BULK INSERT {target_table}
            FROM '{filepath}'
            WITH (
                FIELDTERMINATOR = ';',
                ROWTERMINATOR = '\\n',
                FIRSTROW = 2,
                CODEPAGE = '65001', -- UTF-8
                KEEPNULLS
            );
        """)
        
        db_session.execute(sql_bulk)
        
        # Si es tabla temporal, no hacemos commit aquí (depende de la transacción padre)
        # Si es tabla real, se debería hacer commit fuera de esta función
        
        count = len(df)
        logger.info(f"BULK INSERT exitoso en {target_table}. Filas: {count}")
        return count

    except Exception as e:
        logger.error(f"Error en carga BULK: {e}")
        raise e
    finally:
        # 4. Limpieza: Intentar borrar el archivo temporal
        # Nota: A veces SQL Server mantiene el lock un momento.
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception as cleanup_error:
            logger.warning(f"No se pudo borrar archivo temporal {filepath}: {cleanup_error}")