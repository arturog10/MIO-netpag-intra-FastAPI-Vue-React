import logging
from datetime import datetime
from sqlalchemy import select, insert, update, desc, or_
from app.db_operations import _get_reflected_table

logger = logging.getLogger(__name__)

def listar_plantillas_db(db_session, es_admin=False):
    """
    Lista las plantillas.
    - Usuarios normales: Solo ven activas (estado = 1 o NULL).
    - Admins: Ven todas (incluyendo estado = 0).
    """
    try:
        tabla = _get_reflected_table("tabla_plantillas_campanas")
        
        stmt = select(
            tabla.c.id, 
            tabla.c.nombre_plantilla, 
            tabla.c.usuario_creador, 
            tabla.c.fecha_creacion,
            tabla.c.usuario_modificacion, # Nuevo
            tabla.c.fecha_modificacion,   # Nuevo
            tabla.c.estado                # Nuevo
        ).order_by(desc(tabla.c.fecha_creacion))
        
        # Filtro: Si no es admin, ocultar las eliminadas (estado 0)
        if not es_admin:
            # Mostramos las que son 1 ó NULL (para compatibilidad con datos viejos)
            stmt = stmt.where(or_(tabla.c.estado == 1, tabla.c.estado.is_(None)))

        result = db_session.execute(stmt).fetchall()
        
        lista_final = []
        for row in result:
            row_dict = dict(row._mapping)
            
            # Formato Fechas
            if row_dict.get('fecha_creacion'):
                row_dict['fecha_creacion'] = row_dict['fecha_creacion'].strftime('%d/%m/%Y %H:%M')
            
            if row_dict.get('fecha_modificacion'):
                row_dict['fecha_modificacion'] = row_dict['fecha_modificacion'].strftime('%d/%m/%Y %H:%M')
            else:
                row_dict['fecha_modificacion'] = "-"
            
            # Normalizar estado (si es None, asumir 1)
            if row_dict.get('estado') is None:
                row_dict['estado'] = 1
                
            lista_final.append(row_dict)
            
        return lista_final

    except Exception as e:
        logger.error(f"Error listando plantillas: {e}")
        raise e

def cargar_plantilla_db(db_session, id_plantilla):
    """Carga una plantilla por ID."""
    try:
        tabla = _get_reflected_table("tabla_plantillas_campanas")
        stmt = select(tabla).where(tabla.c.id == id_plantilla)
        row = db_session.execute(stmt).fetchone()
        
        if row:
            return dict(row._mapping)
        return None
    except Exception as e:
        logger.error(f"Error cargando plantilla {id_plantilla}: {e}")
        raise e

def guardar_plantilla_db(db_session, nombre, id_estrategia, reglas_val, reglas_proc, modo, id_usuario_creador, usuario_creador):
    """Guarda nueva plantilla (Activa por defecto)."""
    try:
        tabla = _get_reflected_table("tabla_plantillas_campanas")
        
        stmt = insert(tabla).values(
            nombre_plantilla=nombre,
            id_estrategia_base=id_estrategia,
            reglas_validacion_json=reglas_val,
            reglas_procesamiento_json=reglas_proc,
            modo_salida=modo,
            id_usuario_creador=id_usuario_creador,
            usuario_creador=usuario_creador,
            fecha_creacion=datetime.now(),
            estado=1, # <--- Activo
            # Inicializamos campos de modificación vacíos o iguales a creación
            fecha_modificacion=None 
        )
        
        result = db_session.execute(stmt)
        return result.inserted_primary_key[0]

    except Exception as e:
        logger.error(f"Error guardando plantilla: {e}")
        raise e

def actualizar_plantilla_db(db_session, id_plantilla, nombre, id_estrategia, reglas_val, reglas_proc, modo, id_usuario_mod, usuario_mod):
    """Actualiza datos y registra quién lo hizo (Auditoría)."""
    try:
        tabla = _get_reflected_table("tabla_plantillas_campanas")
        
        stmt = update(tabla).where(tabla.c.id == id_plantilla).values(
            nombre_plantilla=nombre,
            id_estrategia_base=id_estrategia,
            reglas_validacion_json=reglas_val,
            reglas_procesamiento_json=reglas_proc,
            modo_salida=modo,
            # --- Auditoría de Modificación ---
            id_usuario_modificacion=id_usuario_mod,
            usuario_modificacion=usuario_mod,
            fecha_modificacion=datetime.now()
        )
        
        db_session.execute(stmt)
        
    except Exception as e:
        logger.error(f"Error actualizando plantilla {id_plantilla}: {e}")
        raise e

def eliminar_plantilla_db(db_session, id_plantilla, id_usuario_mod, usuario_mod):
    """
    Borrado Lógico: Cambia estado a 0 y registra quién lo borró.
    """
    try:
        tabla = _get_reflected_table("tabla_plantillas_campanas")
        
        stmt = update(tabla).where(tabla.c.id == id_plantilla).values(
            estado=0, # <--- Inactivo
            id_usuario_modificacion=id_usuario_mod,
            usuario_modificacion=usuario_mod,
            fecha_modificacion=datetime.now()
        )
        
        result = db_session.execute(stmt)
        if result.rowcount == 0:
            # Puede pasar si el ID no existe
            logger.warning(f"Intentando eliminar plantilla inexistente ID {id_plantilla}")
            
    except Exception as e:
        logger.error(f"Error eliminando (lógico) plantilla {id_plantilla}: {e}")
        raise e

def cambiar_estado_plantilla_db(db_session, id_plantilla, nuevo_estado, id_user_mod, user_mod):
    """
    Para el Switch: Cambia solo el estado (1 o 0) y audita.
    """
    try:
        tabla = _get_reflected_table("tabla_plantillas_campanas")
        
        stmt = update(tabla).where(tabla.c.id == id_plantilla).values(
            estado=nuevo_estado,
            id_usuario_modificacion=id_user_mod,
            usuario_modificacion=user_mod,
            fecha_modificacion=datetime.now()
        )
        
        db_session.execute(stmt)
    except Exception as e:
        logger.error(f"Error cambiando estado plantilla {id_plantilla}: {e}")
        raise e