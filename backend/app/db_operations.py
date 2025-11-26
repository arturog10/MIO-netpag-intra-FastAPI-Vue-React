import logging
import json
from datetime import datetime
from typing import Optional, List, Tuple
import pandas as pd
import numpy as np

from sqlalchemy import (
    text, select, func, cast, String, column, Table,
    MetaData, insert, update, delete, Numeric, Date, and_,
    DateTime, Time
)
from sqlalchemy.engine import Connection
from app.config import config
from app.database import engines 

logger = logging.getLogger(__name__)

# --- FUNCIONES AUXILIARES DE CONFIGURACIÓN Y REFLEXIÓN ---

def _get_table_info(config_key: str, client_code: str = None) -> dict:
    """
    Recupera la info de conexión desde config.json.
    CORREGIDO: Ahora maneja cualquier mapa (Clientes, Listas Negras) si se pasa client_code.
    """
    json_conf = config.get("json_config", {})
    
    # Si nos pasan un código/key específico, buscamos dentro del mapa correspondiente
    if client_code:
        mapping = json_conf.get(config_key, {})
        info = mapping.get(client_code)
        
        if not info:
             # Fallback exclusivo para clientes dinámicos (b2c_oper)
             if config_key == "cliente_table_map":
                return {"db_key": "b2c_oper", "schema": "dbo", "table": client_code}
             
             # Si es otra cosa (ej: lista negra) y no existe, error
             raise ValueError(f"No se encontró configuración para {config_key} -> {client_code}")
        
        return info
    
    # Si no hay client_code, es una tabla simple (Estrategias, Usuarios, etc.)
    info = json_conf.get(config_key)
    if not info:
        raise ValueError(f"Configuración no encontrada para: {config_key}")
    
    return info

def _get_reflected_table(config_key: str, client_code: str = None) -> Table:
    """Obtiene el objeto Table reflejado (SQLAlchemy Core)."""
    info = _get_table_info(config_key, client_code)
    db_key = info["db_key"]
    schema = info.get("schema", "dbo")
    table_name = info["table"]
    
    engine_info = engines.get(db_key)
    if not engine_info:
        raise ValueError(f"Motor de base de datos no encontrado para la clave: {db_key}")
    
    engine = engine_info["engine"]
    metadata = MetaData()
    metadata.reflect(bind=engine, schema=schema, only=[table_name])
    
    return metadata.tables[f"{schema}.{table_name}"]


# --- FUNCIÓN: Convertir fecha a DATE de forma robusta ---
def _create_robust_date_conversion(col_name: str):
    return text(f"""
        CASE
            WHEN SQL_VARIANT_PROPERTY([{col_name}], 'BaseType') = 'date' THEN CAST([{col_name}] AS DATE)
            WHEN LEN(REPLACE(REPLACE([{col_name}], ';', ''), ' ', '')) = 8 AND ISDATE(LEFT(REPLACE(REPLACE([{col_name}], ';', ''), ' ', ''), 8)) = 1 THEN CONVERT(DATE, LEFT(REPLACE(REPLACE([{col_name}], ';', ''), ' ', ''), 8), 112)
            WHEN CHARINDEX('/', [{ col_name}]) > 0 AND ISDATE(LEFT(REPLACE([{col_name}], ';', ''), 10)) = 1 THEN CONVERT(DATE, LEFT(REPLACE([{col_name}], ';', ''), 10), 103)
            WHEN CHARINDEX('-', [{col_name}]) > 0 AND SUBSTRING([{col_name}], 3, 1) = '-' AND ISDATE(LEFT([{col_name}], 10)) = 1 THEN CONVERT(DATE, LEFT([{col_name}], 10), 105)
            WHEN CHARINDEX('-', [{col_name}]) > 0 AND SUBSTRING([{col_name}], 5, 1) = '-' AND ISDATE([{col_name}]) = 1 THEN CONVERT(DATE, [{col_name}], 120)
            WHEN ISDATE([{col_name}]) = 1 THEN CONVERT(DATE, [{col_name}])
            ELSE NULL
        END
    """)


# --- LÓGICA DE FILTROS ROBUSTA ---

def construir_where_dinamico(filtros: Optional[dict] = None, tabla: Optional[Table] = None) -> Tuple[list, dict]:
    sql_filters = []
    params = {}
    if not filtros:
        return sql_filters, params

    for col_name, filter_info in filtros.items():
        operador = filter_info.get("operador")
        if not operador:
            continue

        safe_col = column(col_name)
        safe_param_name = f"param_{col_name.lower().replace(' ', '_').replace('-', '_')}"

        # Operadores Nulos
        if operador == "es_nulo":
            sql_filters.append(safe_col.is_(None))
            continue
        elif operador == "no_es_nulo":
            sql_filters.append(safe_col.is_not(None))
            continue

        # Operador de Rango (Fechas o Números)
        elif operador == "esta_entre":
            es_fecha = "fecha" in col_name.lower()
            val_desde = filter_info.get("desde")
            val_hasta = filter_info.get("hasta")
            
            is_native_date = False
            if es_fecha and tabla is not None and col_name in tabla.c:
                col_type = tabla.c[col_name].type
                if isinstance(col_type, (Date, DateTime, Time)):
                    is_native_date = True

            if es_fecha:
                if is_native_date:
                    sql_expr = cast(safe_col, Date)
                else:
                    sql_expr = _create_robust_date_conversion(col_name)
            else:
                try:
                    sql_expr = cast(safe_col, Numeric(18, 2))
                except:
                    sql_expr = safe_col

            if val_desde:
                param_name = f"desde_{safe_param_name}"
                clean_val = str(val_desde).strip()[:10]
                if es_fecha:
                    for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d']:
                        try:
                            clean_val = datetime.strptime(clean_val, fmt).strftime('%Y-%m-%d')
                            break
                        except ValueError: pass
                
                if is_native_date or not es_fecha:
                    sql_filters.append(sql_expr >= text(f":{param_name}"))
                else:
                    sql_filters.append(text(f"({sql_expr.text}) >= :{param_name}"))
                params[param_name] = clean_val

            if val_hasta:
                param_name = f"hasta_{safe_param_name}"
                clean_val = str(val_hasta).strip()[:10]
                if es_fecha:
                    for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d']:
                        try:
                            clean_val = datetime.strptime(clean_val, fmt).strftime('%Y-%m-%d')
                            break
                        except ValueError: pass
                
                if is_native_date or not es_fecha:
                    sql_filters.append(sql_expr <= text(f":{param_name}"))
                else:
                    sql_filters.append(text(f"({sql_expr.text}) <= :{param_name}"))
                params[param_name] = clean_val
            
            continue

        # --- OTROS OPERADORES ---
        valor = filter_info.get("valor")
        if valor is None or valor == "": 
            continue

        col_casteada_texto = cast(safe_col, String(255))
        col_casteada_num = cast(safe_col, Numeric(18, 2))

        if operador == "contiene":
            sql_filters.append(func.lower(col_casteada_texto).like(text(f":{safe_param_name}")))
            params[safe_param_name] = f"%{str(valor).lower()}%"
        elif operador == "es_igual":
            sql_filters.append(col_casteada_texto == text(f":{safe_param_name}"))
            params[safe_param_name] = str(valor)
        elif operador == "distinto_de":
            sql_filters.append(col_casteada_texto != text(f":{safe_param_name}"))
            params[safe_param_name] = str(valor)
        elif operador == "mayor_que":
            sql_filters.append(col_casteada_num > text(f":{safe_param_name}"))
            params[safe_param_name] = valor
        elif operador == "menor_que":
            sql_filters.append(col_casteada_num < text(f":{safe_param_name}"))
            params[safe_param_name] = valor
        elif operador in ["in", "not_in"]:
            valores = [v.strip() for v in str(valor).split(',') if v.strip()]
            if valores:
                if operador == "in": 
                    sql_filters.append(col_casteada_texto.in_(valores))
                else: 
                    sql_filters.append(col_casteada_texto.notin_(valores))

    return sql_filters, params


# --- OPERACIONES DE DATOS (VISOR) ---

def contar_datos_cliente(db_session, client_code: str, filtros: Optional[dict] = None) -> int:
    try:
        tabla = _get_reflected_table("cliente_table_map", client_code)
        sql_filters, params = construir_where_dinamico(filtros, tabla)

        stmt = select(func.count()).select_from(tabla)
        if sql_filters:
            stmt = stmt.where(and_(*sql_filters))

        result = db_session.execute(stmt, params).scalar_one_or_none()
        return result or 0
    except Exception as e:
        logger.error(f"Error al CONTAR datos para '{client_code}': {e}")
        raise e

def obtener_datos_cliente(db_session, client_code: str, filtros: Optional[dict] = None, page: int = 1, items_per_page: int = 15, sort_field: Optional[str] = None, sort_order: Optional[int] = None):
    try:
        tabla = _get_reflected_table("cliente_table_map", client_code)
        sql_filters, params = construir_where_dinamico(filtros, tabla)

        stmt = select(tabla)
        if sql_filters:
            stmt = stmt.where(and_(*sql_filters))

        order_expression = None
        if sort_field and sort_order is not None and sort_field in tabla.c:
            sort_col = tabla.c[sort_field]
            if sort_order == -1: order_expression = sort_col.desc()
            else: order_expression = sort_col.asc()
        elif len(tabla.c) > 0:
             order_expression = tabla.c[0]

        if order_expression is not None:
             stmt = stmt.order_by(order_expression)

        offset_val = (page - 1) * items_per_page
        stmt = stmt.offset(offset_val).limit(items_per_page)

        result = db_session.execute(stmt, params)
        column_names = list(result.keys())
        rows_as_dicts = [dict(zip(column_names, row)) for row in result.fetchall()]

        return column_names, rows_as_dicts
    except Exception as e:
        logger.error(f"Error al OBTENER datos para '{client_code}': {e}")
        raise e

def obtener_todos_los_datos_filtrados(db_session: Connection, client_code: str, filtros: Optional[dict] = None):
    """Obtiene todos los datos (sin paginación) para exportación o pipelines."""
    try:
        tabla = _get_reflected_table("cliente_table_map", client_code)
        sql_filters, params = construir_where_dinamico(filtros, tabla)

        stmt = select(tabla)
        if sql_filters:
            stmt = stmt.where(and_(*sql_filters))
        
        if len(tabla.c) > 0: stmt = stmt.order_by(tabla.c[0])

        result = db_session.execute(stmt, params)
        column_names = list(result.keys())
        rows_as_dicts = [dict(zip(column_names, row)) for row in result.fetchall()]

        return column_names, rows_as_dicts
    except Exception as e:
        logger.error(f"Error al OBTENER TODOS los datos para '{client_code}': {e}")
        raise e


# --- OPERACIONES DE ESTRATEGIAS ---

def estrategia_existe_db(db_session, nombre: str, cliente: str) -> bool:
    try:
        tabla = _get_reflected_table("tabla_estrategias")
        stmt = select(func.count()).select_from(tabla).where(
            tabla.c.nombre_estrategia == nombre,
            tabla.c.codigo_cliente == cliente
        )
        result = db_session.execute(stmt).scalar_one_or_none()
        return (result or 0) > 0
    except Exception as e:
        logger.error(f"Error chequeando estrategia: {e}")
        raise e

def guardar_estrategia_db(
    db_session: Connection, 
    nombre_estrategia: str, 
    cliente: str, 
    columnas: str, 
    filtro_columnas: str, 
    filtros_aplicados: str, 
    orden_estado: str,
    usuario_creador: str,
    id_usuario_creador: int = None
):
    try:
        tabla = _get_reflected_table("tabla_estrategias")
        stmt = insert(tabla).values(
            nombre_estrategia=nombre_estrategia,
            codigo_cliente=cliente,
            columnas_visibles=columnas,
            filtro_columnas=filtro_columnas,
            filtros_aplicados=filtros_aplicados,
            orden_estado=orden_estado,
            usuario_creador=usuario_creador,
            fecha_creacion=datetime.now(),
            activa=1,
            es_publica=0,
            id_usuario_creador=id_usuario_creador
        )
        db_session.execute(stmt)
        db_session.commit()
        return True
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error guardando estrategia: {e}")
        raise e

def actualizar_estrategia_db(db_session, nombre, cliente, columnas, filtro_columnas, filtros_aplicados, orden_estado):
    try:
        tabla = _get_reflected_table("tabla_estrategias")
        stmt = update(tabla).where(
            and_(
                tabla.c.nombre_estrategia == nombre,
                tabla.c.codigo_cliente == cliente
            )
        ).values(
            columnas_visibles=columnas, filtro_columnas=filtro_columnas,
            filtros_aplicados=filtros_aplicados, orden_estado=orden_estado
        )
        result = db_session.execute(stmt)
        db_session.commit()
        return result.rowcount > 0
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error actualizando estrategia: {e}")
        raise e

def cargar_estrategias_db(db_session, client_code: str) -> list:
    """
    Devuelve la lista de estrategias para el cliente.
    """
    try:
        tabla = _get_reflected_table("tabla_estrategias")
        
        # Seleccionamos TODO para que el Visor pueda restaurar los filtros
        stmt = select(tabla).where(
            tabla.c.codigo_cliente == client_code,
            tabla.c.activa == 1
        ).order_by(tabla.c.nombre_estrategia)
        
        result = db_session.execute(stmt).fetchall()
        
        lista = []
        for row in result:
            d = dict(row._mapping)
            d['nombre'] = d['nombre_estrategia'] # Mapeo para el frontend
            lista.append(d)
            
        return lista
    except Exception as e:
        logger.error(f"Error cargando estrategias: {e}")
        return []

def cargar_una_estrategia_db(db_session, id_estrategia: int) -> Optional[dict]:
    try:
        tabla = _get_reflected_table("tabla_estrategias")
        stmt = select(
            tabla.c.codigo_cliente, tabla.c.nombre_estrategia,
            tabla.c.columnas_visibles, tabla.c.filtros_aplicados,
            tabla.c.orden_estado
        ).where(tabla.c.id == id_estrategia)
        result = db_session.execute(stmt).fetchone()
        if result:
            d = dict(result._mapping)
            d['nombre'] = d['nombre_estrategia']
            return d
        return None
    except Exception as e:
        logger.error(f"Error cargando estrategia {id_estrategia}: {e}")
        raise e

def eliminar_estrategia_db(db_session, id_estrategia: int):
    try:
        tabla = _get_reflected_table("tabla_estrategias")
        stmt = update(tabla).where(tabla.c.id == id_estrategia).values(activa=0)
        db_session.execute(stmt)
        db_session.commit()
        return True
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error eliminando estrategia {id_estrategia}: {e}")
        raise e


# --- LISTA NEGRA ---

def obtener_columnas_listanegra(db_session) -> list[str]:
    try:
        # Busca "Lista Principal" en el mapa
        tabla = _get_reflected_table("listanegra_table_map", "Lista Principal")
        return [c.name for c in tabla.columns]
    except Exception as e:
        logger.error(f"Error obteniendo columnas lista negra: {e}")
        raise e

def contar_datos_listanegra(db_session, listanegra_key: str = "Lista Principal", filtros: Optional[dict] = None) -> int:
    try:
        # Pasa listanegra_key como "client_code" para que _get_reflected_table lo busque en el mapa
        tabla = _get_reflected_table("listanegra_table_map", listanegra_key)
        sql_filters, params = construir_where_dinamico(filtros, tabla)
        stmt = select(func.count()).select_from(tabla)
        if sql_filters: stmt = stmt.where(and_(*sql_filters))
        result = db_session.execute(stmt, params).scalar_one_or_none()
        return result or 0
    except Exception as e:
        logger.error(f"Error contando lista negra: {e}")
        raise e

def obtener_datos_listanegra(db_session, listanegra_key: str = "Lista Principal", filtros: Optional[dict] = None, page: int = 1, items_per_page: int = 15, sort_field: Optional[str] = None, sort_order: Optional[int] = None):
    try:
        tabla = _get_reflected_table("listanegra_table_map", listanegra_key)
        sql_filters, params = construir_where_dinamico(filtros, tabla)

        stmt = select(tabla)
        if sql_filters: stmt = stmt.where(and_(*sql_filters))
        
        if sort_field and sort_order is not None and sort_field in tabla.c:
            sort_col = tabla.c[sort_field]
            stmt = stmt.order_by(sort_col.desc() if sort_order == -1 else sort_col.asc())
        elif len(tabla.c) > 0:
             stmt = stmt.order_by(tabla.c[0])

        offset_val = (page - 1) * items_per_page
        stmt = stmt.offset(offset_val).limit(items_per_page)
        result = db_session.execute(stmt, params)
        cols = list(result.keys())
        return cols, [dict(zip(cols, r)) for r in result.fetchall()]
    except Exception as e:
        logger.error(f"Error obteniendo lista negra: {e}")
        raise e

def obtener_todos_los_datos_listanegra(db_session, listanegra_key: str = "Lista Principal", filtros: Optional[dict] = None, sort_field: Optional[str]= None, sort_order: Optional[int] = None) -> tuple[list[str], list[dict]]:
    try:
        tabla = _get_reflected_table("listanegra_table_map", listanegra_key)
        sql_filters, params = construir_where_dinamico(filtros, tabla)
        stmt = select(tabla)
        if sql_filters: stmt = stmt.where(and_(*sql_filters))
        
        if sort_field and sort_order is not None and sort_field in tabla.c:
            sort_col = tabla.c[sort_field]
            stmt = stmt.order_by(sort_col.desc() if sort_order == -1 else sort_col.asc())
        elif len(tabla.c) > 0:
             stmt = stmt.order_by(tabla.c[0])

        result = db_session.execute(stmt, params)
        cols = list(result.keys())
        return cols, [dict(zip(cols, r)) for r in result.fetchall()]
    except Exception as e:
        logger.error(f"Error exportando lista negra: {e}")
        raise e

def obtener_lista_negra_completa(db_session: Connection, listanegra_key: str = "Lista Principal") -> pd.DataFrame:
    try:
        tabla = _get_reflected_table("listanegra_table_map", listanegra_key)
        # Se asume que las columnas en BD pueden ser RUT, FONO, EMAIL, CLIENTE (Case Sensitive en algunos drivers)
        # Para seguridad, usamos .c (acceso a columnas reflejadas)
        cols = [c for c in tabla.columns if c.name.upper() in ['RUT', 'FONO', 'EMAIL', 'CLIENTE']]
        if not cols: # Fallback si nombres son distintos
             stmt = select(tabla)
        else:
             stmt = select(*cols)

        result = db_session.execute(stmt).fetchall()
        # Convertir a DataFrame con nombres normalizados
        df = pd.DataFrame(result, columns=[c.name.lower() for c in cols] if cols else result[0].keys())
        
        # Normalización básica
        if 'rut' in df.columns: df['rut'] = df['rut'].astype(str).str.strip()
        if 'fono' in df.columns: df['fono'] = df['fono'].astype(str).str.strip().replace(r'\.0$', '', regex=True)
        if 'email' in df.columns: df['email'] = df['email'].astype(str).str.lower().str.strip()
        
        df.replace(['nan', 'None', 'NaT', '', '0'], np.nan, inplace=True)
        return df
    except Exception as e:
        logger.error(f"Error cargando lista negra completa: {e}")
        raise e