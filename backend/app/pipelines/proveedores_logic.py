import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# --- LÓGICA ESPECÍFICA POR PROVEEDOR ---

def logica_punto_net(df: pd.DataFrame, **kwargs) -> pd.DataFrame:
    """Lógica para PUNTO NET (Mail)"""
    # Ej: Asegurar encoding o columnas específicas
    return df

def logica_fidelizador(df: pd.DataFrame, **kwargs) -> pd.DataFrame:
    """Lógica para FIDELIZADOR (Mail)"""
    # Ej: Fidelizador suele pedir un ID secuencial único o un formato específico
    # Aquí podrías implementar la lógica de 'start_code' que vimos antes si es necesario
    if "id_fidelizador" not in df.columns:
        # Ejemplo: Crear un ID correlativo simple si no existe
        df["id_fidelizador"] = range(1, len(df) + 1)
    return df

def logica_masivian(df: pd.DataFrame, **kwargs) -> pd.DataFrame:
    """Lógica para MASIVIAN (SMS)"""
    # Ej: Masivian a veces pide el fono sin el 56 o con formato internacional específico
    return df

def logica_siptel(df: pd.DataFrame, **kwargs) -> pd.DataFrame:
    """Lógica para SIPTEL (SMS)"""
    return df

# --- REGISTRO DE PROVEEDORES ---
# Para agregar uno nuevo, solo defínelo arriba y agrégalo a este diccionario.
PROVIDERS_MAP = {
    "PUNTO_NET": logica_punto_net,
    "FIDELIZADOR": logica_fidelizador,
    "MASIVIAN": logica_masivian,
    "SIPTEL": logica_siptel
}

def aplicar_logica_proveedor(df: pd.DataFrame, proveedor_key: str, **kwargs) -> pd.DataFrame:
    """
    Función orquestadora que busca la función del proveedor y la ejecuta.
    """
    if not proveedor_key:
        return df
    
    logic_func = PROVIDERS_MAP.get(proveedor_key)
    
    if logic_func:
        try:
            logger.info(f"  [Proveedor] Aplicando lógica específica para: {proveedor_key}")
            return logic_func(df, **kwargs)
        except Exception as e:
            logger.error(f"Error aplicando lógica de proveedor {proveedor_key}: {e}")
            return df # Retornar original ante error para no romper flujo
    else:
        # Si el proveedor no tiene lógica especial, pasamos de largo
        return df