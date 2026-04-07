import logging
import pandas as pd
from app.config import config
from app.database import get_db_session_context
from app.bulk_utils import bulk_insert_via_csv

logger = logging.getLogger(__name__)

def bulk_insert_final(df_validos: pd.DataFrame, cliente: str, tipo: str, task_id: str):
    """
    Prepara y carga a masiv_dia usando BULK INSERT rápido.
    ELIMINA EL PREFIJO '56' antes de guardar.
    """
    logger.info(f"[Task {task_id}] Preparando carga final rápida...")
    
    if df_validos.empty:
        return 0

    try:
        # 1. Formatear
        df_carga = pd.DataFrame()
        df_validos.columns = df_validos.columns.str.lower().str.strip()

        df_carga["rut"] = df_validos.get("rut", "")
        df_carga["rutsdv"] = df_carga["rut"].astype(str).str.split('-').str[0]
        
        phone_col = next((c for c in df_validos.columns if "fono" in c or "tel" in c), None)
        
        # --- MODIFICACIÓN: QUITAR PREFIJO '56' ---
        if phone_col:
            telefonos = df_validos[phone_col].astype(str).str.strip()
            # Si empieza con 56 y tiene largo suficiente (para no dejarlo vacío si era solo '56')
            df_carga["fono"] = telefonos.apply(lambda x: x[2:] if x.startswith('56') and len(x) > 2 else x)
            # Convertir vacíos a None
            df_carga["fono"] = df_carga["fono"].replace('', None)
        else:
            df_carga["fono"] = None
        # -----------------------------------------
        
        df_carga["mail"] = df_validos.get("mail", None) 
        df_carga["cliente"] = cliente
        df_carga["tipo_ges"] = tipo
        df_carga["fecha_ges"] = pd.to_datetime("now").strftime("%Y-%m-%d")
        df_carga["hora_ges"] = pd.to_datetime("now").strftime("%H:%M:%S")
        df_carga["id_emp"] = df_validos.get("idempresa", None)
        df_carga["ic"] = df_validos.get("ic", None)
        
        df_carga.fillna("", inplace=True)

        # 2. Conectar y Cargar
        with get_db_session_context("intranet") as db_session:
            count = bulk_insert_via_csv(db_session, df_carga, "intranet.dbo.masiv_dia", task_id, is_temp_table=False)
            logger.info(f"[Task {task_id}] Carga final completada: {count} registros.")
            return count

    except Exception as e:
        logger.error(f"[Task {task_id}] Error carga final: {e}", exc_info=True)
        raise e