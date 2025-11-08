import logging
import json
from sqlalchemy import text, select, insert, update
from sqlalchemy.engine import Connection # Importamos Connection
from app.config import config
from app.db_operations import _get_reflected_table # Reutilizamos la función auxiliar
from app.auth_security import get_password_hash, verify_password # Importamos los helpers de auth
from typing import Optional


logger = logging.getLogger(__name__)

# --- Funciones de Base de Datos (Adaptadas) ---

def crear_usuario_db(db_session: Connection, username: str, password_plano: str, email: str, nombre_completo: str, rol: str) -> bool:
    """
    Crea un nuevo usuario en la base de datos hasheando la contraseña.
    Usa la conexión (db_session) inyectada.
    """
    try:
        # 1. Hashear la contraseña usando el helper
        hash_password_str = get_password_hash(password_plano)

        # 2. Obtener la tabla de usuarios
        tabla = _get_reflected_table("tabla_usuarios")

        # 3. Insertar en la base de datos
        stmt = insert(tabla).values(
            nombre_usuario=username,
            hash_password=hash_password_str,
            email=email,
            nombre_completo=nombre_completo,
            rol=rol,
            activo=1
        )
        
        db_session.execute(stmt)
        # El commit se maneja en el 'with' del endpoint
        logger.info(f"Usuario '{username}' creado exitosamente.")
        return True
            
    except Exception as e:
        logger.error(f"Error al crear el usuario '{username}'. Puede que ya exista. Error: {e}")
        return False

def verificar_usuario_db(db_session: Connection, email: str, password_plano: str) -> Optional[dict]:
    """
    Verifica las credenciales de un usuario (por email) contra la base de datos.
    Devuelve los datos del usuario si es exitoso, o None si falla.
    """
    try:
        tabla = _get_reflected_table("tabla_usuarios")

        # 1. Busca al usuario por su email
        stmt = select(tabla).where(
            tabla.c.email == email,
            tabla.c.activo == 1
        )
        result = db_session.execute(stmt).fetchone()
        
        if not result:
            logger.warning(f"Intento de login fallido: Email '{email}' no encontrado o inactivo.")
            return None

        user_data = dict(result._mapping)
        hash_guardado_str = user_data['hash_password']

        # 2. Compara la contraseña usando el helper
        if verify_password(password_plano, hash_guardado_str):
            logger.info(f"Login exitoso para el email: {email}")
            user_data.pop('hash_password') # ¡Nunca devolver el hash!
            return user_data
        else:
            logger.warning(f"Intento de login fallido: Contraseña incorrecta para '{email}'.")
            return None

    except Exception as e:
        logger.error(f"Error durante la verificación de usuario: {e}", exc_info=True)
        return None

def registrar_accion_db(db_session: Connection, usuario: Optional[str], accion: str, detalles: Optional[dict] = None):
    """
    Inserta un nuevo registro en la tabla de auditoría.
    """
    if not usuario:
        usuario = "sistema"

    try:
        tabla = _get_reflected_table("tabla_auditoria")
        detalles_str = json.dumps(detalles, ensure_ascii=False) if detalles else None # ensure_ascii para tildes
        
        stmt = insert(tabla).values(
            nombre_usuario=usuario,
            accion=accion,
            detalles_json=detalles_str
        )
        
        db_session.execute(stmt)
        # El commit se maneja en el endpoint

    except Exception as e:
        logger.error(f"FALLO AL REGISTRAR AUDITORÍA: {e}", exc_info=True)

def update_user_field_db(db_session: Connection, user_id: int, field_name: str, new_value: any) -> bool:
    """
    Actualiza un campo específico para un usuario en la base de datos.
    Función genérica para 'rol' y 'activo'.
    """
    try:
        tabla = _get_reflected_table("tabla_usuarios")

        stmt = update(tabla).where(
            tabla.c.id_usuario == user_id
        ).values(
            {field_name: new_value} # Usa un diccionario para establecer el campo dinámicamente
        )
        
        result = db_session.execute(stmt)
        
        if result.rowcount == 0:
            logger.warning(f"No se encontró el usuario {user_id} al intentar actualizar '{field_name}'.")
            return False
            
        logger.info(f"Campo '{field_name}' actualizado para el usuario {user_id}.")
        return True
            
    except Exception as e:
        logger.error(f"Error al actualizar el campo '{field_name}' para el usuario {user_id}: {e}", exc_info=True)
        return False
    
def reset_password_db(db_session: Connection, user_id: int, new_password_plano: str) -> bool:
    """
    Resetea la contraseña de un usuario hasheando la nueva contraseña.
    """
    try:
        # 1. Hashear la nueva contraseña
        hash_password_str = get_password_hash(new_password_plano)
        
        tabla = _get_reflected_table("tabla_usuarios")

        # 2. Actualizar en la base de datos
        stmt = update(tabla).where(
            tabla.c.id_usuario == user_id
        ).values(
            hash_password=hash_password_str
        )
        
        result = db_session.execute(stmt)
        
        if result.rowcount == 0:
            logger.warning(f"No se encontró el usuario {user_id} al intentar resetear la contraseña.")
            return False
        
        logger.info(f"Contraseña reseteada exitosamente para el usuario {user_id}.")
        return True

    except Exception as e:
        logger.error(f"Error al resetear la contraseña para el usuario {user_id}: {e}", exc_info=True)
        return False    
# Ejemplo de adaptación de get_all_users_db

def get_all_users_db(db_session: Connection) -> list[dict]:
    """Obtiene una lista de todos los usuarios (sin sus contraseñas)."""
    try:
        tabla = _get_reflected_table("tabla_usuarios")
        # Selecciona columnas específicas
        stmt = select(
            tabla.c.id_usuario,
            tabla.c.nombre_usuario,
            tabla.c.nombre_completo,
            tabla.c.email,
            tabla.c.rol,
            tabla.c.activo
        )
        result = db_session.execute(stmt).fetchall()
        return [dict(row._mapping) for row in result]
    except Exception as e:
        logger.error(f"Error al obtener la lista de usuarios: {e}", exc_info=True)
        return []