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
from app.pipelines import proveedores_logic 
from app import db_bulk_operations

logger = logging.getLogger(__name__)
tasks_db: dict = {}

# --- FUNCIONES AUXILIARES ---

def verificar_cancelacion(task_id: str):
    """Verifica si la tarea fue cancelada por el usuario."""
    task = tasks_db.get(task_id)
    if task and task.get("status") == "cancelled":
        raise InterruptedError("Tarea cancelada por el usuario.")

def actualizar_paso(task_id: str, mensaje: str):
    """Actualiza el mensaje de progreso para que el frontend lo lea."""
    if task_id in tasks_db:
        tasks_db[task_id]["step"] = mensaje

def formatear_miles(val):
    """Convierte 10000 -> 100.000 (Formato visual con punto)"""
    try:
        if pd.isna(val) or str(val).strip() == "": return ""
        f = float(val)
        return "{:,.0f}".format(f).replace(",", ".")
    except:
        return val

def aplicar_formato_visual(df_raw):
    """Aplica formato de miles a TODAS las columnas numéricas"""
    if df_raw.empty: return df_raw
    df_fmt = df_raw.copy()
    # Evitar formatear columnas que son IDs o códigos
    cols_ignorar = ['id', 'rut', 'fono', 'tel', 'celular', 'codigo', 'code', 'ic', 'idempresa', 'numero']
    
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
    actualizar_paso(task_id, "Iniciando proceso...")
    
    # Inicialización de variables
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
        actualizar_paso(task_id, "Cargando configuración...")
        plantilla_dict = db_plantillas_operations.cargar_plantilla_db(db_session_b2c, id_plantilla)
        estrategia_dict = db_operations.cargar_una_estrategia_db(db_session_b2c, plantilla_dict["id_estrategia_base"])
        
        cliente_codigo = estrategia_dict["codigo_cliente"]
        filtros = json.loads(estrategia_dict["filtros_aplicados"] or "{}")
        
        reglas_val_json = json.loads(plantilla_dict["reglas_validacion_json"] or "{}")
        tipo_campana = reglas_val_json.get("tipo_campana")

        reglas_proc_json = json.loads(plantilla_dict["reglas_procesamiento_json"] or "{}")
        proveedor_seleccionado = reglas_proc_json.get("proveedor")
        mensaje_sms_template = reglas_proc_json.get("mensaje_sms_template", "")
        
        cols_visibles_raw = json.loads(estrategia_dict["columnas_visibles"] or "[]")
        lista_cols_finales = [c['field'].lower() for c in cols_visibles_raw] if cols_visibles_raw else []
        
        cols_mails_estrategia = [c for c in lista_cols_finales if "mail" in c or "correo" in c]
        cols_fonos_estrategia = [c for c in lista_cols_finales if "fono" in c or "tel" in c]

        # Selección Columna Única (EMAIL)
        email_mode = reglas_proc_json.get("estrategia_email", "jerarquia")
        email_col = reglas_proc_json.get("columna_email_elegida")
        if tipo_campana in ["MAIL", "MAIL_INF"] and email_mode == "unica" and email_col:
            if email_col.lower() in lista_cols_finales:
                cols_mails_estrategia = [email_col.lower()]
                logger.info(f"[Task {task_id}] Modo Email Único: {cols_mails_estrategia}")

        # Selección Columna Única (SMS)
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

        # --- PASO 2: EXTRACCIÓN ---
        verificar_cancelacion(task_id)
        actualizar_paso(task_id, f"Extrayendo datos del cliente {cliente_codigo}...")
        
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

            # --- NUEVO: Lógica Especial 0200ENTE (Limpiar RUT) ---
            if cliente_codigo == "0200ENTE" and "rut" in df_validado.columns:
                logger.info(f"[Task {task_id}] Aplicando limpieza especial de RUT para 0200ENTE (quitar 0s y DV)...")
                
                # 1. Guardar RUT original
                df_validado["_rut_orig"] = df_validado["rut"]
                
                # 2. Función de limpieza: 0000783498 -> 78349
                def limpiar_rut_ente(val):
                    s = str(val).strip().lstrip("0")
                    # Eliminar último caracter (DV) si queda algo
                    return s[:-1] if len(s) > 0 else s
                
                # 3. Aplicar al RUT principal (para que las validaciones usen este)
                df_validado["rut"] = df_validado["rut"].apply(limpiar_rut_ente)
            # ------------------------------------------------------

            # --- FASE A: FILTROS DE RUT ---
            actualizar_paso(task_id, "Validando gestionados hoy y segmento...")
            
            # 1. Gestionados Hoy
            df_validado, df_rech_hoy = validaciones_pipeline.validar_gestionados_hoy(
                df_validado, cliente_codigo, db_session_b2c, task_id 
            )
            if not df_rech_hoy.empty:
                df_rechazados_total = pd.concat([df_rechazados_total, df_rech_hoy])
            
            verificar_cancelacion(task_id)

            # 2. Segmento (Ley Cobranza)
            df_validado, df_rech_seg = validaciones_pipeline.validar_inhibicion_segmento(
                df_validado, tipo_campana, cliente_codigo, db_session_datos, task_id
            )
            if not df_rech_seg.empty:
                df_rechazados_total = pd.concat([df_rechazados_total, df_rech_seg])

            verificar_cancelacion(task_id)

            # --- FASE B: PROCESAMIENTO DE CONTACTOS ---
            actualizar_paso(task_id, "Procesando contactos (Inhibiciones y Consolidación)...")
            
            if tipo_campana in ["MAIL", "MAIL_INF"]:
                # Inhibición SP
                df_validado, _ = validaciones_pipeline.validar_inhibicion_con_sp(
                    df_validado, cliente_codigo, tipo_campana, db_session_b2c, task_id, cols_mails_estrategia
                )
                db_session_b2c.commit()
                verificar_cancelacion(task_id)

                # Consolidación
                df_validado, df_rech_mail = validaciones_pipeline.procesar_emails_jerarquia(
                    df_validado, task_id, cols_mail_estrategia=cols_mails_estrategia
                )
                if not df_rech_mail.empty:
                    df_rechazados_total = pd.concat([df_rechazados_total, df_rech_mail])

            elif tipo_campana == "SMS":
                # Normalizar
                df_validado = validaciones_pipeline.normalizar_telefonos(
                    df_validado, task_id, cols_fono_estrategia=cols_fonos_estrategia
                )
                
                # Inhibición SP
                df_validado, _ = validaciones_pipeline.validar_inhibicion_con_sp(
                    df_validado, cliente_codigo, tipo_campana, db_session_b2c, task_id, cols_fonos_estrategia
                )
                db_session_b2c.commit()
                verificar_cancelacion(task_id)

                # Consolidación
                df_validado, df_rech_sms_cons = validaciones_pipeline.procesar_telefonos_jerarquia(
                    df_validado, task_id, cols_fono_estrategia=cols_fonos_estrategia
                )
                if not df_rech_sms_cons.empty:
                     df_rechazados_total = pd.concat([df_rechazados_total, df_rech_sms_cons])

                # Validación Técnica
                df_validado, df_rech_tec = validaciones_pipeline.validar_tecnicamente(
                    df_validado, tipo_campana, task_id
                )
                if not df_rech_tec.empty:
                    df_rechazados_total = pd.concat([df_rechazados_total, df_rech_tec])

            elif tipo_campana == "DISC":
                # Discador solo valida RUTs (ya hecho en Fase A y C)
                pass

            # --- FASE C: DUPLICADOS FINALES ---
            actualizar_paso(task_id, "Eliminando registros duplicados...")
            df_validado, df_rech_dup = validaciones_pipeline.validar_duplicados(
                df_validado, tipo_campana, cliente_codigo, task_id
            )
            if not df_rech_dup.empty:
                df_rechazados_total = pd.concat([df_rechazados_total, df_rech_dup])

        finally:
            db_gen_datos.close()

        verificar_cancelacion(task_id)

        # --- PASO 6: CARGA FINAL ---
        actualizar_paso(task_id, f"Cargando {len(df_validado)} registros válidos a base de datos...")
        db_bulk_operations.bulk_insert_final(df_validado, cliente_codigo, tipo_campana, task_id)

        verificar_cancelacion(task_id)

        # --- PASO 7: GUARDAR RECHAZADOS ---
        actualizar_paso(task_id, "Guardando reporte de rechazados...")
        output_dir = "campanas_generadas"
        output_dir = os.path.join(output_dir, cliente_codigo, fecha_str)
        if not os.path.exists(output_dir): os.makedirs(output_dir, exist_ok=True)
        
        if not df_rechazados_total.empty:
            # --- RESTAURAR RUT ORIGINAL EN RECHAZADOS (0200ENTE) ---
            if "_rut_orig" in df_rechazados_total.columns:
                df_rechazados_total["rut"] = df_rechazados_total["_rut_orig"]
            # -------------------------------------------------------

            n_rech = f"{prefijo_archivo}_RECHAZADOS.csv"
            path_rech = os.path.join(output_dir, n_rech)
            
            cols_base = ['motivo_rechazo', 'rut', 'idempresa', 'mail', 'telefono']
            cols_rech = [c.lower() for c in cols_base]
            for c in lista_cols_finales:
                if c.lower() not in cols_rech: cols_rech.append(c.lower())
            
            cols_exist = [c for c in cols_rech if c in df_rechazados_total.columns]
            if not cols_exist: cols_exist = df_rechazados_total.columns.tolist()
            
            for c in ['rut', 'motivo_rechazo']:
                if c not in df_rechazados_total.columns: df_rechazados_total[c] = ""
            
            df_rech_fmt = aplicar_formato_visual(df_rechazados_total[cols_exist])
            df_rech_fmt.to_csv(path_rech, index=False, sep=';', encoding='utf-8-sig')
            archivos_generados.append(f"{cliente_codigo}/{fecha_str}/{n_rech}")

            # Guardar en BD
            try:
                logger.info(f"[Task {task_id}] Insertando rechazados en SQL...")
                df_db = df_rechazados_total.copy()
                df_db['fecha_proceso'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                df_db['cliente'] = cliente_codigo
                df_db['task_id'] = task_id
                df_db['archivo_origen'] = n_rech
                
                if 'rut' not in df_db.columns: df_db['rut'] = df_db.get('idempresa', '')
                if 'telefono' not in df_db.columns: df_db['telefono'] = ''
                if 'mail' not in df_db.columns: df_db['mail'] = ''
                if 'motivo_rechazo' not in df_db.columns: df_db['motivo_rechazo'] = 'Desconocido'

                cols_db_ordenadas = ['fecha_proceso', 'cliente', 'rut', 'telefono', 'mail', 'motivo_rechazo', 'archivo_origen', 'task_id']
                df_db_final = df_db[cols_db_ordenadas].fillna('')
                
                db_bulk_operations.bulk_insert_via_csv(
                    db_session_b2c, 
                    df_db_final, 
                    "B2C.dbo.RechazosHistoricos", 
                    f"rech_{task_id}", 
                    is_temp_table=False
                )
                db_session_b2c.commit()
            except Exception as e_db:
                logger.error(f"[Task {task_id}] Error guardando rechazos DB: {e_db}")

        # --- PASO 8: DIVISIÓN Y CÁLCULO ---
        actualizar_paso(task_id, "Aplicando cálculos y generando archivos finales...")
        
        # --- RESTAURAR RUT ORIGINAL EN VÁLIDOS (0200ENTE) ---
        if "_rut_orig" in df_validado.columns:
             df_validado["rut"] = df_validado["_rut_orig"]
             # Nota: No borramos _rut_orig por si acaso, pero "rut" ya tiene el valor original
        # ----------------------------------------------------

        cols_div = [c.lower() for c in (reglas_proc_json.get("columnas_division") or [])]
        if isinstance(cols_div, str): cols_div = [cols_div]
        cols_validas_div = [c for c in cols_div if c in df_validado.columns]
        reglas_segmentacion = reglas_proc_json.get("segmentacion", [])

        def guardar_grupo(df_g, sufijo_nombre, columnas_extra=[]):
            nombre_final = f"{prefijo_archivo}_{sufijo_nombre}.csv"
            ruta = os.path.join(output_dir, nombre_final)
            
            # Lógica Proveedor
            df_final = proveedores_logic.aplicar_logica_proveedor(
                df_g.copy(), 
                proveedor_seleccionado, 
                mensaje_template=mensaje_sms_template,
                cliente_codigo=cliente_codigo
            )

            cols_exportar = []
            if proveedor_seleccionado:
                cols_exportar = df_final.columns.tolist()
            else:
                if lista_cols_finales:
                    cn = {c.lower(): c for c in df_final.columns}
                    for r in lista_cols_finales:
                        if "mail" in r and tipo_campana in ["MAIL", "MAIL_INF"]:
                            if "mail" in cn and cn["mail"] not in cols_exportar: cols_exportar.append(cn["mail"])
                        elif "fono" in r and tipo_campana == "SMS":
                             if "telefono" in cn and cn["telefono"] not in cols_exportar: cols_exportar.append(cn["telefono"])
                        elif r in cn: cols_exportar.append(cn[r])
                    for e in columnas_extra: 
                        if e in df_final.columns and e not in cols_exportar: cols_exportar.append(e)
                    if not cols_exportar: cols_exportar = df_final.columns.tolist()
                else: cols_exportar = df_final.columns.tolist()
            
            df_to_save = aplicar_formato_visual(df_final[cols_exportar])
            df_to_save.to_csv(ruta, index=False, sep=';', encoding='utf-8-sig')
            return f"{cliente_codigo}/{fecha_str}/{nombre_final}"

        def procesar(bloque, base):
            arch = []
            if not reglas_segmentacion or (len(reglas_segmentacion) == 1 and reglas_segmentacion[0].get('id') == 'base'):
                sb = reglas_segmentacion[0] if reglas_segmentacion else {}
                rc = {"formulas": sb.get("formulas", []), "columnas_estaticas": sb.get("columnas_estaticas", [])}
                dp, nc = calculos_pipeline.procesar_calculos(bloque.copy(), rc, lista_cols_finales)
                arch.append(guardar_grupo(dp, base, nc))
                return arch

            restante = bloque.copy()
            for r in reglas_segmentacion:
                suf = r.get("sufijo", "SEG")
                rc = {"formulas": r.get("formulas", []), "columnas_estaticas": r.get("columnas_estaticas", [])}
                conds = r.get("condiciones", [])
                
                if r.get("id") == 'else' or r.get("condicion") == 'else':
                     if not restante.empty:
                        dp, nc = calculos_pipeline.procesar_calculos(restante.copy(), rc, lista_cols_finales)
                        arch.append(guardar_grupo(dp, f"{base}_{suf}", nc))
                     restante = pd.DataFrame()
                     continue

                mask = None
                for c in conds:
                    col, op, val = c.get("columna", "").lower().strip(), c.get("operador", ""), c.get("valor", "")
                    m = None
                    try:
                        # --- NUEVOS OPERADORES ---
                        if op == "comienza_con":
                            m = restante[col].astype(str).str.lower().str.startswith(str(val).lower(), na=False)
                        elif op == "termina_con":
                            m = restante[col].astype(str).str.lower().str.endswith(str(val).lower(), na=False)
                        elif op=="==": m = restante[col].astype(str) == str(val)
                        elif op=="!=": m = restante[col].astype(str) != str(val)
                        elif op==">": m = pd.to_numeric(restante[col], errors='coerce') > float(val)
                        elif op=="<": m = pd.to_numeric(restante[col], errors='coerce') < float(val)
                        elif op==">=": m = pd.to_numeric(restante[col], errors='coerce') >= float(val)
                        elif op=="<=": m = pd.to_numeric(restante[col], errors='coerce') <= float(val)
                        elif op=="contiene": m = restante[col].astype(str).str.contains(str(val), case=False, na=False)
                        elif op=="es_nulo": m = restante[col].isna() | (restante[col].astype(str).str.strip() == "") | (restante[col].astype(str).str.lower() == "nan")
                        elif op=="no_es_nulo": m = restante[col].notna() & (restante[col].astype(str).str.strip() != "") & (restante[col].astype(str).str.lower() != "nan")
                    except: pass
                    if m is not None: mask = m if mask is None else (mask & m)
                
                if mask is not None and mask.any():
                    seg = restante[mask].copy()
                    dp, nc = calculos_pipeline.procesar_calculos(seg, rc, lista_cols_finales)
                    arch.append(guardar_grupo(dp, f"{base}_{suf}", nc))
                    restante = restante[~mask]

            if not restante.empty: arch.append(guardar_grupo(restante, base))
            return arch

        if not cols_validas_div or df_validado.empty:
            if not df_validado.empty: archivos_generados.extend(procesar(df_validado, "GLOBAL"))
        else:
            for grp, dfg in df_validado.groupby(cols_validas_div):
                verificar_cancelacion(task_id)
                n = "_".join(map(str, grp)) if isinstance(grp, tuple) else str(grp)
                safe = n.replace("/", "-").replace("\\", "-").replace(" ", "")
                archivos_generados.extend(procesar(dfg, safe))

        actualizar_paso(task_id, "Finalizado")
        logger.info(f"[Task {task_id}] Fin.")
        st = {
            "total_registros": total_inicial,
            "total_validos": len(df_validado),
            "total_rechazados": len(df_rechazados_total),
            "detalle_rechazo": df_rechazados_total['motivo_rechazo'].value_counts().to_dict() if not df_rechazados_total.empty else {}
        }
        tasks_db[task_id] = {"status": "complete", "data": {"archivos": archivos_generados, "resumen": st}}

    except InterruptedError as e:
        logger.warning(f"[Task {task_id}] Cancelado.")
        tasks_db[task_id]["status"] = "cancelled" 
    except Exception as e:
        logger.error(f"Error pipeline: {e}", exc_info=True)
        tasks_db[task_id] = {"status": "error", "error_message": str(e)}
    finally:
        if db_session_b2c: db_gen_b2c.close()