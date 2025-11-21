import logging
import pandas as pd
import json
import os
import numpy as np
from datetime import datetime
from sqlalchemy import text
from app import db_operations, db_plantillas_operations
from app.database import get_db_session

# Importar el pipeline de validaciones (Lógica de negocio)
from app.pipelines import validaciones_pipeline
# Importar el cargador final (Lógica de base de datos)
from app import db_bulk_operations

logger = logging.getLogger(__name__)
tasks_db: dict = {}

def obtener_registros_finales_masiv_dia(cliente: str, db_session_b2c) -> pd.DataFrame:
    """Consulta masiv_dia y devuelve los registros finales y válidos."""
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

# --- PIPELINE PRINCIPAL (Orquestador) ---
def ejecutar_pipeline_campana(id_plantilla: int, task_id: str, db_key_b2c: str):
    logger.info(f"[Task {task_id}] Iniciando pipeline completo...")
    
    df_rechazados_total = pd.DataFrame()
    total_inicial = 0
    
    # Usamos 'get_db_session' manualmente para control fino
    db_gen_b2c = get_db_session(db_key_b2c) 
    db_session_b2c = None
    
    try:
        db_session_b2c = next(db_gen_b2c)
        
        # --- PASO 1: CARGAR CONFIGURACIÓN ---
        logger.info(f"[Task {task_id}] Paso 1: Cargando configuración...")
        plantilla_dict = db_plantillas_operations.cargar_plantilla_db(db_session_b2c, id_plantilla)
        estrategia_dict = db_operations.cargar_una_estrategia_db(db_session_b2c, plantilla_dict["id_estrategia_base"])
        
        cliente_codigo = estrategia_dict["codigo_cliente"]
        filtros = json.loads(estrategia_dict["filtros_aplicados"] or "{}")
        
        # Configuración de la plantilla
        reglas_val_json = json.loads(plantilla_dict["reglas_validacion_json"] or "{}")
        tipo_campana = reglas_val_json.get("tipo_campana")
        
        # Columnas de salida (Estrategia)
        cols_visibles_raw = json.loads(estrategia_dict["columnas_visibles"] or "[]")
        lista_cols_finales = [c['field'].lower() for c in cols_visibles_raw] if cols_visibles_raw else []
        
        # Identificar columnas específicas de la estrategia para validar
        cols_mails_estrategia = [c for c in lista_cols_finales if "mail" in c or "correo" in c]
        cols_fonos_estrategia = [c for c in lista_cols_finales if "fono" in c or "tel" in c]

        # Preparar prefijo de archivo: CLIENTE_FECHA_HORA
        now = datetime.now()
        fecha_str = now.strftime("%d%m%Y") 
        hora_str = now.strftime("%H%M").lstrip('0') 
        prefijo_archivo = f"{cliente_codigo}_{fecha_str}_{hora_str}"

        # --- PASO 2: EXTRACCIÓN (BD Operativa) ---
        logger.info(f"[Task {task_id}] Paso 2: Extrayendo datos (Cliente: {cliente_codigo})...")
        info_tabla = db_operations._get_table_info("cliente_table_map", cliente_codigo)
        db_gen_datos = get_db_session(info_tabla["db_key"])
        db_session_datos = next(db_gen_datos)
        
        try:
            _, datos = db_operations.obtener_todos_los_datos_filtrados(db_session_datos, cliente_codigo, filtros)
            df_completo = pd.DataFrame(datos)
            # Normalizar nombres de columnas inmediatamente
            df_completo.columns = df_completo.columns.str.lower().str.strip()
            total_inicial = len(df_completo)
            logger.info(f"Registros extraídos: {total_inicial}")
            
            df_validado = df_completo.copy()

            # --- FASE A: FILTROS GLOBALES DE RUT (Eliminación Total) ---
            
            # A.1 Gestionados Hoy (Valida contra masiv_dia en B2C)
            df_validado, df_rech_hoy = validaciones_pipeline.validar_gestionados_hoy(
                df_validado, cliente_codigo, db_session_b2c
            )
            if not df_rech_hoy.empty:
                df_rechazados_total = pd.concat([df_rechazados_total, df_rech_hoy])
            
            # A.2 Segmento (Lista Blanca SQL en Operativa)
            df_validado, df_rech_seg = validaciones_pipeline.validar_inhibicion_segmento(
                df_validado, tipo_campana, cliente_codigo, db_session_datos
            )
            if not df_rech_seg.empty:
                df_rechazados_total = pd.concat([df_rechazados_total, df_rech_seg])

            # --- FASE B: PROCESAMIENTO DE CONTACTOS (Validación y Limpieza) ---
            
            if tipo_campana in ["MAIL", "MAIL_INF"]:
                # 1. Inhibición SP: Marca con '0' los mails inhibidos (Solo columnas de estrategia)
                df_validado, _ = validaciones_pipeline.validar_inhibicion_con_sp(
                    df_validado, cliente_codigo, tipo_campana, db_session_b2c, cols_mails_estrategia
                )
                
                # 2. Consolidación: Lee en cascada ignorando los '0' y nulos
                # (Ya no pasamos cliente_codigo, solo el DF y las columnas)
                df_validado, df_rech_mail = validaciones_pipeline.procesar_emails_jerarquia(
                    df_validado, cols_mail_estrategia=cols_mails_estrategia
                )
                if not df_rech_mail.empty:
                    df_rechazados_total = pd.concat([df_rechazados_total, df_rech_mail])

            elif tipo_campana == "SMS":
                # 1. Normalizar Teléfonos (Solo columnas de estrategia, agrega '56')
                df_validado = validaciones_pipeline.normalizar_telefonos(
                    df_validado, cols_fono_estrategia=cols_fonos_estrategia
                )
                
                # 2. Inhibición SP: Marca con '0' los fonos inhibidos
                df_validado, _ = validaciones_pipeline.validar_inhibicion_con_sp(
                    df_validado, cliente_codigo, tipo_campana, db_session_b2c, cols_fonos_estrategia
                )
                
                # 3. Validación Técnica: Rechaza si fono es '0', vacío o mal formato
                df_validado, df_rech_tec = validaciones_pipeline.validar_tecnicamente(
                    df_validado, tipo_campana
                )
                if not df_rech_tec.empty:
                    df_rechazados_total = pd.concat([df_rechazados_total, df_rech_tec])

            # --- FASE C: DUPLICADOS FINALES ---
            # Pasamos cliente_codigo para aplicar lógica especial de 0360CQTA si corresponde
            df_validado, df_rech_dup = validaciones_pipeline.validar_duplicados(
                df_validado, tipo_campana, cliente_codigo
            )
            if not df_rech_dup.empty:
                df_rechazados_total = pd.concat([df_rechazados_total, df_rech_dup])

        finally:
            # Cerramos la conexión a la BD operativa
            db_gen_datos.close()

        # --- PASO 6: CARGA FINAL EN 'masiv_dia' ---
        logger.info(f"[Task {task_id}] Paso 6: Cargando {len(df_validado)} registros válidos a 'masiv_dia'...")
        # (Aquí se elimina el '56' antes de insertar)
        db_bulk_operations.bulk_insert_final(df_validado, cliente_codigo, tipo_campana, task_id)

        # --- PASO 7: GUARDAR RECHAZADOS (CSV) ---
        logger.info(f"[Task {task_id}] Paso 7: Guardando reporte de rechazados...")
        output_dir = "campanas_generadas"
        if not os.path.exists(output_dir): os.makedirs(output_dir)
        
        archivos_generados = []
        if not df_rechazados_total.empty:
            nombre_rechazados = f"{prefijo_archivo}_RECHAZADOS.csv"
            ruta_rechazos = f"{output_dir}/{nombre_rechazados}"
            
            # Columnas clave + Columnas de Estrategia
            cols_base = ['motivo_rechazo', 'rut', 'idempresa', 'mail', 'telefono', 'fono1', 'fono2', 'mail1', 'mail2']
            cols_rech = [c.lower() for c in cols_base]
            
            for c in lista_cols_finales:
                if c.lower() not in cols_rech:
                    cols_rech.append(c.lower())
            
            # Filtrar columnas existentes en el DF
            cols_existentes = [c for c in cols_rech if c in df_rechazados_total.columns]
            if not cols_existentes: 
                cols_existentes = df_rechazados_total.columns.tolist()
            
            # Rellenar columnas críticas faltantes
            for c in ['rut', 'motivo_rechazo']:
                if c not in df_rechazados_total.columns:
                     df_rechazados_total[c] = ""
            
            df_rechazados_total[cols_existentes].to_csv(
                ruta_rechazos, index=False, sep=';', encoding='utf-8-sig'
            )
            archivos_generados.append(nombre_rechazados)

        # --- PASO 8: DIVISIÓN Y GUARDADO DE VÁLIDOS (CSV) ---
        logger.info(f"[Task {task_id}] Paso 8: Generando archivos finales de campaña...")
        
        config_proc = json.loads(plantilla_dict["reglas_procesamiento_json"] or "{}")
        cols_div = config_proc.get("columnas_division") or []
        if isinstance(cols_div, str): cols_div = [cols_div]
        cols_div = [c.lower() for c in cols_div]
        
        cols_validas_div = [c for c in cols_div if c in df_validado.columns]

        def guardar_grupo(df_g, sufijo_nombre):
            nombre_final = f"{prefijo_archivo}_{sufijo_nombre}.csv"
            ruta = f"{output_dir}/{nombre_final}"
            
            cols_exportar = df_g.columns.tolist()
            
            if lista_cols_finales:
                cols_norm = {c.lower(): c for c in df_g.columns}
                cols_exportar = []
                
                for c_req in lista_cols_finales:
                    # Si es MAIL, reemplazar mail1/mail2 por 'mail' consolidado
                    if "mail" in c_req and tipo_campana in ["MAIL", "MAIL_INF"]:
                         if "mail" in cols_norm and cols_norm["mail"] not in cols_exportar:
                             cols_exportar.append(cols_norm["mail"])
                         # Omitir mail1, mail2, etc.
                    elif c_req in cols_norm:
                        cols_exportar.append(cols_norm[c_req])
                
                if not cols_exportar: cols_exportar = df_g.columns.tolist()
            
            df_g[cols_exportar].to_csv(ruta, index=False, sep=';', encoding='utf-8-sig')
            return nombre_final

        if not cols_validas_div or df_validado.empty:
            if not df_validado.empty:
                archivos_generados.append(guardar_grupo(df_validado, "GLOBAL"))
        else:
            for nombre_grupo, df_grupo in df_validado.groupby(cols_validas_div):
                # Aplicar cálculos futuros
                df_grupo_procesado = validaciones_pipeline.aplicar_reglas_calculo(df_grupo, {})

                grupo_str = "_".join(map(str, nombre_grupo)) if isinstance(nombre_grupo, tuple) else str(nombre_grupo)
                safe_segmento = grupo_str.replace("/", "-").replace("\\", "-").replace(" ", "")
                
                if plantilla_dict["modo_salida"] == "api":
                    archivos_generados.append(f"API: {safe_segmento} (Simulado)")
                else:
                    archivos_generados.append(guardar_grupo(df_grupo_procesado, safe_segmento))

        # --- PASO 9: FINALIZAR ---
        logger.info(f"[Task {task_id}] Pipeline finalizado.")
        resumen = {
            "total_registros": total_inicial,
            "total_validos": len(df_validado),
            "total_rechazados": len(df_rechazados_total),
            "detalle_rechazo": df_rechazados_total['motivo_rechazo'].value_counts().to_dict() if not df_rechazados_total.empty else {}
        }
        tasks_db[task_id] = {"status": "complete", "data": {"archivos": archivos_generados, "resumen": resumen}}

    except Exception as e:
        logger.error(f"Error pipeline: {e}", exc_info=True)
        tasks_db[task_id] = {"status": "error", "error_message": str(e)}
    finally:
        if db_session_b2c: db_gen_b2c.close()