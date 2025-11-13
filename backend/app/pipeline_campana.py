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

# --- 0. NORMALIZACIÓN (Agrega 56 si falta) ---
def normalizar_telefonos(df):
    phone_cols = [c for c in df.columns if "fono" in c or "tel" in c]
    if not phone_cols: return df

    logger.info("Normalizando teléfonos...")
    for col in phone_cols:
        # Convertir a string, quitar decimales (.0) si vienen de excel numérico
        df[col] = df[col].astype(str).replace(r'\.0$', '', regex=True).str.strip()
        
        # Limpiar nulos
        mask_nulos = df[col].isin(['nan', 'None', 'NaT', '', '0'])
        df.loc[mask_nulos, col] = ""
        
        # Si tiene datos y no empieza con 56, agregarlo
        mask_fix = (~mask_nulos) & (~df[col].str.startswith("56"))
        if mask_fix.any():
            df.loc[mask_fix, col] = "56" + df.loc[mask_fix, col]
    return df

# --- 1. VALIDACIÓN TÉCNICA ---
def validar_tipo_campana(df, tipo_campana):
    df.columns = df.columns.str.lower().str.strip()
    
    if tipo_campana == "SMS":
        cols_tel = [c for c in df.columns if "fono" in c or "tel" in c]
        if not cols_tel: raise ValueError("Para SMS falta columna de teléfono.")
        if "mensaje" not in df.columns: raise ValueError("Para SMS falta columna 'mensaje'.")
        
        # Validar largo
        largos = df[df["mensaje"].astype(str).str.len() > 160]
        if not largos.empty: raise ValueError(f"{len(largos)} mensajes exceden 160 caracteres.")
        
        # Validar formato (Solo para SMS es crítico)
        for col in cols_tel:
            invalidos = df[(df[col] != "") & (~df[col].str.startswith("56"))]
            if not invalidos.empty: 
                raise ValueError(f"Columna '{col}': {len(invalidos)} números inválidos (no empiezan con 56).")

    elif tipo_campana in ["MAIL", "MAIL_INF"]:
        if "rut" not in df.columns and "idempresa" not in df.columns:
             raise ValueError("Para Mail se requiere columna 'rut' o 'idempresa'.")

# --- 2. LIMPIEZA DE DUPLICADOS ---
def limpiar_duplicados_dataframe(df):
    df_clean = df.copy()
    df_clean.columns = df_clean.columns.str.lower().str.strip()
    df_duplicates_total = pd.DataFrame()

    # RUT
    if "rut" in df_clean.columns:
        mask_dup = df_clean.duplicated(subset=["rut"], keep="first")
        if mask_dup.any():
            dups = df_clean[mask_dup].copy()
            dups["motivo_rechazo"] = "RUT Duplicado"
            df_duplicates_total = pd.concat([df_duplicates_total, dups])
            df_clean = df_clean[~mask_dup]

    # Email
    email_cols = [c for c in df_clean.columns if "mail" in c or "correo" in c]
    if email_cols:
        col = email_cols[0]
        mask_dup = df_clean.duplicated(subset=[col], keep="first")
        if mask_dup.any():
            dups = df_clean[mask_dup].copy()
            dups["motivo_rechazo"] = "Email Duplicado"
            df_duplicates_total = pd.concat([df_duplicates_total, dups])
            df_clean = df_clean[~mask_dup]

    # Teléfono
    phone_cols = [c for c in df_clean.columns if "fono" in c or "tel" in c]
    if phone_cols:
        col = phone_cols[0]
        mask_dup = df_clean.duplicated(subset=[col], keep="first")
        if mask_dup.any():
            dups = df_clean[mask_dup].copy()
            dups["motivo_rechazo"] = "Teléfono Duplicado"
            df_duplicates_total = pd.concat([df_duplicates_total, dups])
            df_clean = df_clean[~mask_dup]

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
        
        # CARGA
        plantilla_dict = db_plantillas_operations.cargar_plantilla_db(db_session, id_plantilla)
        estrategia_dict = db_operations.cargar_una_estrategia_db(db_session, plantilla_dict["id_estrategia_base"])
        
        cliente_codigo = estrategia_dict["codigo_cliente"]
        filtros = json.loads(estrategia_dict["filtros_aplicados"] or "{}")
        reglas_val_json = json.loads(plantilla_dict["reglas_validacion_json"] or "{}")
        tipo_campana = reglas_val_json.get("tipo_campana")
        
        cols_visibles_raw = json.loads(estrategia_dict["columnas_visibles"] or "[]")
        lista_cols_finales = [c['field'].lower() for c in cols_visibles_raw] if cols_visibles_raw else []

        # EXTRACCIÓN
        info_tabla = db_operations._get_table_info("cliente_table_map", cliente_codigo)
        db_gen_datos = get_db_session(info_tabla["db_key"])
        try:
            db_session_datos = next(db_gen_datos)
            _, datos = db_operations.obtener_todos_los_datos_filtrados(db_session_datos, cliente_codigo, filtros)
            df_completo = pd.DataFrame(datos)
            
            # Normalizar columnas
            df_completo.columns = df_completo.columns.str.lower().str.strip()
            
            # --- NORMALIZACIÓN ---
            df_completo = normalizar_telefonos(df_completo)
            
            # --- VALIDACIÓN TÉCNICA ---
            if tipo_campana:
                try:
                    validar_tipo_campana(df_completo, tipo_campana)
                except ValueError as ve:
                    raise Exception(f"Error Validación: {ve}")

            # --- INHIBICIÓN SQL ---
            df_filtrado_sql = df_completo
            df_rechazados_sql = pd.DataFrame()

            if tipo_campana:
                query = obtener_query_inhibicion(tipo_campana, cliente_codigo)
                if query:
                    res_sql = db_session_datos.execute(text(query))
                    df_sql = pd.DataFrame(res_sql.fetchall(), columns=res_sql.keys())
                    df_sql.columns = df_sql.columns.str.lower().str.strip()
                    
                    col_cruce = "rut" if "rut" in df_completo.columns else "idempresa"
                    if col_cruce in df_sql.columns:
                        # Cruce seguro como string
                        df_completo[col_cruce] = df_completo[col_cruce].astype(str).str.strip()
                        df_sql[col_cruce] = df_sql[col_cruce].astype(str).str.strip()
                        
                        df_filtrado_sql = pd.merge(df_completo, df_sql, on=col_cruce, how="inner")
                        
                        mask_rech = ~df_completo[col_cruce].isin(df_filtrado_sql[col_cruce])
                        df_rechazados_sql = df_completo[mask_rech].copy()
                        df_rechazados_sql["motivo_rechazo"] = "Inhibición SQL (Regla Negocio)"
        finally:
            db_gen_datos.close()

        # --- LIMPIEZA DUPLICADOS ---
        df_validado, df_rech_dups = limpiar_duplicados_dataframe(df_filtrado_sql)
        
        # Guardar Rechazados
        df_rech_total = pd.concat([df_rechazados_sql, df_rech_dups])
        output_dir = "campanas_generadas"
        if not os.path.exists(output_dir): os.makedirs(output_dir)
        
        archivos_generados = []
        if not df_rech_total.empty:
            # Aseguramos que la columna motivo esté al principio
            cols = ['motivo_rechazo'] + [c for c in df_rech_total.columns if c != 'motivo_rechazo']
            df_rech_total[cols].to_excel(f"{output_dir}/{task_id}_RECHAZADOS.xlsx", index=False)
            archivos_generados.append(f"{task_id}_RECHAZADOS.xlsx")

        # --- DIVISIÓN ---
        config_proc = json.loads(plantilla_dict["reglas_procesamiento_json"] or "{}")
        cols_div = config_proc.get("columnas_division") or []
        if isinstance(cols_div, str): cols_div = [cols_div]
        cols_div = [c.lower() for c in cols_div]
        cols_validas_div = [c for c in cols_div if c in df_validado.columns]

        def guardar_grupo(df_g, nombre_archivo):
            ruta = f"{output_dir}/{nombre_archivo}"
            cols_exportar = df_g.columns.tolist()
            if lista_cols_finales:
                cols_norm = {c.lower(): c for c in df_g.columns}
                cols_exportar = [cols_norm[c] for c in lista_cols_finales if c in cols_norm]
                if not cols_exportar: cols_exportar = df_g.columns.tolist()
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

        # --- GENERAR RESUMEN ESTADÍSTICO ---
        resumen = {
            "total_registros": len(df_completo),
            "total_validos": len(df_validado),
            "total_rechazados": len(df_rech_total),
            "detalle_rechazo": df_rech_total['motivo_rechazo'].value_counts().to_dict() if not df_rech_total.empty else {}
        }

        tasks_db[task_id] = {
            "status": "complete", 
            "data": {
                "archivos": archivos_generados,
                "resumen": resumen
            }
        }
        logger.info("Pipeline finalizado con éxito.")

    except Exception as e:
        logger.error(f"Error pipeline: {e}", exc_info=True)
        tasks_db[task_id] = {"status": "error", "error_message": str(e)}
    finally:
        if db_session: db_gen.close()