import logging
import pandas as pd
import numpy as np
import re

logger = logging.getLogger(__name__)

# ... (Función _generar_mensaje_dinamico IGUAL) ...
def _generar_mensaje_dinamico(df: pd.DataFrame, template: str) -> pd.DataFrame:
    if not template:
        df['mensaje'] = ""
        return df

    def formatear_valor(val):
        try:
            f = float(val)
            return "{:,.0f}".format(f).replace(",", ".")
        except: return str(val)

    def construir(row):
        msg = template
        def replacer(match):
            key = match.group(1).lower().strip()
            if key in row.index:
                val = row[key]
                if pd.notnull(val) and str(val).strip() != "":
                    return formatear_valor(val)
                return "" 
            return match.group(0)

        return re.sub(r'\{([^{}]+)\}', replacer, msg)[:160]

    df['mensaje'] = df.apply(construir, axis=1)
    return df

# --- LÓGICA ESPECÍFICA ---

def logica_punto_net(df: pd.DataFrame, **kwargs) -> pd.DataFrame:
    return df

def logica_fidelizador(df: pd.DataFrame, **kwargs) -> pd.DataFrame:
    if "id_fidelizador" not in df.columns:
        df["id_fidelizador"] = range(1, len(df) + 1)
    return df

def logica_masivian(df: pd.DataFrame, **kwargs) -> pd.DataFrame:
    mensaje_template = kwargs.get("mensaje_template", "")
    cliente_codigo = kwargs.get("cliente_codigo", "")
    
    df = _generar_mensaje_dinamico(df, mensaje_template)
    df['cliente'] = cliente_codigo
    if 'telefono' not in df.columns: df['telefono'] = ""
    
    try: return df[['cliente', 'rut', 'telefono', 'mensaje']].copy()
    except KeyError: return df

def logica_siptel(df: pd.DataFrame, **kwargs) -> pd.DataFrame:
    mensaje_template = kwargs.get("mensaje_template", "")
    cliente_codigo = kwargs.get("cliente_codigo", "")

    df = _generar_mensaje_dinamico(df, mensaje_template)
    df['cliente'] = cliente_codigo
    
    if 'telefono' in df.columns: df.rename(columns={'telefono': 'numero'}, inplace=True)
    else: df['numero'] = ""

    try: return df[['numero', 'mensaje', 'cliente', 'rut']].copy()
    except KeyError: return df

# --- NUEVO: Lógica NEOTEL (Discador) ---
def logica_neotel(df: pd.DataFrame, **kwargs) -> pd.DataFrame:
    """
    Lógica para Discador NEOTEL:
    - Solo genera un archivo con los RUTs.
    - Elimina cualquier otra columna.
    """
    logger.info("Aplicando lógica Neotel: Filtrando solo RUTs.")
    
    # Asegurar que existe la columna rut
    if 'rut' in df.columns:
        # Retornar solo el RUT
        return df[['rut']].copy()
    else:
        # Si por algún motivo no está (ej: se llama idempresa), intentar buscarla o fallar
        if 'idempresa' in df.columns:
             return df[['idempresa']].rename(columns={'idempresa': 'rut'})
        logger.error("No se encontró columna RUT para Neotel.")
        return df

# --- REGISTRO ---
PROVIDERS_MAP = {
    "PUNTO_NET": logica_punto_net,
    "FIDELIZADOR": logica_fidelizador,
    "MASIVIAN": logica_masivian,
    "SIPTEL": logica_siptel,
    "NEOTEL": logica_neotel # <--- Nuevo Proveedor
}

def aplicar_logica_proveedor(df: pd.DataFrame, proveedor_key: str, **kwargs) -> pd.DataFrame:
    if not proveedor_key: return df
    logic_func = PROVIDERS_MAP.get(proveedor_key)
    if logic_func:
        try:
            return logic_func(df, **kwargs)
        except Exception as e:
            logger.error(f"Error lógica proveedor {proveedor_key}: {e}", exc_info=True)
            return df
    return df