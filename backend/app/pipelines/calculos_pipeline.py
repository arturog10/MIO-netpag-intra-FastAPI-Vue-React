import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

def procesar_calculos(df: pd.DataFrame, reglas_procesamiento: dict, cols_estrategia: list = None) -> tuple[pd.DataFrame, list]:
    """
    Aplica cálculos definidos por el usuario con lógica condicional.
    Retorna: (DataFrame Modificado, Lista de Nombres de Nuevas Columnas)
    """
    nuevas_columnas = []
    
    if df.empty or not reglas_procesamiento:
        return df, nuevas_columnas

    df_calc = df.copy()
    df_calc.columns = df_calc.columns.str.lower().str.strip()
    
    try:
        # --- 1. COLUMNAS ESTÁTICAS ---
        estaticas = reglas_procesamiento.get("columnas_estaticas", [])
        for regla in estaticas:
            col = regla.get("columna", "").lower().strip()
            valor = regla.get("valor", "")
            condicion = regla.get("condicion", "")

            if col:
                # Evaluar condición si existe
                aplicar = True
                if condicion:
                    try:
                        # Si ningún registro cumple la condición, no creamos la columna
                        if not df_calc.eval(condicion).any():
                            aplicar = False
                    except:
                        aplicar = False # Ante error de condición, no aplicar
                
                if aplicar:
                    df_calc[col] = valor
                    nuevas_columnas.append(col)

        # --- 2. FÓRMULAS MATEMÁTICAS ---
        formulas = reglas_procesamiento.get("formulas", [])
        for regla in formulas:
            target_col = regla.get("columna", "").lower().strip()
            formula = regla.get("formula", "").lower()
            condicion = regla.get("condicion", "") # <--- NUEVO CAMPO
            tipo_dato = regla.get("tipo", "int")
            fill_na = regla.get("rellenar_nulos", 0)

            if target_col and formula:
                try:
                    # 1. Pre-procesamiento numérico (solo para columnas usadas)
                    # Identificamos columnas usadas en la fórmula o condición
                    texto_a_analizar = formula + " " + condicion
                    for col_existente in df_calc.columns:
                        if col_existente in texto_a_analizar:
                            if df_calc[col_existente].dtype == 'object':
                                df_calc[col_existente] = pd.to_numeric(df_calc[col_existente], errors='coerce').fillna(fill_na)
                            else:
                                df_calc[col_existente] = df_calc[col_existente].fillna(fill_na)

                    # 2. Evaluar Condición (Si existe)
                    mask_aplicar = None
                    if condicion:
                        try:
                            mask_aplicar = df_calc.eval(condicion)
                            # Si NADIE en este grupo cumple la condición, SALTAMOS la regla
                            # Esto logra que la columna NO se cree en archivos donde no aplica
                            if not mask_aplicar.any():
                                logger.debug(f"  [Cálculo] Saltando {target_col} (condición '{condicion}' no se cumple).")
                                continue
                        except Exception as e:
                            logger.error(f"Error evaluando condición '{condicion}': {e}")
                            continue

                    # 3. Evaluar Fórmula
                    resultado = df_calc.eval(formula)

                    # 4. Asignar Resultados
                    if mask_aplicar is not None:
                        # Si hay condición, inicializamos con valor por defecto (0/vacío)
                        # y solo llenamos los que cumplen
                        df_calc[target_col] = fill_na 
                        df_calc.loc[mask_aplicar, target_col] = resultado[mask_aplicar]
                    else:
                        # Si no hay condición, aplica a todos
                        df_calc[target_col] = resultado

                    # 5. Casting de Tipo
                    if tipo_dato == "int":
                        df_calc[target_col] = df_calc[target_col].fillna(0).astype(int)
                    elif tipo_dato == "float":
                        df_calc[target_col] = df_calc[target_col].fillna(0.0).astype(float)
                    elif tipo_dato == "str":
                        df_calc[target_col] = df_calc[target_col].astype(str)
                    
                    nuevas_columnas.append(target_col)
                    logger.info(f"  [Cálculo] {target_col} creado.")

                except Exception as e:
                    logger.error(f"Error en fórmula '{formula}': {e}")
                    # No creamos la columna si falla

        return df_calc, nuevas_columnas

    except Exception as e:
        logger.error(f"Error general en procesar_calculos: {e}", exc_info=True)
        return df, []