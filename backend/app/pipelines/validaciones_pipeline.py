import logging
import pandas as pd
import numpy as np
import json
import os
import uuid
from sqlalchemy import text
from sqlalchemy.engine import Connection
from typing import Tuple, List

from app.bulk_utils import bulk_insert_via_csv

logger = logging.getLogger(__name__)

# --- 1. NORMALIZACIÓN ---
def normalizar_telefonos(df: pd.DataFrame, task_id: str, cols_fono_estrategia: List[str] = None) -> pd.DataFrame:
    logger.info(f"[Task {task_id}] [Sub-paso] Normalizando teléfonos...")
    df.columns = df.columns.str.lower().str.strip()
    if cols_fono_estrategia:
        phone_cols = [c for c in cols_fono_estrategia if c in df.columns]
    else:
        phone_cols = [c for c in df.columns if "fono" in c or "tel" in c]

    if not phone_cols: return df

    for col in phone_cols:
        df[col] = df[col].astype(str).replace(r'\.0$', '', regex=True).str.strip()
        mask_nulos = df[col].isin(['nan', 'None', 'NaT', '', '0', 'NULL'])
        df.loc[mask_nulos, col] = ""
        mask_fix = (df[col] != "") & (~df[col].str.startswith("56"))
        if mask_fix.any():
            df.loc[mask_fix, col] = "56" + df.loc[mask_fix, col]
    return df

# --- 2. CONSOLIDACIÓN (CORREGIDO WARNING) ---
def procesar_emails_jerarquia(df: pd.DataFrame, task_id: str, cols_mail_estrategia: List[str] = None) -> Tuple[pd.DataFrame, pd.DataFrame]:
    logger.info(f"[Task {task_id}] [Sub-paso] Procesando jerarquía de correos...")
    cols_existentes = df.columns.tolist()
    prioridad_estandar = [f'mail{i}' for i in range(1, 7)] + [f'm{i}' for i in range(1, 7)] + ['email', 'correo']
    
    cols_a_revisar = []
    if cols_mail_estrategia:
        candidatas = [c for c in cols_mail_estrategia if c in cols_existentes]
        cols_a_revisar = sorted(candidatas, key=lambda x: prioridad_estandar.index(x) if x in prioridad_estandar else 999)
    else:
        cols_a_revisar = [c for c in prioridad_estandar if c in cols_existentes]

    if not cols_a_revisar:
        return df, pd.DataFrame(columns=df.columns) 

    df['mail_final'] = pd.Series([None] * len(df), dtype='object')
    email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    lista_rechazos_parciales = []

    for col in cols_a_revisar:
        mask_pendientes = df['mail_final'].isna()
        if not mask_pendientes.any(): break 

        raw_data = df.loc[mask_pendientes, col].astype(str).str.strip()
        es_inhibido = raw_data == '0'
        es_nulo = raw_data.isin(['nan', 'None', 'NaT', '', 'NULL'])
        
        # --- CORRECCIÓN: USAR MASK EN VEZ DE REPLACE ---
        # Esto evita el FutureWarning y es más eficiente
        clean_data = raw_data.mask(raw_data.isin(['nan', 'None', 'NaT', '', '0']), np.nan)
        
        cumple_formato = raw_data.str.match(email_regex, case=False, na=False)
        
        es_formato_malo = (~es_nulo) & (~es_inhibido) & (~cumple_formato)
        es_valido = (~es_nulo) & (~es_inhibido) & cumple_formato
        
        filas_validas = mask_pendientes & (df.index.isin(raw_data[es_valido].index))
        df.loc[filas_validas, 'mail_final'] = clean_data[es_valido]

        mask_dato_existe = (~es_nulo)
        mask_rech_inhib = mask_pendientes & mask_dato_existe & es_inhibido
        if mask_rech_inhib.any():
            rech = df[mask_rech_inhib].copy()
            rech['motivo_rechazo'] = f"Inhibido LN ({col})"
            rech[col] = "INHIBIDO (0)"
            lista_rechazos_parciales.append(rech)

        mask_rech_fmt = mask_pendientes & mask_dato_existe & es_formato_malo
        if mask_rech_fmt.any():
            rech = df[mask_rech_fmt].copy()
            rech['motivo_rechazo'] = f"Formato Inválido ({col})"
            lista_rechazos_parciales.append(rech)

    mask_con_mail = df['mail_final'].notna()
    df_validos = df[mask_con_mail].copy()
    df_validos['mail'] = df_validos['mail_final']
    df_sin_mail = df[~mask_con_mail].copy()
    if not df_sin_mail.empty:
        df_sin_mail['motivo_rechazo'] = "Sin Correo Válido (Todos agotados/inhibidos)"
        lista_rechazos_parciales.append(df_sin_mail)

    df_rech_final = pd.concat(lista_rechazos_parciales, ignore_index=True) if lista_rechazos_parciales else pd.DataFrame(columns=df.columns)
    df_validos = df_validos.drop(columns=['mail_final'], errors='ignore')
    if not df_rech_final.empty: df_rech_final = df_rech_final.drop(columns=['mail_final'], errors='ignore')
    return df_validos, df_rech_final

# --- 3. VALIDACIÓN CON SP (Sin Cambios) ---
def validar_inhibicion_con_sp(df: pd.DataFrame, cliente: str, tipo_campana: str, db_session: Connection, task_id: str, cols_a_validar: List[str]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    logger.info(f"[Task {task_id}] Ejecutando inhibición SP en columnas: {cols_a_validar}")
    if df.empty or not cols_a_validar: return df, pd.DataFrame()
    tipo_contacto_sp = 'MAIL' if tipo_campana in ["MAIL", "MAIL_INF"] else 'FONO'
    table_id = str(uuid.uuid4()).replace('-', '')
    staging_table_name = f"stg_inhib_{table_id}"
    try:
        df_upload = df.copy()
        cols_def_list = []
        for col in df_upload.columns:
            if df_upload[col].dtype == 'object':
                df_upload[col] = df_upload[col].astype(str).replace(['nan', 'None', '0'], '')
            col_lower = col.lower()
            if col_lower in ['rut', 'idempresa', 'rut_clean'] or 'mail' in col_lower or 'fono' in col_lower or 'tel' in col_lower:
                cols_def_list.append(f"[{col}] NVARCHAR(255)")
            else:
                cols_def_list.append(f"[{col}] NVARCHAR(MAX)")
        col_rut_key = "rut" if "rut" in df_upload.columns else "idempresa"
        col_rut_sp = col_rut_key
        if col_rut_key == "rut":
             cols_def_list.append("[rut_clean] NVARCHAR(255)")
             df_upload['rut_clean'] = df_upload['rut'].astype(str).str.split('-').str[0]
             col_rut_sp = 'rut_clean'
        cols_def = ", ".join(cols_def_list)
        db_session.execute(text(f"CREATE TABLE [B2C].[dbo].[{staging_table_name}] ({cols_def})"))
        bulk_insert_via_csv(db_session, df_upload, f"[B2C].[dbo].[{staging_table_name}]", f"inhib_{table_id}", is_temp_table=False)
        columnas_reales = [c for c in cols_a_validar if c in df_upload.columns]
        for col_contacto in columnas_reales:
            logger.info(f"[Task {task_id}]   - SP Inhibiendo: {col_contacto}")
            idx_name = f"IX_{staging_table_name}_{col_contacto}"
            try: db_session.execute(text(f"CREATE INDEX {idx_name} ON [B2C].[dbo].[{staging_table_name}] ({col_contacto}, {col_rut_sp})"))
            except: pass
            query_sp = text(f"EXEC [B2C].[dbo].[sp_exclusiones_netpag] @db_target='B2C', @schema_target='dbo', @tbl_target='{staging_table_name}', @cliente=:cli, @col_rut=:rut_col, @col_ctto=:ctto_col, @modo='ACTUALIZAR', @tipo_contacto=:tipo_ctto")
            db_session.execute(query_sp, {"cli": cliente, "rut_col": col_rut_sp, "ctto_col": col_contacto, "tipo_ctto": tipo_contacto_sp})
        result = db_session.execute(text(f"SELECT * FROM [B2C].[dbo].[{staging_table_name}]"))
        cols_res = result.keys()
        df_resultado = pd.DataFrame(result.fetchall(), columns=cols_res)
        df_resultado.columns = df_resultado.columns.str.lower().str.strip()
        if 'rut_clean' in df_resultado.columns: df_resultado = df_resultado.drop(columns=['rut_clean'])
        return df_resultado, pd.DataFrame()
    except Exception as e:
        logger.error(f"[Task {task_id}] Error SP Inhibiciones: {e}", exc_info=True)
        raise e
    finally:
        try: db_session.execute(text(f"IF OBJECT_ID('[B2C].[dbo].[{staging_table_name}]', 'U') IS NOT NULL DROP TABLE [B2C].[dbo].[{staging_table_name}]"))
        except: pass

# --- 4. OTROS (Sin cambios) ---
def validar_gestionados_hoy(df, cliente, db_session, task_id):
    logger.info(f"[Task {task_id}] Validando gestionados hoy...")
    if df.empty: return df, pd.DataFrame()
    try:
        col_cruce = "rut" if "rut" in df.columns else "idempresa"
        db_col = "id_emp" if col_cruce == "idempresa" else "rut"
        query = text(f"SELECT DISTINCT {db_col} FROM B2C.dbo.masiv_dia WITH (NOLOCK) WHERE cliente = :c AND CONVERT(DATE, fecha_ges) = CONVERT(DATE, GETDATE())")
        result = db_session.execute(query, {"c": cliente})
        ids = {str(r[0]).strip() for r in result}
        if not ids: return df, pd.DataFrame()
        mask = df[col_cruce].astype(str).str.strip().isin(ids)
        return df[~mask].copy(), df[mask].assign(motivo_rechazo="Gestionado Mismo Día")
    except: return df, pd.DataFrame()

def _obtener_query_inhibicion(tipo, cliente):
    try:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        json_path = os.path.join(base, "validaMasiv.json")
        if not os.path.exists(json_path): return None
        with open(json_path, "r", encoding="utf-8") as f: config = json.load(f)
        folder = config["rutas"].get(tipo)
        filename = config["queries"].get(cliente)
        if not folder or not filename: return None
        sql_path = os.path.join(base, folder.strip("/\\"), filename)
        if not os.path.exists(sql_path): return None
        with open(sql_path, "r", encoding="utf-8-sig") as f: return f.read()
    except: return None

def validar_inhibicion_segmento(df, tipo, cliente, db_session, task_id):
    logger.info(f"[Task {task_id}] Validando segmento SQL...")
    q = _obtener_query_inhibicion(tipo, cliente)
    if not q: return df, pd.DataFrame()
    try:
        res = db_session.execute(text(q))
        df_s = pd.DataFrame(res.fetchall(), columns=res.keys())
        df_s.columns = df_s.columns.str.lower().str.strip()
        col = "rut" if "rut" in df.columns else "idempresa"
        if col not in df_s.columns: return df, pd.DataFrame()
        df[col] = df[col].astype(str).str.strip()
        df_s[col] = df_s[col].astype(str).str.strip()
        df_v = pd.merge(df, df_s, on=col, how="inner")
        msk = ~df[col].isin(df_v[col])
        return df_v, df[msk].assign(motivo_rechazo="Inhibición SQL (Segmento)")
    except Exception as e: raise e

def validar_duplicados(df, tipo, cliente, task_id):
    logger.info(f"[Task {task_id}] Validando duplicados...")
    df_c = df.copy()
    df_d = pd.DataFrame()
    def chk(c, m):
        nonlocal df_c, df_d
        if c in df_c.columns:
            msk = df_c.duplicated(subset=[c], keep=False) & df_c[c].notna() & (df_c[c] != "")
            if msk.any():
                d = df_c[msk].copy()
                d["motivo_rechazo"] = m
                df_d = pd.concat([df_d, d])
                df_c = df_c[~msk]
    
    if cliente != "0360CQTA":
        if "rut" in df_c.columns: chk("rut", "RUT Duplicado")
        if "mail" in df_c.columns and tipo in ["MAIL", "MAIL_INF"]: chk("mail", "Email Duplicado")
    
    if cliente == "0360CQTA":
        cols_id = ["idempresa", "id", "id_empresa"]
        c_id = next((x for x in cols_id if x in df_c.columns), None)
        if c_id: chk(c_id, f"ID Duplicado ({c_id})")
        c_dir = next((x for x in ["direccion", "dir"] if x in df_c.columns), None)
        if c_dir: chk(c_dir, "Dirección Duplicada")

    if tipo == "SMS":
        cols = [c for c in df_c.columns if "fono" in c or "tel" in c]
        if cols: chk(cols[0], "Teléfono Duplicado")
    if "ic" in df_c.columns: chk("ic", "IC Duplicado")
    return df_c, df_d

def validar_tecnicamente(df, tipo, task_id):
    df_r = pd.DataFrame(columns=df.columns)
    df_v = df.copy()
    if tipo == "SMS":
        cols = [c for c in df_v.columns if "fono" in c or "tel" in c]
        if not cols: raise ValueError("Falta fono SMS")
        c = cols[0]
        mask = (df_v[c] == "") | (df_v[c] == "0") 
        if mask.any():
            r = df_v[mask].copy()
            r["motivo_rechazo"] = "Teléfono Inválido/Inhibido"
            df_r = pd.concat([df_r, r])
            df_v = df_v[~mask]
    return df_v, df_r

def aplicar_reglas_calculo(df, reglas): return df