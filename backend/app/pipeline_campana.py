import logging
import pandas as pd
import json
import os
import numpy as np
from sqlalchemy import text
from app import db_operations, db_plantillas_operations
from app.database import get_db_session

logger = logging.getLogger(__name__)
tasks_db: dict = {}

# --- 0. FUNCIONES AUXILIARES DE LIMPIEZA ---

def normalizar_telefonos(df):
    """Normaliza columnas de teléfono agregando 56 si falta."""
    phone_cols = [c for c in df.columns if "fono" in c or "tel" in c]
    if not phone_cols: return df

    logger.info("Normalizando teléfonos...")
    for col in phone_cols:
        # Convertir a string y limpiar
        df[col] = df[col].astype(str).replace(r'\.0$', '', regex=True).str.strip()
        
        # Convertir 'nan', 'None', '0', '' a string vacío
        mask_nulos = df[col].isin(['nan', 'None', 'NaT', '', '0'])
        df.loc[mask_nulos, col] = ""
        
        # Solo agregar 56 si tiene datos y no lo tiene
        mask_fix = (~mask_nulos) & (~df[col].str.startswith("56")) & (df[col] != "")
        if mask_fix.any():
            df.loc[mask_fix, col] = "56" + df.loc[mask_fix, col]
    return df

def procesar_consolidacion_emails(df):
    """
    Busca columnas de mail (mail1..6, m1..6), toma el primero válido
    y lo consolida en una columna 'mail'.
    """
    logger.info("Consolidando correos (MAIL1...MAIL6 -> MAIL)...")
    
    # 1. Identificar columnas candidatas en orden de prioridad
    cols_existentes = df.columns.tolist()
    cols_prioridad = [f'mail{i}' for i in range(1, 7)] + [f'm{i}' for i in range(1, 7)] + ['email', 'correo']
    
    # Filtrar las que realmente existen en el DF
    cols_a_revisar = [c for c in cols_prioridad if c in cols_existentes]
    
    # Si no hay columnas de mail específicas pero existe 'mail', la usamos directo
    if not cols_a_revisar and 'mail' in cols_existentes:
        cols_a_revisar = ['mail']

    if not cols_a_revisar:
        logger.warning("No se encontraron columnas de correo para consolidar.")
        return df, pd.DataFrame() # Retorna vacío en rechazados, la validación técnica posterior fallará si es necesario

    # 2. Crear columna 'mail_final' usando backfill (coalesce)
    # Creamos una serie vacía (NaN) del tamaño del DF
    df['mail_final'] = np.nan
    
    for col in cols_a_revisar:
        # Limpiamos la columna actual: vacíos y 'nan' se vuelven NaN real
        clean_col = df[col].astype(str).str.strip().replace(['', 'nan', 'None', 'NaT'], np.nan)
        # Rellenamos los huecos en 'mail_final' con los valores de esta columna
        df['mail_final'] = df['mail_final'].fillna(clean_col)
    
    # 3. Separar Validos y Rechazados
    mask_sin_mail = df['mail_final'].isna()
    
    df_rechazados = df[mask_sin_mail].copy()
    if not df_rechazados.empty:
        df_rechazados['motivo_rechazo'] = "Sin Correo Válido"
        
    df_validos = df[~mask_sin_mail].copy()
    
    # Asignamos el valor consolidado a la columna oficial 'mail'
    df_validos['mail'] = df_validos['mail_final']
    
    # Limpieza de columnas temporales
    if 'mail_final' in df_validos.columns: del df_validos['mail_final']
    if 'mail_final' in df_rechazados.columns: del df_rechazados['mail_final']
    
    logger.info(f"Correos consolidados. Válidos: {len(df_validos)}, Sin Correo: {len(df_rechazados)}")
    return df_validos, df_rechazados


# --- 1. VALIDACIÓN TÉCNICA ---
def validar_tipo_campana(df, tipo_campana):
    """
    Validaciones estrictas. Lanza error si la estructura no es válida.
    """
    logger.info(f"Validando reglas técnicas para: {tipo_campana}")
    df.columns = df.columns.str.lower().str.strip()
    
    if tipo_campana == "SMS":
        # --- Reglas SMS ---
        cols_tel = [c for c in df.columns if "fono" in c or "tel" in c]
        if not cols_tel: raise ValueError("Para SMS falta columna de teléfono.")
        if "mensaje" not in df.columns: raise ValueError("Para SMS falta columna 'mensaje'.")
        
        # Largo Mensaje
        col_msg = "mensaje"
        largos = df[df[col_msg].astype(str).str.len() > 160]
        if not largos.empty: raise ValueError(f"{len(largos)} mensajes exceden 160 caracteres.")
        
        # Formato Teléfono (Solo SMS)
        for col in cols_tel:
            # Validamos solo los que tienen datos
            invalidos = df[(df[col] != "") & (~df[col].str.startswith("56"))]
            if not invalidos.empty: 
                raise ValueError(f"Columna '{col}': {len(invalidos)} números inválidos (no empiezan con 56).")

    elif tipo_campana in ["MAIL", "MAIL_INF"]:
        # --- Reglas MAIL ---
        # Solo validamos existencia de RUT o ID. NO validamos teléfonos.
        if "rut" not in df.columns and "idempresa" not in df.columns:
             raise ValueError("Para Mail se requiere columna 'rut' o 'idempresa'.")
        
        if "mail" not in df.columns:
             # Esto no debería pasar si corrió procesar_consolidacion_emails antes
             raise ValueError("No se generó la columna 'mail' consolidada.")


# --- 2. LIMPIEZA DE DUPLICADOS ---
def limpiar_duplicados_dataframe(df, tipo_campana):
    """
    Elimina duplicados ignorando vacíos.
    """
    logger.info("Limpiando duplicados...")
    df_clean = df.copy()
    df_clean.columns = df_clean.columns.str.lower().str.strip()
    df_duplicates_total = pd.DataFrame()

    # Helper para detectar duplicados ignorando vacíos
    def get_dups_mask(dataframe, col_name):
        # Solo consideramos duplicado si el valor NO es vacío
        mask_not_empty = (dataframe[col_name] != "") & (dataframe[col_name].notna())
        # Buscamos duplicados en todo el DF
        mask_is_dup = dataframe.duplicated(subset=[col_name], keep="first")
        # El registro es duplicado real SOLO SI no es vacío Y está duplicado
        return mask_is_dup & mask_not_empty

    # 1. RUT (Siempre)
    if "rut" in df_clean.columns:
        df_clean["rut"] = df_clean["rut"].astype(str).str.strip()
        mask_dup = get_dups_mask(df_clean, "rut")
        
        if mask_dup.any():
            dups = df_clean[mask_dup].copy()
            dups["motivo_rechazo"] = "RUT Duplicado"
            df_duplicates_total = pd.concat([df_duplicates_total, dups])
            df_clean = df_clean[~mask_dup]
            logger.info(f"Eliminados {len(dups)} RUTs duplicados.")

    # 2. Email (Siempre, usando la columna consolidada 'mail')
    if "mail" in df_clean.columns:
        df_clean["mail"] = df_clean["mail"].astype(str).str.lower().str.strip()
        mask_dup = get_dups_mask(df_clean, "mail")
        
        if mask_dup.any():
            dups = df_clean[mask_dup].copy()
            dups["motivo_rechazo"] = "Email Duplicado"
            df_duplicates_total = pd.concat([df_duplicates_total, dups])
            df_clean = df_clean[~mask_dup]
            logger.info(f"Eliminados {len(dups)} Emails duplicados.")

    # 3. Teléfono (SOLO si es SMS)
    if tipo_campana == "SMS":
        phone_cols = [c for c in df_clean.columns if "fono" in c or "tel" in c]
        for col in phone_cols:
            df_clean[col] = df_clean[col].astype(str).str.strip()
            mask_dup = get_dups_mask(df_clean, col)
            
            if mask_dup.any():
                dups = df_clean[mask_dup].copy()
                dups["motivo_rechazo"] = f"Teléfono Duplicado ({col})"
                df_duplicates_total = pd.concat([df_duplicates_total, dups])
                df_clean = df_clean[~mask_dup]
                logger.info(f"Eliminados {len(dups)} Teléfonos duplicados en {col}.")

    return df_clean, df_duplicates_total

# --- 3. INHIBICIÓN SQL ---
def obtener_query_inhibicion(tipo_campana, cliente_codigo):
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(base_dir, "validaMasiv.json")
        with open(json_path, "r", encoding="utf-8") as f: config = json.load(f)
        folder = config["rutas"].get(tipo_campana)
        filename = config["queries"].get(cliente_codigo)
        if not folder or not filename: return None
        sql_path = os.path.join(base_dir, folder.strip("/\\"), filename)
        if not os.path.exists(sql_path): return None
        with open(sql_path, "r", encoding="utf-8-sig") as f: return f.read()
    except Exception: return None

# --- PIPELINE PRINCIPAL ---
def ejecutar_pipeline_campana(id_plantilla: int, task_id: str, db_key_b2c: str):
    logger.info(f"[Task {task_id}] Iniciando pipeline...")
    db_gen = get_db_session(db_key_b2c)
    db_session = None
    
    try:
        db_session = next(db_gen)
        
        # CARGAR CONFIG
        plantilla_dict = db_plantillas_operations.cargar_plantilla_db(db_session, id_plantilla)
        estrategia_dict = db_operations.cargar_una_estrategia_db(db_session, plantilla_dict["id_estrategia_base"])
        
        cliente_codigo = estrategia_dict["codigo_cliente"]
        filtros = json.loads(estrategia_dict["filtros_aplicados"] or "{}")
        
        reglas_val_json = json.loads(plantilla_dict["reglas_validacion_json"] or "{}")
        tipo_campana = reglas_val_json.get("tipo_campana") # MAIL, MAIL_INF, SMS

        # Columnas de salida
        cols_visibles_raw = json.loads(estrategia_dict["columnas_visibles"] or "[]")
        lista_cols_finales = [c['field'].lower() for c in cols_visibles_raw] if cols_visibles_raw else []

        # EXTRACCIÓN
        info_tabla = db_operations._get_table_info("cliente_table_map", cliente_codigo)
        db_gen_datos = get_db_session(info_tabla["db_key"])
        try:
            db_session_datos = next(db_gen_datos)
            _, datos = db_operations.obtener_todos_los_datos_filtrados(db_session_datos, cliente_codigo, filtros)
            df_completo = pd.DataFrame(datos)
            df_completo.columns = df_completo.columns.str.lower().str.strip()
            
            # --- 1. NORMALIZACIÓN PREVIA ---
            # Normalizamos teléfonos (agrega 56)
            df_completo = normalizar_telefonos(df_completo)
            
            df_pre_validado = df_completo
            df_rechazados_mail = pd.DataFrame()

            # --- 2. CONSOLIDACIÓN DE CORREOS (Solo si es MAIL) ---
            if tipo_campana in ["MAIL", "MAIL_INF"]:
                df_pre_validado, df_rechazados_mail = procesar_consolidacion_emails(df_completo)
            
            # --- 3. VALIDACIÓN TÉCNICA ---
            if tipo_campana:
                try:
                    validar_tipo_campana(df_pre_validado, tipo_campana)
                except ValueError as ve:
                    raise Exception(f"Validación Técnica: {ve}")

            # --- 4. INHIBICIÓN SQL ---
            df_filtrado_sql = df_pre_validado
            df_rechazados_sql = pd.DataFrame()

            if tipo_campana:
                query = obtener_query_inhibicion(tipo_campana, cliente_codigo)
                if query:
                    logger.info(f"Ejecutando inhibición SQL...")
                    res_sql = db_session_datos.execute(text(query))
                    df_sql = pd.DataFrame(res_sql.fetchall(), columns=res_sql.keys())
                    df_sql.columns = df_sql.columns.str.lower().str.strip()
                    
                    col_cruce = "rut" if "rut" in df_completo.columns else "idempresa"
                    if col_cruce in df_sql.columns:
                        df_pre_validado[col_cruce] = df_pre_validado[col_cruce].astype(str).str.strip()
                        df_sql[col_cruce] = df_sql[col_cruce].astype(str).str.strip()
                        
                        df_filtrado_sql = pd.merge(df_pre_validado, df_sql, on=col_cruce, how="inner")
                        
                        mask_rech = ~df_pre_validado[col_cruce].isin(df_filtrado_sql[col_cruce])
                        df_rechazados_sql = df_pre_validado[mask_rech].copy()
                        df_rechazados_sql["motivo_rechazo"] = "Inhibición SQL (Negocio)"
        finally:
            db_gen_datos.close()

        # --- 5. LIMPIEZA DUPLICADOS ---
        # Pasamos tipo_campana para que sepa si debe limpiar teléfonos o no
        df_validado, df_rech_dups = limpiar_duplicados_dataframe(df_filtrado_sql, tipo_campana)
        
        # --- 6. CONSOLIDACIÓN DE RECHAZADOS ---
        # Concatenamos todos los rechazos
        df_rech_total = pd.concat([df_rechazados_mail, df_rechazados_sql, df_rech_dups])
        
        output_dir = "campanas_generadas"
        if not os.path.exists(output_dir): os.makedirs(output_dir)
        
        archivos_generados = []
        if not df_rech_total.empty:
            # Reordenar columnas para que 'motivo_rechazo' sea la primera
            cols_rech = df_rech_total.columns.tolist()
            if 'motivo_rechazo' in cols_rech:
                cols_rech.insert(0, cols_rech.pop(cols_rech.index('motivo_rechazo')))
            
            # IMPORTANTE: Guardar con TODAS las columnas para consistencia
            ruta_rechazos = f"{output_dir}/{task_id}_RECHAZADOS.xlsx"
            df_rech_total[cols_rech].to_excel(ruta_rechazos, index=False)
            archivos_generados.append(f"{task_id}_RECHAZADOS.xlsx")

        # --- 7. DIVISIÓN Y EXPORTACIÓN (df_validado) ---
        config_proc = json.loads(plantilla_dict["reglas_procesamiento_json"] or "{}")
        cols_div = config_proc.get("columnas_division") or []
        if isinstance(cols_div, str): cols_div = [cols_div]
        cols_div = [c.lower() for c in cols_div]
        cols_validas_div = [c for c in cols_div if c in df_validado.columns]

        def guardar_grupo(df_g, nombre_archivo):
            ruta = f"{output_dir}/{nombre_archivo}"
            # Filtrar columnas finales (Si mail fue consolidada, aseguramos que esté)
            cols_exportar = df_g.columns.tolist()
            if lista_cols_finales:
                cols_norm = {c.lower(): c for c in df_g.columns}
                # Mapeamos las solicitadas. Si pedían 'mail1' pero ahora es 'mail', hacemos el ajuste
                final_selection = []
                for c_req in lista_cols_finales:
                    if c_req in cols_norm:
                        final_selection.append(cols_norm[c_req])
                    elif "mail" in c_req and "mail" in cols_norm:
                        # Si pedían mail1, mail2, etc, y ahora solo existe 'mail', agregamos 'mail'
                        if cols_norm["mail"] not in final_selection:
                            final_selection.append(cols_norm["mail"])
                
                if final_selection: cols_exportar = final_selection

            df_g[cols_exportar].to_excel(ruta, index=False)
            return nombre_archivo

        if not cols_validas_div:
            archivos_generados.append(guardar_grupo(df_validado, f"{task_id}_GLOBAL.xlsx"))
        else:
            for nombre_grupo, df_grupo in df_validado.groupby(cols_validas_div):
                grupo_str = "_".join(map(str, nombre_grupo)) if isinstance(nombre_grupo, tuple) else str(nombre_grupo)
                safe_name = grupo_str.replace("/", "-").replace("\\", "-").replace(" ", "")
                
                if plantilla_dict["modo_salida"] == "api":
                    archivos_generados.append(f"API: {grupo_str} (Simulado)")
                else:
                    archivos_generados.append(guardar_grupo(df_grupo, f"{task_id}_{safe_name}.xlsx"))

        # RESUMEN
        resumen = {
            "total_registros": len(df_completo),
            "total_validos": len(df_validado),
            "total_rechazados": len(df_rech_total),
            "detalle_rechazo": df_rech_total['motivo_rechazo'].value_counts().to_dict() if not df_rech_total.empty else {}
        }

        tasks_db[task_id] = {"status": "complete", "data": {"archivos": archivos_generados, "resumen": resumen}}
        logger.info("Pipeline finalizado.")

    except Exception as e:
        logger.error(f"Error pipeline: {e}", exc_info=True)
        tasks_db[task_id] = {"status": "error", "error_message": str(e)}
    finally:
        if db_session: db_gen.close()