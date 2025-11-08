import logging
import json
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    text, select, func, cast, String, column, Table,
    MetaData, insert, update, delete, Numeric, Date, and_
)
from app.config import config

logger = logging.getLogger(__name__)

# --- FUNCIONES AUXILIARES CLAVE ---

def _get_table_info(table_key: str, client_code: str = None) -> dict:
    """
    Obtiene la información (engine, schema, table_name, db_key)
    de la tabla desde la configuración central.
    """
    if client_code:
        map_key = table_key
        json_map = config["json_config"].get(map_key, {})
        info = json_map.get(client_code)
    else:
        info = config["json_config"].get(table_key)

    if not info:
        logger.error(f"No se encontró config para: {table_key} / {client_code}")
        raise ValueError(f"Configuración de tabla no encontrada")

    db_key = info["db_key"]
    engine_info = config["engines"].get(db_key)
    if not engine_info:
        logger.error(f"No se encontró motor de DB para la clave: {db_key}")
        raise ValueError(f"Configuración de motor de DB no encontrada")

    return {
        "engine": engine_info["engine"],
        "schema": info["schema"],
        "table_name": info["table"],
        "db_key": db_key
    }

def _get_reflected_table(table_key: str, client_code: str = None) -> Table:
    """
    Obtiene un objeto 'Table' de SQLAlchemy reflejando la estructura.
    """
    info = _get_table_info(table_key, client_code)
    engine_para_reflejar = info["engine"]
    metadata = MetaData()

    tabla = Table(
        info["table_name"],
        metadata,
        schema=info["schema"],
        autoload_with=engine_para_reflejar
    )
    return tabla


# --- NUEVA FUNCIÓN: Convertir fecha a DATE de forma robusta ---
def _create_robust_date_conversion(col_name: str):
    """
    Crea una expresión SQL que convierte una columna a DATE
    probando múltiples formatos en cascada usando CASE WHEN.
    
    Compatible con SQL Server 2008+
    """
    safe_col = column(col_name)
    
    # Crear expresión SQL cruda (raw SQL) que SQL Server puede entender
    # Usamos CASE WHEN con ISDATE() para verificar formatos válidos
    sql_expression = text(f"""
        CASE
            -- Si ya es tipo DATE, usarlo directamente
            WHEN SQL_VARIANT_PROPERTY([{col_name}], 'BaseType') = 'date' 
                THEN CAST([{col_name}] AS DATE)
            
            -- Formato YYYYMMDD (8 dígitos)
            WHEN LEN(REPLACE(REPLACE([{col_name}], ';', ''), ' ', '')) = 8 
                AND ISDATE(LEFT(REPLACE(REPLACE([{col_name}], ';', ''), ' ', ''), 8)) = 1
                THEN CONVERT(DATE, LEFT(REPLACE(REPLACE([{col_name}], ';', ''), ' ', ''), 8), 112)
            
            -- Formato DD/MM/YYYY (103)
            WHEN CHARINDEX('/', [{ col_name}]) > 0 
                AND ISDATE(LEFT(REPLACE([{col_name}], ';', ''), 10)) = 1
                THEN CONVERT(DATE, LEFT(REPLACE([{col_name}], ';', ''), 10), 103)
            
            -- Formato DD-MM-YYYY (105)
            WHEN CHARINDEX('-', [{col_name}]) > 0 
                AND SUBSTRING([{col_name}], 3, 1) = '-'
                AND ISDATE(LEFT([{col_name}], 10)) = 1
                THEN CONVERT(DATE, LEFT([{col_name}], 10), 105)
            
            -- Formato ISO YYYY-MM-DD (120 o 126)
            WHEN CHARINDEX('-', [{col_name}]) > 0 
                AND SUBSTRING([{col_name}], 5, 1) = '-'
                AND ISDATE([{col_name}]) = 1
                THEN CONVERT(DATE, [{col_name}], 120)
            
            -- Intento genérico con CONVERT
            WHEN ISDATE([{col_name}]) = 1
                THEN CONVERT(DATE, [{col_name}])
            
            ELSE NULL
        END
    """)
    
    return sql_expression


# --- LÓGICA DE FILTROS (MEJORADA) ---

def construir_where_dinamico(filtros: Optional[dict] = None, tabla: Optional[Table] = None) -> tuple[list, dict]:
    """
    Construye la cláusula WHERE usando objetos de SQLAlchemy (¡PORTABLE!)
    y prepara los parámetros.
    """
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

        if operador == "es_nulo":
            sql_filters.append(safe_col.is_(None))
            continue
        elif operador == "no_es_nulo":
            sql_filters.append(safe_col.is_not(None))
            continue
        elif operador == "esta_entre":
            es_fecha = "fecha" in col_name.lower()
            is_numeric = False
            val_desde = filter_info.get("desde")
            val_hasta = filter_info.get("hasta")

            if not es_fecha:
                # Detectar si es numérico
                try:
                    if val_desde: float(val_desde)
                    elif val_hasta: float(val_hasta)
                    is_numeric = True
                except (ValueError, TypeError): 
                    is_numeric = False

            # --- MANEJO DE FECHAS ROBUSTO ---
            if es_fecha:
                # Usar la expresión SQL cruda directamente
                sql_expr = _create_robust_date_conversion(col_name)
            elif is_numeric:
                sql_expr = cast(safe_col, Numeric(18, 2))
            else:
                sql_expr = cast(safe_col, String(255))

            # Procesar los valores desde/hasta
            try:
                if val_desde:
                    param_name = f"desde_{safe_param_name}"
                    clean_val_desde = str(val_desde).strip()[:10]
                    
                    if es_fecha:
                        # Intentar ambos formatos: DD/MM/YYYY y DD-MM-YYYY
                        valor_param = None
                        for date_format in ['%d/%m/%Y', '%d-%m-%Y']:
                            try:
                                valor_param = datetime.strptime(clean_val_desde, date_format).strftime('%Y-%m-%d')
                                break
                            except ValueError:
                                continue
                        
                        if valor_param is None:
                            logger.warning(f"No se pudo parsear la fecha 'desde' para {col_name}: {clean_val_desde}")
                            continue
                        
                        sql_filters.append(text(f"({sql_expr.text}) >= :{param_name}"))
                        params[param_name] = valor_param

                    else:
                        valor_param = val_desde
                    
                    # Para fechas, usar la comparación directamente con el SQL raw
                        sql_filters.append(sql_expr >= text(f":{param_name}"))
                        params[param_name] = valor_param
                    # NO agregar a params porque ya está en el SQL

                if val_hasta:
                    param_name = f"hasta_{safe_param_name}"
                    clean_val_hasta = str(val_hasta).strip()[:10]
                    
                    if es_fecha:
                        # Intentar ambos formatos: DD/MM/YYYY y DD-MM-YYYY
                        valor_param = None
                        for date_format in ['%d/%m/%Y', '%d-%m-%Y']:
                            try:
                                valor_param = datetime.strptime(clean_val_hasta, date_format).strftime('%Y-%m-%d')
                                break
                            except ValueError:
                                continue
                        
                        if valor_param is None:
                            logger.warning(f"No se pudo parsear la fecha 'hasta' para {col_name}: {clean_val_hasta}")
                            continue
                        sql_filters.append(text(f"({sql_expr.text}) <= :{param_name}"))
                        params[param_name] = valor_param
                    else:
                        valor_param = val_hasta
                    
                    # Para fechas, usar la comparación directamente con el SQL raw
                        sql_filters.append(sql_expr <= text(f":{param_name}"))
                        params[param_name] = valor_param
                    
                    # NO agregar a params porque ya está en el SQL
                    
            except (ValueError, TypeError) as e:
                if es_fecha: 
                    logger.warning(f"Formato de fecha inválido para {col_name}: {e}. Se ignora este filtro.")
                pass
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


# --- OPERACIONES DE DATOS ---

def contar_datos_cliente(db_session, client_code: str, filtros: Optional[dict] = None) -> int:
    try:
        tabla = _get_reflected_table("cliente_table_map", client_code)
        sql_filters, params = construir_where_dinamico(filtros)

        stmt = select(func.count()).select_from(tabla)
        if sql_filters:
            stmt = stmt.where(and_(*sql_filters))

        result = db_session.execute(stmt, params).scalar_one_or_none()
        return result or 0

    except Exception as e:
        logger.error(f"Error al CONTAR datos para '{client_code}': {e}", exc_info=True)
        raise e

def obtener_datos_cliente(db_session, client_code: str, filtros: Optional[dict] = None, page: int = 1, items_per_page: int = 15, sort_field: Optional[str] = None, sort_order: Optional[int] = None):
    try:
        tabla = _get_reflected_table("cliente_table_map", client_code)
        sql_filters, params = construir_where_dinamico(filtros)

        stmt = select(tabla)
        if sql_filters:
            stmt = stmt.where(and_(*sql_filters))

        # --- LÓGICA DE ORDENAMIENTO ---
        order_expression = None
        if sort_field and sort_order is not None and sort_field in tabla.c:
            logger.info(f"Aplicando orden: {sort_field} {sort_order}")
            sort_col = tabla.c[sort_field]
            if sort_order == -1:
                order_expression = sort_col.desc()
            else:
                order_expression = sort_col.asc()
        else:
            logger.info("Aplicando orden por defecto (columna 1)")
            if len(tabla.c) > 0:
                 order_expression = tabla.c[0]
            else:
                 logger.warning(f"La tabla '{tabla.name}' no tiene columnas.")

        if order_expression is not None:
             stmt = stmt.order_by(order_expression)

        # Paginación
        offset_val = (page - 1) * items_per_page
        stmt = stmt.offset(offset_val).limit(items_per_page)

        logger.info(f"Ejecutando consulta (paginada) con params: {params}")
        result = db_session.execute(stmt, params)
        column_names = list(result.keys())
        rows_as_dicts = [dict(zip(column_names, row)) for row in result.fetchall()]

        return column_names, rows_as_dicts

    except Exception as e:
        logger.error(f"Error al OBTENER datos para '{client_code}': {e}", exc_info=True)
        raise e

def obtener_todos_los_datos_filtrados(db_session, client_code: str, filtros: Optional[dict] = None):
    try:
        tabla = _get_reflected_table("cliente_table_map", client_code)
        sql_filters, params = construir_where_dinamico(filtros)

        stmt = select(tabla)
        if sql_filters:
            stmt = stmt.where(and_(*sql_filters))

        if len(tabla.c) > 0:
             stmt = stmt.order_by(tabla.c[0])

        logger.info(f"Ejecutando consulta (TODOS) con params: {params}")
        result = db_session.execute(stmt, params)
        column_names = list(result.keys())
        rows_as_dicts = [dict(zip(column_names, row)) for row in result.fetchall()]

        return column_names, rows_as_dicts

    except Exception as e:
        logger.error(f"Error al OBTENER TODOS los datos para '{client_code}': {e}", exc_info=True)
        raise e


# --- OPERACIONES DE ESTRATEGIAS ---
# (Sin cambios - las funciones siguen igual)

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
        logger.error(f"Error al CHEQUEAR estrategia '{nombre}': {e}", exc_info=True)
        raise e

def guardar_estrategia_db(db_session, nombre: str, cliente: str, columnas: str, filtro_columnas: str, filtros_aplicados: str, orden_estado: Optional[str] = None) -> bool:
    try:
        tabla = _get_reflected_table("tabla_estrategias")
        stmt = insert(tabla).values(
            nombre_estrategia=nombre, codigo_cliente=cliente,
            columnas_visibles=columnas, filtro_columnas=filtro_columnas,
            filtros_aplicados=filtros_aplicados,
            orden_estado = orden_estado
        )
        db_session.execute(stmt)
        logger.info(f"Estrategia '{nombre}' guardada con éxito.")
        return True
    except Exception as e:
        logger.error(f"Error al GUARDAR la estrategia '{nombre}': {e}", exc_info=True)
        raise e

def actualizar_estrategia_db(db_session, nombre: str, cliente: str, columnas: str, filtro_columnas: str, filtros_aplicados: str, orden_estado: Optional[str] = None) -> bool:
    try:
        tabla = _get_reflected_table("tabla_estrategias")
        stmt = update(tabla).where(
            tabla.c.nombre_estrategia == nombre,
            tabla.c.codigo_cliente == cliente
        ).values(
            columnas_visibles=columnas, filtro_columnas=filtro_columnas,
            filtros_aplicados=filtros_aplicados,
            orden_estado=orden_estado
        )
        result = db_session.execute(stmt)
        if result.rowcount == 0:
            logger.warning(f"Se intentó actualizar la estrategia '{nombre}', pero no se encontró.")
            return False
        logger.info(f"Estrategia '{nombre}' actualizada con éxito.")
        return True
    except Exception as e:
        logger.error(f"Error al ACTUALIZAR la estrategia '{nombre}': {e}", exc_info=True)
        raise e

def cargar_estrategias_db(db_session, client_code: str) -> list:
    try:
        tabla = _get_reflected_table("tabla_estrategias")
        stmt = select(tabla.c.id, tabla.c.nombre_estrategia).where(
            tabla.c.codigo_cliente == client_code,
            tabla.c.activa == 1
        ).order_by(tabla.c.nombre_estrategia)
        result = db_session.execute(stmt).fetchall()
        logger.info(f"Se encontraron {len(result)} estrategias activas para '{client_code}'.")
        return result
    except Exception as e:
        logger.error(f"Error al CARGAR LISTA de estrategias para '{client_code}': {e}", exc_info=True)
        raise e

def cargar_una_estrategia_db(db_session, id_estrategia: int) -> dict | None:
    try:
        tabla = _get_reflected_table("tabla_estrategias")
        stmt = select(
            tabla.c.columnas_visibles,
            tabla.c.filtros_aplicados,
            tabla.c.orden_estado
        ).where(tabla.c.id == id_estrategia)
        result = db_session.execute(stmt).fetchone()
        if result:
            logger.info(f"Cargando datos de la estrategia ID: {id_estrategia}")
            return dict(result._mapping)
        logger.warning(f"No se encontró la estrategia con ID: {id_estrategia}")
        return None
    except Exception as e:
        logger.error(f"Error al CARGAR UNA estrategia (ID {id_estrategia}): {e}", exc_info=True)
        raise e


# --- LISTA NEGRA ---

def obtener_columnas_listanegra(db_session) -> list[str]:
    """
    Obtiene solo los nombres de las columnas de lista negra.
    Útil para poblar los filtros en el frontend.
    """
    try:
        tabla = _get_reflected_table("lista_negra")
        return [c.name for c in tabla.columns]
    except Exception as e:
        logger.error(f"No se pudo obtener la estructura de lista_negra. Error: {e}")
        raise e

def contar_datos_listanegra(db_session, filtros: dict | None = None) -> int:
    try:
        tabla = _get_reflected_table("lista_negra")
        sql_filters, params = construir_where_dinamico(filtros)
        stmt = select(func.count()).select_from(tabla)
        if sql_filters: stmt = stmt.where(and_(*sql_filters))
        result = db_session.execute(stmt, params).scalar_one_or_none()
        return result or 0
    except Exception as e:
        logger.error(f"Error al CONTAR datos de lista_negra: {e}", exc_info=True)
        raise e

def obtener_datos_listanegra(db_session, filtros: Optional[dict] = None, page: int = 1, items_per_page: int = 15, sort_field: Optional[str] = None, sort_order: Optional[int] = None):
    """
    Obtiene los datos paginados y ordenados de Lista Negra.
    (Versión mejorada)
    """
    try:
        tabla = _get_reflected_table("lista_negra")
        sql_filters, params = construir_where_dinamico(filtros)

        stmt = select(tabla)
        if sql_filters:
            stmt = stmt.where(and_(*sql_filters))

        # --- LÓGICA DE ORDENAMIENTO (Igual que en el Visor) ---
        order_expression = None
        if sort_field and sort_order is not None and sort_field in tabla.c:
            logger.info(f"Aplicando orden: {sort_field} {sort_order}")
            sort_col = tabla.c[sort_field]
            if sort_order == -1: # Asumimos -1 para DESC
                order_expression = sort_col.desc()
            else: # Asumimos 1 o cualquier otro valor para ASC
                order_expression = sort_col.asc()
        else:
            if len(tabla.c) > 0:
                 order_expression = tabla.c[0] # Orden por defecto

        if order_expression is not None:
             stmt = stmt.order_by(order_expression)

        # Paginación
        offset_val = (page - 1) * items_per_page
        stmt = stmt.offset(offset_val).limit(items_per_page)

        logger.info(f"Ejecutando consulta (paginada) en Lista Negra con params: {params}")
        result = db_session.execute(stmt, params)
        column_names = list(result.keys())
        rows_as_dicts = [dict(zip(column_names, row)) for row in result.fetchall()]

        # Devuelve las columnas y las filas, igual que obtener_datos_cliente
        return column_names, rows_as_dicts

    except Exception as e:
        logger.error(f"Error al OBTENER datos de lista_negra: {e}", exc_info=True)
        raise e

def obtener_todos_los_datos_listanegra(db_session, filtros: Optional[dict] = None, sort_field: Optional[str]= None, sort_order: Optional[int] = None) -> tuple[list[str], list[dict]]:
    """
    Obtiene TODOS los datos filtrados de Lista Negra para exportar.
    (Versión mejorada)
    """
    try:
        tabla = _get_reflected_table("lista_negra")
        sql_filters, params = construir_where_dinamico(filtros)

        stmt = select(tabla)
        if sql_filters:
            stmt = stmt.where(and_(*sql_filters))

        # --- LÓGICA DE ORDENAMIENTO (Igual que en el Visor) ---
        order_expression = None
        if sort_field and sort_order is not None and sort_field in tabla.c:
            sort_col = tabla.c[sort_field]
            if sort_order == -1:
                order_expression = sort_col.desc()
            else:
                order_expression = sort_col.asc()
        else:
            if len(tabla.c) > 0:
                 order_expression = tabla.c[0]

        if order_expression is not None:
             stmt = stmt.order_by(order_expression)
        
        logger.info(f"Ejecutando consulta de exportación en Lista Negra: {params}")
        result = db_session.execute(stmt, params)
        column_names = list(result.keys())
        rows_as_dicts = [dict(row._mapping) for row in result.fetchall()]
        
        return column_names, rows_as_dicts
        
    except Exception as e:
        logger.error(f"Error al EXPORTAR datos de lista_negra: {e}", exc_info=True)
        raise e