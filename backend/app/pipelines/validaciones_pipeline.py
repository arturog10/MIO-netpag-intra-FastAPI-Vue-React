import logging
import pandas as pd
import numpy as np
import json
import os
import uuid
from sqlalchemy import text
from sqlalchemy.engine import Connection
from typing import Tuple, List

# Importamos la utilidad de carga rápida
from app.bulk_utils import bulk_insert_via_csv

logger = logging.getLogger(__name__)

# --- 1. NORMALIZACIÓN ---

def normalizar_telefonos(df: pd.DataFrame, task_id: str, cols_fono_estrategia: List[str] = None) -> pd.DataFrame:
    """
    Busca columnas de teléfono y agrega el prefijo '56' si falta.
    """
    logger.info(f"[Task {task_id}] [Sub-paso] Normalizando teléfonos...")
    df.columns = df.columns.str.lower().str.strip()
    
    if cols_fono_estrategia:
        phone_cols = [c for c in cols_fono_estrategia if c in df.columns]
    else:
        phone_cols = [c for c in df.columns if "fono" in c or "tel" in c]

    if not phone_cols: return df

    for col in phone_cols:
        # Convertir a string y limpiar decimales
        df[col] = df[col].astype(str).replace(r'\.0$', '', regex=True).str.strip()
        
        # Convertir basura a vacío
        mask_nulos = df[col].isin(['nan', 'None', 'NaT', '', '0', 'NULL'])
        df.loc[mask_nulos, col] = ""
        
        # Agregar 56 solo si hay un número válido
        mask_fix = (df[col] != "") & (~df[col].str.startswith("56"))
        if mask_fix.any():
            df.loc[mask_fix, col] = "56" + df.loc[mask_fix, col]
            
    return df

# --- 2. CONSOLIDACIÓN EMAILS (CASCADA) ---

def procesar_emails_jerarquia(df: pd.DataFrame, task_id: str, cols_mail_estrategia: List[str] = None) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Recorre mail1, mail2... buscando el primero válido.
    """
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
        if not mask_pendientes.any():
            break 

        raw_data = df.loc[mask_pendientes, col].astype(str).str.strip()
        
        # Condiciones
        es_inhibido = raw_data == '0'
        es_nulo = raw_data.isin(['nan', 'None', 'NaT', '', 'NULL'])
        
        # Limpieza
        clean_data = raw_data.mask(raw_data.isin(['nan', 'None', 'NaT', '', '0']), np.nan)
        
        # Validación Formato
        cumple_formato = raw_data.str.match(email_regex, case=False, na=False)
        
        es_formato_malo = (~es_nulo) & (~es_inhibido) & (~cumple_formato)
        es_valido = (~es_nulo) & (~es_inhibido) & cumple_formato
        
        # ASIGNAR
        filas_validas = mask_pendientes & (df.index.isin(raw_data[es_valido].index))
        df.loc[filas_validas, 'mail_final'] = clean_data[es_valido]

        # AUDITORÍA
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

    # Resultados
    mask_con_mail = df['mail_final'].notna()
    df_validos = df[mask_con_mail].copy()
    df_validos['mail'] = df_validos['mail_final']

    df_sin_mail = df[~mask_con_mail].copy()
    if not df_sin_mail.empty:
        df_sin_mail['motivo_rechazo'] = "Sin Correo Válido (Agotados/Inhibidos)"
        lista_rechazos_parciales.append(df_sin_mail)

    df_rech_final = pd.concat(lista_rechazos_parciales, ignore_index=True) if lista_rechazos_parciales else pd.DataFrame(columns=df.columns)

    df_validos = df_validos.drop(columns=['mail_final'], errors='ignore')
    if not df_rech_final.empty:
        df_rech_final = df_rech_final.drop(columns=['mail_final'], errors='ignore')

    return df_validos, df_rech_final


# --- 3. CONSOLIDACIÓN TELÉFONOS (SMS) ---

def procesar_telefonos_jerarquia(df: pd.DataFrame, task_id: str, cols_fono_estrategia: List[str] = None) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Recorre fono1, fono2... buscando el primero válido.
    REGLA SMS: Debe empezar con 569 (Celular). Se descartan fijos (562...).
    """
    logger.info(f"[Task {task_id}] [Sub-paso] Procesando jerarquía de teléfonos (Regla SMS: 569)...")
    
    cols_existentes = df.columns.tolist()
    if cols_fono_estrategia:
        candidatas = [c for c in cols_fono_estrategia if c in cols_existentes]
        cols_a_revisar = candidatas
    else:
        cols_a_revisar = [c for c in df.columns if "fono" in c or "tel" in c]

    if not cols_a_revisar: return df, pd.DataFrame(columns=df.columns) 

    df['telefono_final'] = pd.Series([None] * len(df), dtype='object')
    lista_rechazos = []

    for col in cols_a_revisar:
        mask_pendientes = df['telefono_final'].isna()
        if not mask_pendientes.any(): break 

        raw_data = df.loc[mask_pendientes, col].astype(str).str.strip()
        
        es_inhibido = raw_data == '0'
        es_nulo = raw_data.isin(['nan', 'None', 'NaT', '', 'NULL'])
        
        # --- REGLA ACTUALIZADA ---
        # Debe empezar con 569 y tener largo adecuado (11 o 12 dígitos)
        es_formato_valido = raw_data.str.startswith('569') & (raw_data.str.len() >= 11)
        
        es_valido = (~es_nulo) & (~es_inhibido) & es_formato_valido
        
        # Limpieza
        clean_data = raw_data.mask(raw_data.isin(['nan', 'None', 'NaT', '', '0']), np.nan)
        
        filas_validas = mask_pendientes & (df.index.isin(raw_data[es_valido].index))
        df.loc[filas_validas, 'telefono_final'] = clean_data[es_valido]

        # Auditoría
        mask_dato_existe = (~es_nulo)
        
        mask_rech_inhib = mask_pendientes & mask_dato_existe & es_inhibido
        if mask_rech_inhib.any():
            r = df[mask_rech_inhib].copy()
            r['motivo_rechazo'] = f"Inhibido LN ({col})"
            r[col] = "INHIBIDO (0)"
            lista_rechazos.append(r)

        # Si no es inhibido pero no cumple formato (ej: empieza con 562)
        mask_rech_fmt = mask_pendientes & mask_dato_existe & ~es_inhibido & ~es_formato_valido
        if mask_rech_fmt.any():
            r = df[mask_rech_fmt].copy()
            r['motivo_rechazo'] = f"Teléfono Inválido/Fijo ({col})"
            lista_rechazos.append(r)

    # Consolidar
    mask_con_fono = df['telefono_final'].notna()
    df_validos = df[mask_con_fono].copy()
    df_validos['telefono'] = df_validos['telefono_final']

    df_sin_fono = df[~mask_con_fono].copy()
    if not df_sin_fono.empty:
        df_sin_fono['motivo_rechazo'] = "Sin Celular Válido (Agotados/Inhibidos/Fijos)"
        lista_rechazos.append(df_sin_fono)

    df_rech_final = pd.concat(lista_rechazos, ignore_index=True) if lista_rechazos else pd.DataFrame(columns=df.columns)
    
    df_validos = df_validos.drop(columns=['telefono_final'], errors='ignore')
    if not df_rech_final.empty:
        df_rech_final = df_rech_final.drop(columns=['telefono_final'], errors='ignore')

    return df_validos, df_rech_final


# --- 4. VALIDACIÓN CON SP (INHIBICIONES) ---

def validar_inhibicion_con_sp(df: pd.DataFrame, cliente: str, tipo_campana: str, db_session: Connection, task_id: str, cols_a_validar: List[str]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Sube datos a Tabla Real, ejecuta SP y marca con '0'.
    """
    logger.info(f"[Task {task_id}] Ejecutando inhibición SP en columnas: {cols_a_validar}")
    
    if df.empty or not cols_a_validar: 
        return df, pd.DataFrame()

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
            logger.info(f"[Task {task_id}]   - SP Inhibiendo: {col_contacto} (Tipo: {tipo_contacto_sp})")
            
            idx_name = f"IX_{staging_table_name}_{col_contacto}"
            try:
                db_session.execute(text(f"CREATE INDEX {idx_name} ON [B2C].[dbo].[{staging_table_name}] ({col_contacto}, {col_rut_sp})"))
            except: pass

            query_sp = text(f"""
                EXEC [B2C].[dbo].[sp_exclusiones_netpag] 
                    @db_target = 'B2C', 
                    @schema_target = 'dbo', 
                    @tbl_target = '{staging_table_name}',
                    @cliente = :cli, 
                    @col_rut = :rut_col, 
                    @col_ctto = :ctto_col, 
                    @modo = 'ACTUALIZAR',
                    @tipo_contacto = :tipo_ctto
            """)
            
            db_session.execute(query_sp, {
                "cli": cliente, 
                "rut_col": col_rut_sp, 
                "ctto_col": col_contacto, 
                "tipo_ctto": tipo_contacto_sp
            })

        result = db_session.execute(text(f"SELECT * FROM [B2C].[dbo].[{staging_table_name}]"))
        cols_res = result.keys()
        df_resultado = pd.DataFrame(result.fetchall(), columns=cols_res)
        df_resultado.columns = df_resultado.columns.str.lower().str.strip()
        
        if 'rut_clean' in df_resultado.columns:
            df_resultado = df_resultado.drop(columns=['rut_clean'])

        return df_resultado, pd.DataFrame()

    except Exception as e:
        logger.error(f"[Task {task_id}] Error SP Inhibiciones: {e}", exc_info=True)
        raise e
    finally:
        try:
            db_session.execute(text(f"IF OBJECT_ID('[B2C].[dbo].[{staging_table_name}]', 'U') IS NOT NULL DROP TABLE [B2C].[dbo].[{staging_table_name}]"))
        except Exception as cleanup_error:
            logger.error(f"Error limpiando tabla staging: {cleanup_error}")

# --- 5. GESTIONADOS HOY ---
def validar_gestionados_hoy(df: pd.DataFrame, cliente: str, db_session_b2c: Connection, task_id: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    logger.info(f"[Task {task_id}] Validando gestionados hoy...")
    if df.empty: return df, pd.DataFrame()
    try:
        col_cruce = "rut" if "rut" in df.columns else "idempresa"
        db_col_cruce = "id_emp" if col_cruce == "idempresa" else "rut"
        query = text(f"SELECT DISTINCT {db_col_cruce} FROM B2C.dbo.masiv_dia WITH (NOLOCK) WHERE cliente = :cliente AND CONVERT(DATE, fecha_ges) = CONVERT(DATE, GETDATE())")
        result = db_session_b2c.execute(query, {"cliente": cliente})
        ids_gestionados = {str(row[0]).strip() for row in result}
        if not ids_gestionados: return df, pd.DataFrame()
        
        df[col_cruce] = df[col_cruce].astype(str).str.strip()
        mask_rech = df[col_cruce].isin(ids_gestionados)
        df_rech = df[mask_rech].copy()
        df_rech["motivo_rechazo"] = "Gestionado Mismo Día"
        return df[~mask_rech].copy(), df_rech
    except Exception as e: raise e

# --- 6. SEGMENTO ---
def _obtener_query_inhibicion(tipo_campana, cliente_codigo):
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        json_path = os.path.join(base_dir, "validaMasiv.json")
        
        if not os.path.exists(json_path): return None
        with open(json_path, "r", encoding="utf-8") as f: config = json.load(f)
        
        folder = config["rutas"].get(tipo_campana)
        filename = config["queries"].get(cliente_codigo)
        if not folder or not filename: return None
        
        sql_path = os.path.join(base_dir, folder.strip("/\\"), filename)
        if not os.path.exists(sql_path): return None
        
        with open(sql_path, "r", encoding="utf-8-sig") as f: return f.read()
    except: return None

def validar_inhibicion_segmento(df: pd.DataFrame, tipo: str, cliente: str, db_session: Connection, task_id: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    logger.info(f"[Task {task_id}] Validando inhibiciones SQL de Segmento...")
    query = _obtener_query_inhibicion(tipo, cliente)
    if not query:
        logger.warning(f"[Task {task_id}] No se aplicará inhibición de Segmento.")
        return df, pd.DataFrame()

    try:
        res = db_session.execute(text(query))
        df_sql = pd.DataFrame(res.fetchall(), columns=res.keys())
        df_sql.columns = df_sql.columns.str.lower().str.strip()
        col_cruce = "rut" if "rut" in df.columns else "idempresa"
        if col_cruce not in df_sql.columns: return df, pd.DataFrame()

        df[col_cruce] = df[col_cruce].astype(str).str.strip()
        df_sql[col_cruce] = df_sql[col_cruce].astype(str).str.strip()
        
        df_validado = pd.merge(df, df_sql, on=col_cruce, how="inner")
        mask_rech = ~df[col_cruce].isin(df_validado[col_cruce])
        df_rech = df[mask_rech].copy()
        df_rech["motivo_rechazo"] = "Inhibición SQL (Segmento)"
        return df_validado, df_rech
    except Exception as e: raise e

# --- 7. DUPLICADOS ---
def validar_duplicados(df: pd.DataFrame, tipo_campana: str, cliente: str, task_id: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    logger.info(f"[Task {task_id}] Validando duplicados...")
    df_clean = df.copy()
    df_duplicates_total = pd.DataFrame()
    
    def get_dups_mask(dataframe, col_name):
        mask_not_empty = (dataframe[col_name].notna()) & (dataframe[col_name] != "")
        mask_is_dup = dataframe.duplicated(subset=[col_name], keep=False)
        return mask_is_dup & mask_not_empty

    def aplicar_filtro(col, motivo):
        nonlocal df_clean, df_duplicates_total
        if col in df_clean.columns:
            mask = get_dups_mask(df_clean, col)
            if mask.any():
                dups = df_clean[mask].copy()
                dups["motivo_rechazo"] = motivo
                df_duplicates_total = pd.concat([df_duplicates_total, dups])
                df_clean = df_clean[~mask]

    # Reglas Generales
    if cliente != "0360CQTA":
        if "rut" in df_clean.columns: aplicar_filtro("rut", "RUT Duplicado")
        if "mail" in df_clean.columns and tipo_campana in ["MAIL", "MAIL_INF"]:
             aplicar_filtro("mail", "Email Duplicado")

    # Reglas Cliente 0360CQTA
    if cliente == "0360CQTA":
        id_cols = ["idempresa", "id_empresa", "id"]
        id_col = next((c for c in id_cols if c in df_clean.columns), None)
        if id_col: aplicar_filtro(id_col, f"ID Duplicado ({id_col})")
        
        dir_cols = ["direccion", "dir"]
        dir_col = next((c for c in dir_cols if c in df_clean.columns), None)
        if dir_col:
            df_clean[dir_col] = df_clean[dir_col].astype(str).str.lower().str.strip()
            aplicar_filtro(dir_col, "Dirección Duplicada")

    # Reglas SMS
    if tipo_campana == "SMS":
        phone_cols = [c for c in df_clean.columns if "fono" in c or "tel" in c]
        if phone_cols:
            aplicar_filtro(phone_cols[0], "Teléfono Duplicado")
    
    # Reglas DISCADOR
    if tipo_campana == "DISC":
        if "rut" in df_clean.columns: aplicar_filtro("rut", "RUT Duplicado (Discador)")

    if "ic" in df_clean.columns:
        aplicar_filtro("ic", "IC Duplicado")

    return df_clean, df_duplicates_total

# --- 8. TECNICA SMS ---
def validar_tecnicamente(df: pd.DataFrame, tipo_campana: str, task_id: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    df_rech = pd.DataFrame(columns=df.columns)
    df_val = df.copy()
    
    if tipo_campana == "SMS":
        # Validar columna 'telefono' (consolidada)
        col_tel = "telefono"
        if col_tel not in df_val.columns:
             cols_tel = [c for c in df_val.columns if "fono" in c or "tel" in c]
             if cols_tel: df_val[col_tel] = df_val[cols_tel[0]]
             else: raise ValueError("Falta columna de teléfono.")

        mask_tel_invalido = (df_val[col_tel] == "") | (df_val[col_tel] == "0") | (df_val[col_tel].isna())
        
        if mask_tel_invalido.any():
             rech = df_val[mask_tel_invalido].copy()
             rech["motivo_rechazo"] = "Teléfono Inválido/Inhibido"
             df_rech = pd.concat([df_rech, rech])
             df_val = df_val[~mask_tel_invalido]

    return df_val, df_rech

def aplicar_reglas_calculo(df, reglas): return df