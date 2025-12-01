import logging
import pandas as pd
import numpy as np
import re

logger = logging.getLogger(__name__)

# --- FUNCIÓN AUXILIAR PARA SMS (COMPARTIDA) ---
def _generar_mensaje_dinamico(df: pd.DataFrame, template: str) -> pd.DataFrame:
    """
    Genera la columna 'mensaje' reemplazando variables {columna} por valores.
    """
    if not template:
        df['mensaje'] = ""
        return df

    def formatear_valor(val):
        try:
            f = float(val)
            return "{:,.0f}".format(f).replace(",", ".")
        except:
            return str(val)

    def construir(row):
        msg = template
        # Buscar patrones {texto}
        # Usamos una función replacer para buscar la columna correcta
        def replacer(match):
            key_raw = match.group(1)
            key = key_raw.lower().strip()
            
            if key in row.index:
                val = row[key]
                if pd.notnull(val) and str(val).strip() != "":
                    return formatear_valor(val)
                return "" # Valor nulo -> vacío
            
            return match.group(0) # No se encontró columna -> dejar placeholder

        msg_procesado = re.sub(r'\{([^{}]+)\}', replacer, msg)
        return msg_procesado[:160] # Límite SMS

    df['mensaje'] = df.apply(construir, axis=1)
    return df


# --- LÓGICA ESPECÍFICA POR PROVEEDOR ---

def logica_punto_net(df: pd.DataFrame, **kwargs) -> pd.DataFrame:
    return df

def logica_fidelizador(df: pd.DataFrame, **kwargs) -> pd.DataFrame:
    if "id_fidelizador" not in df.columns:
        df["id_fidelizador"] = range(1, len(df) + 1)
    return df

def logica_masivian(df: pd.DataFrame, **kwargs) -> pd.DataFrame:
    """
    MASIVIAN: CLIENTE;RUT;TELEFONO;MENSAJE
    """
    mensaje_template = kwargs.get("mensaje_template", "")
    cliente_codigo = kwargs.get("cliente_codigo", "")

    # 1. Mensaje
    df = _generar_mensaje_dinamico(df, mensaje_template)

    # 2. Cliente
    df['cliente'] = cliente_codigo

    # 3. Telefono
    if 'telefono' not in df.columns: df['telefono'] = ""

    # 4. Ordenar
    try:
        return df[['cliente', 'rut', 'telefono', 'mensaje']].copy()
    except KeyError as e:
        logger.error(f"Faltan columnas para Masivian: {e}")
        return df

def logica_siptel(df: pd.DataFrame, **kwargs) -> pd.DataFrame:
    """
    SIPTEL: NUMERO;MENSAJE;CLIENTE;RUT
    (Nota: 'telefono' pasa a ser 'numero')
    """
    mensaje_template = kwargs.get("mensaje_template", "")
    cliente_codigo = kwargs.get("cliente_codigo", "")

    # 1. Mensaje (Reutilizamos lógica)
    df = _generar_mensaje_dinamico(df, mensaje_template)

    # 2. Cliente
    df['cliente'] = cliente_codigo

    # 3. Renombrar Telefono -> Numero
    if 'telefono' in df.columns:
        df.rename(columns={'telefono': 'numero'}, inplace=True)
    else:
        df['numero'] = ""

    # 4. Ordenar: numero;mensaje;cliente;rut
    try:
        return df[['numero', 'mensaje', 'cliente', 'rut']].copy()
    except KeyError as e:
        logger.error(f"Faltan columnas para Siptel: {e}")
        return df

# --- REGISTRO ---
PROVIDERS_MAP = {
    "PUNTO_NET": logica_punto_net,
    "FIDELIZADOR": logica_fidelizador,
    "MASIVIAN": logica_masivian,
    "SIPTEL": logica_siptel
}

def aplicar_logica_proveedor(df: pd.DataFrame, proveedor_key: str, **kwargs) -> pd.DataFrame:
    if not proveedor_key: return df
    
    logic_func = PROVIDERS_MAP.get(proveedor_key)
    
    if logic_func:
        try:
            logger.info(f"Aplicando lógica proveedor: {proveedor_key}")
            return logic_func(df, **kwargs)
        except Exception as e:
            logger.error(f"Error lógica proveedor {proveedor_key}: {e}", exc_info=True)
            return df
    return df