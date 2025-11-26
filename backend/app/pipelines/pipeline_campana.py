import logging
import pandas as pd
import json
import os
import numpy as np
from datetime import datetime
from sqlalchemy import text
from app import db_operations, db_plantillas_operations
from app.database import get_db_session

# Importar pipelines especializados
from app.pipelines import validaciones_pipeline
from app.pipelines import calculos_pipeline 
from app import db_bulk_operations

logger = logging.getLogger(__name__)
tasks_db: dict = {}

# --- FUNCIONES AUXILIARES ---

def verificar_cancelacion(task_id: str):
    """Verifica si la tarea fue cancelada por el usuario."""
    task = tasks_db.get(task_id)
    if task and task.get("status") == "cancelled":
        raise InterruptedError("Tarea cancelada por el usuario.")

def formatear_miles(val):
    """Convierte 10000 -> 100.000 (Formato visual con punto)"""
    try:
        if pd.isna(val) or val == "": return ""
        f = float(val)
        return "{:,.0f}".format(f).replace(",", ".")
    except:
        return val

def aplicar_formato_visual(df_raw):
    """Aplica formato de miles a TODAS las columnas numéricas"""
    if df_raw.empty: return df_raw
    df_fmt = df_raw.copy()
    # Evitar formatear columnas que son IDs o códigos
    cols_ignorar = ['id', 'rut', 'fono', 'tel', 'celular', 'codigo', 'code', 'ic', 'idempresa']
    
    for col in df_fmt.select_dtypes(include=['number']).columns:
        if any(x in col.lower() for x in cols_ignorar):
            continue
        df_fmt[col] = df_fmt[col].apply(formatear_miles)
    return df_fmt

def obtener_registros_finales_masiv_dia(cliente: str, db_session_b2c) -> pd.DataFrame:
    try:
        query = text("""
            SELECT * FROM B2C.dbo.masiv_dia WITH (NOLOCK)
            WHERE cliente = :c AND CONVERT(DATE, fecha_ges) = CONVERT(DATE, GETDATE())
        """)
        result = db_session_b2c.execute(query, {"c": cliente})
        df_validos = pd.DataFrame(result.fetchall(), columns=result.keys())
        if not df_validos.empty:
            df_validos.columns = df_validos.columns.str.lower().str.strip()
        return df_validos
    except Exception as e:
        logger.error(f"Error al obtener registros finales: {e}", exc_info=True)
        return pd.DataFrame()

# --- PIPELINE PRINCIPAL ---
def ejecutar_pipeline_campana(id_plantilla: int, task_id: str, db_key_b2c: str):
    logger.info(f"[Task {task_id}] Iniciando pipeline completo...")
    
    df_rechazados_total = pd.DataFrame()
    df_validado = pd.DataFrame()
    archivos_generados = []
    total_inicial = 0
    
    db_gen_b2c = get_db_session(db_key_b2c) 
    db_session_b2c = None
    
    try:
        verificar_cancelacion(task_id)
        db_session_b2c = next(db_gen_b2c)
        
        # --- PASO 1: CARGAR CONFIGURACIÓN ---
        logger.info(f"[Task {task_id}] Paso 1: Cargando configuración...")
        plantilla_dict = db_plantillas_operations.cargar_plantilla_db(db_session_b2c, id_plantilla)
        estrategia_dict = db_operations.cargar_una_estrategia_db(db_session_b2c, plantilla_dict["id_estrategia_base"])
        
        cliente_codigo = estrategia_dict["codigo_cliente"]
        filtros = json.loads(estrategia_dict["filtros_aplicados"] or "{}")
        
        reglas_val_json = json.loads(plantilla_dict["reglas_validacion_json"] or "{}")
        tipo_campana = reglas_val_json.get("tipo_campana")

        reglas_proc_json = json.loads(plantilla_dict["reglas_procesamiento_json"] or "{}")
        proveedor_seleccionado = reglas_proc_json.get("proveedor")
        
        cols_visibles_raw = json.loads(estrategia_dict["columnas_visibles"] or "[]")
        lista_cols_finales = [c['field'].lower() for c in cols_visibles_raw] if cols_visibles_raw else []
        
        cols_mails_estrategia = [c for c in lista_cols_finales if "mail" in c or "correo" in c]
        cols_fonos_estrategia = [c for c in lista_cols_finales if "fono" in c or "tel" in c]

        # Selección Columna Única
        email_mode = reglas_proc_json.get("estrategia_email", "jerarquia")
        email_col = reglas_proc_json.get("columna_email_elegida")
        if tipo_campana in ["MAIL", "MAIL_INF"] and email_mode == "unica" and email_col:
            if email_col.lower() in lista_cols_finales:
                cols_mails_estrategia = [email_col.lower()]
                logger.info(f"[Task {task_id}] Modo Email Único: {cols_mails_estrategia}")

        fono_mode = reglas_proc_json.get("estrategia_fono", "jerarquia")
        fono_col = reglas_proc_json.get("columna_fono_elegida")
        if tipo_campana == "SMS" and fono_mode == "unica" and fono_col:
            if fono_col.lower() in lista_cols_finales:
                cols_fonos_estrategia = [fono_col.lower()]
                logger.info(f"[Task {task_id}] Modo Fono Único: {cols_fonos_estrategia}")

        now = datetime.now()
        fecha_str = now.strftime("%d%m%Y") 
        hora_str = now.strftime("%H%M").lstrip('0') 
        prefijo_archivo = f"{cliente_codigo}_{fecha_str}_{hora_str}"

        # --- PASO 2: EXTRACCIÓN (BD Operativa) ---
        verificar_cancelacion(task_id)
        logger.info(f"[Task {task_id}] Paso 2: Extrayendo datos (Cliente: {cliente_codigo})...")
        info_tabla = db_operations._get_table_info("cliente_table_map", cliente_codigo)
        db_gen_datos = get_db_session(info_tabla["db_key"])
        db_session_datos = next(db_gen_datos)
        
        try:
            _, datos = db_operations.obtener_todos_los_datos_filtrados(db_session_datos, cliente_codigo, filtros)
            verificar_cancelacion(task_id)

            df_completo = pd.DataFrame(datos)
            df_completo.columns = df_completo.columns.str.lower().str.strip()
            total_inicial = len(df_completo)
            logger.info(f"Registros extraídos: {total_inicial}")
            
            df_validado = df_completo.copy()

            # --- FASE A: FILTROS DE RUT ---
            df_validado, df_rech_hoy = validaciones_pipeline.validar_gestionados_hoy(
                df_validado, cliente_codigo, db_session_b2c, task_id 
            )
            if not df_rech_hoy.empty:
                df_rechazados_total = pd.concat([df_rechazados_total, df_rech_hoy])
            
            verificar_cancelacion(task_id)

            df_validado, df_rech_seg = validaciones_pipeline.validar_inhibicion_segmento(
                df_validado, tipo_campana, cliente_codigo, db_session_datos, task_id
            )
            if not df_rech_seg.empty:
                df_rechazados_total = pd.concat([df_rechazados_total, df_rech_seg])

            verificar_cancelacion(task_id)

            # --- FASE B: PROCESAMIENTO DE CONTACTOS ---
            if tipo_campana in ["MAIL", "MAIL_INF"]:
                # 1. Inhibición SP
                df_validado, _ = validaciones_pipeline.validar_inhibicion_con_sp(
                    df_validado, cliente_codigo, tipo_campana, db_session_b2c, task_id, cols_mails_estrategia
                )
                
                # --- COMMIT CRÍTICO: Guardar logs de inhibición mail INMEDIATAMENTE ---
                db_session_b2c.commit()
                # --------------------------------------------------------------------

                verificar_cancelacion(task_id)

                # 2. Consolidación
                df_validado, df_rech_mail = validaciones_pipeline.procesar_emails_jerarquia(
                    df_validado, task_id, cols_mail_estrategia=cols_mails_estrategia
                )
                if not df_rech_mail.empty:
                    df_rechazados_total = pd.concat([df_rechazados_total, df_rech_mail])

            elif tipo_campana == "SMS":
                # 1. Normalizar
                df_validado = validaciones_pipeline.normalizar_telefonos(
                    df_validado, task_id, cols_fono_estrategia=cols_fonos_estrategia
                )
                
                # 2. Inhibición SP
                df_validado, _ = validaciones_pipeline.validar_inhibicion_con_sp(
                    df_validado, cliente_codigo, tipo_campana, db_session_b2c, task_id, cols_fonos_estrategia
                )
                
                # --- COMMIT CRÍTICO: Guardar logs de inhibición sms INMEDIATAMENTE ---
                db_session_b2c.commit()
                # -------------------------------------------------------------------

                verificar_cancelacion(task_id)

                # 3. Consolidación SMS
                df_validado, df_rech_sms_cons = validaciones_pipeline.procesar_telefonos_jerarquia(
                    df_validado, task_id, cols_fono_estrategia=cols_fonos_estrategia
                )
                if not df_rech_sms_cons.empty:
                     df_rechazados_total = pd.concat([df_rechazados_total, df_rech_sms_cons])

                # 4. Validación Técnica
                df_validado, df_rech_tec = validaciones_pipeline.validar_tecnicamente(
                    df_validado, tipo_campana, task_id
                )
                if not df_rech_tec.empty:
                    df_rechazados_total = pd.concat([df_rechazados_total, df_rech_tec])

            # --- FASE C: DUPLICADOS FINALES ---
            df_validado, df_rech_dup = validaciones_pipeline.validar_duplicados(
                df_validado, tipo_campana, cliente_codigo, task_id
            )
            if not df_rech_dup.empty:
                df_rechazados_total = pd.concat([df_rechazados_total, df_rech_dup])

        finally:
            db_gen_datos.close()

        verificar_cancelacion(task_id)

        # --- PASO 6: CARGA FINAL EN 'masiv_dia' ---
        logger.info(f"[Task {task_id}] Paso 6: Cargando {len(df_validado)} registros válidos a 'masiv_dia'...")
        db_bulk_operations.bulk_insert_final(df_validado, cliente_codigo, tipo_campana, task_id)

        verificar_cancelacion(task_id)

        # --- PASO 7: GUARDAR RECHAZADOS (CSV) ---
        logger.info(f"[Task {task_id}] Paso 7: Guardando reporte de rechazados...")
        output_dir = "campanas_generadas"
        output_dir = os.path.join(output_dir, cliente_codigo, fecha_str)
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        archivos_generados = []
        if not df_rechazados_total.empty:
            nombre_rechazados = f"{prefijo_archivo}_RECHAZADOS.csv"
            ruta_rechazos = os.path.join(output_dir, nombre_rechazados)
            
            cols_base = ['motivo_rechazo', 'rut', 'idempresa', 'mail', 'telefono']
            cols_rech = [c.lower() for c in cols_base]
            for c in lista_cols_finales:
                if c.lower() not in cols_rech: cols_rech.append(c.lower())
            
            cols_existentes = [c for c in cols_rech if c in df_rechazados_total.columns]
            if not cols_existentes: cols_existentes = df_rechazados_total.columns.tolist()
            
            for c in ['rut', 'motivo_rechazo']:
                if c not in df_rechazados_total.columns: df_rechazados_total[c] = ""
            
            # Aplicar formato visual
            df_rech_fmt = aplicar_formato_visual(df_rechazados_total[cols_existentes])
            
            df_rech_fmt.to_csv(ruta_rechazos, index=False, sep=';', encoding='utf-8-sig')
            archivos_generados.append(f"{cliente_codigo}/{fecha_str}/{nombre_rechazados}")

        # --- PASO 8: DIVISIÓN, CÁLCULO Y PROVEEDOR ---
        logger.info(f"[Task {task_id}] Paso 8: Procesando y generando archivos finales...")
        
        cols_div = [c.lower() for c in (reglas_proc_json.get("columnas_division") or [])]
        if isinstance(cols_div, str): cols_div = [cols_div]
        cols_validas_div = [c for c in cols_div if c in df_validado.columns]
        
        reglas_segmentacion = reglas_proc_json.get("segmentacion", [])

        def guardar_grupo(df_g, sufijo_nombre, columnas_extra=[]):
            nombre_final = f"{prefijo_archivo}_{sufijo_nombre}.csv"
            ruta = os.path.join(output_dir, nombre_final)
            
            # 1. Lógica Proveedor
            from app.pipelines import proveedores_logic
            df_final = proveedores_logic.aplicar_logica_proveedor(df_g.copy(), proveedor_seleccionado)

            cols_exportar = []
            if lista_cols_finales:
                cols_norm = {c.lower(): c for c in df_final.columns}
                for c_req in lista_cols_finales:
                    if "mail" in c_req and tipo_campana in ["MAIL", "MAIL_INF"]:
                         if "mail" in cols_norm and cols_norm["mail"] not in cols_exportar:
                             cols_exportar.append(cols_norm["mail"])
                    elif c_req in cols_norm:
                        cols_exportar.append(cols_norm[c_req])
                
                for cc in columnas_extra:
                    if cc and cc in df_final.columns and cc not in cols_exportar:
                        cols_exportar.append(cc)
                
                if proveedor_seleccionado == "FIDELIZADOR" and "id_fidelizador" in df_final.columns:
                     if "id_fidelizador" not in cols_exportar: cols_exportar.insert(0, "id_fidelizador")

                if not cols_exportar: cols_exportar = df_final.columns.tolist()
            else:
                cols_exportar = df_final.columns.tolist()
            
            # 2. Formato Visual
            df_to_save = aplicar_formato_visual(df_final[cols_exportar])
            
            df_to_save.to_csv(ruta, index=False, sep=';', encoding='utf-8-sig')
            return f"{cliente_codigo}/{fecha_str}/{nombre_final}"

        def procesar_y_guardar(df_bloque, nombre_base):
            archivos = []
            
            if not reglas_segmentacion or (len(reglas_segmentacion) == 1 and reglas_segmentacion[0].get('id') == 'base'):
                seg_base = reglas_segmentacion[0] if reglas_segmentacion else {}
                reglas_calc = {"formulas": seg_base.get("formulas", []), "columnas_estaticas": seg_base.get("columnas_estaticas", [])}
                
                df_proc, nuevas_cols = calculos_pipeline.procesar_calculos(df_bloque.copy(), reglas_calc, lista_cols_finales)
                archivos.append(guardar_grupo(df_proc, nombre_base, nuevas_cols))
                return archivos

            registros_restantes = df_bloque.copy()
            
            for regla in reglas_segmentacion:
                sufijo = regla.get("sufijo", "SEG")
                reglas_calc = { "formulas": regla.get("formulas", []), "columnas_estaticas": regla.get("columnas_estaticas", []) }
                condiciones = regla.get("condiciones", [])
                
                if regla.get("id") == 'else' or regla.get("condicion") == 'else':
                     if not registros_restantes.empty:
                        df_proc, nuevas = calculos_pipeline.procesar_calculos(registros_restantes.copy(), reglas_calc, lista_cols_finales)
                        archivos.append(guardar_grupo(df_proc, f"{nombre_base}_{sufijo}", nuevas))
                     registros_restantes = pd.DataFrame()
                     continue

                mask_total = None
                for cond in condiciones:
                    col = cond.get("columna", "").lower().strip()
                    op = cond.get("operador", "")
                    val = cond.get("valor", "")
                    mask_cond = None
                    try:
                        if op == "==": mask_cond = registros_restantes[col].astype(str) == str(val)
                        elif op == "!=": mask_cond = registros_restantes[col].astype(str) != str(val)
                        elif op == ">": mask_cond = pd.to_numeric(registros_restantes[col], errors='coerce') > float(val)
                        elif op == "<": mask_cond = pd.to_numeric(registros_restantes[col], errors='coerce') < float(val)
                        elif op == ">=": mask_cond = pd.to_numeric(registros_restantes[col], errors='coerce') >= float(val)
                        elif op == "<=": mask_cond = pd.to_numeric(registros_restantes[col], errors='coerce') <= float(val)
                        elif op == "contiene": mask_cond = registros_restantes[col].astype(str).str.contains(str(val), case=False, na=False)
                        elif op == "es_nulo": mask_cond = registros_restantes[col].isna() | (registros_restantes[col].astype(str).str.strip() == "") | (registros_restantes[col].astype(str).str.lower() == "nan")
                        elif op == "no_es_nulo": mask_cond = registros_restantes[col].notna() & (registros_restantes[col].astype(str).str.strip() != "") & (registros_restantes[col].astype(str).str.lower() != "nan")
                    except: pass

                    if mask_cond is not None:
                        mask_total = mask_cond if mask_total is None else (mask_total & mask_cond)
                
                if mask_total is not None and mask_total.any():
                     df_seg = registros_restantes[mask_total].copy()
                     df_proc, nuevas = calculos_pipeline.procesar_calculos(df_seg, reglas_calc, lista_cols_finales)
                     archivos.append(guardar_grupo(df_proc, f"{nombre_base}_{sufijo}", nuevas))
                     registros_restantes = registros_restantes[~mask_total]

            if not registros_restantes.empty:
                 archivos.append(guardar_grupo(registros_restantes, nombre_base))
            
            return archivos

        if not cols_validas_div or df_validado.empty:
            if not df_validado.empty:
                archivos_generados.extend(procesar_y_guardar(df_validado, "GLOBAL"))
        else:
            for nombre_grupo, df_grupo in df_validado.groupby(cols_validas_div):
                verificar_cancelacion(task_id)
                n = "_".join(map(str, nombre_grupo)) if isinstance(nombre_grupo, tuple) else str(nombre_grupo)
                safe_seg = n.replace("/", "-").replace("\\", "-").replace(" ", "")
                archivos_generados.extend(procesar_y_guardar(df_grupo, safe_seg))

        logger.info(f"[Task {task_id}] Pipeline finalizado.")
        resumen = {
            "total_registros": total_inicial,
            "total_validos": len(df_validado),
            "total_rechazados": len(df_rechazados_total),
            "detalle_rechazo": df_rechazados_total['motivo_rechazo'].value_counts().to_dict() if not df_rechazados_total.empty else {}
        }
        tasks_db[task_id] = {"status": "complete", "data": {"archivos": archivos_generados, "resumen": resumen}}

    except InterruptedError as e:
        logger.warning(f"[Task {task_id}] DETENIDO: {e}")
        tasks_db[task_id]["status"] = "cancelled" 
    except Exception as e:
        logger.error(f"Error pipeline: {e}", exc_info=True)
        tasks_db[task_id] = {"status": "error", "error_message": str(e)}
    finally:
        if db_session_b2c: db_gen_b2c.close()