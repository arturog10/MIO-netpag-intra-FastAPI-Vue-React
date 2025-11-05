import logging
from getpass import getpass
import sys

# Añade la carpeta 'app' al path para poder importar
sys.path.append('./app') 

# Importar las funciones que ya creamos
try:
    from app.db_user_operations import crear_usuario_db
    from app.database import get_db_session
    from app.config import config
    from app.logging_config import setup_logging
except ImportError as e:
    print(f"Error: No se pudieron importar los módulos. Asegúrate de que estás en la carpeta 'backend' y que 'app/__init__.py' existe. Error: {e}")
    sys.exit(1)

# Configurar logging para ver la salida
setup_logging()
logger = logging.getLogger(__name__)

def main():
    print("--- Creación de Usuario Administrador ---")
    
    # Recopilar datos del nuevo admin
    email = input("Email del administrador: ").strip()
    username = input("Nombre de usuario (nickname): ").strip()
    nombre_completo = input("Nombre completo: ").strip()
    password = getpass("Contraseña (no se mostrará): ")
    password_confirm = getpass("Confirma la contraseña: ")
    
    # ¡NO IMPRIMIR CONTRASEÑAS! Es un riesgo de seguridad
    
    if password != password_confirm:
        print("\n❌ Las contraseñas no coinciden. Abortando.")
        return

    if not all([email, username, nombre_completo, password]):
        print("\n❌ Todos los campos son obligatorios. Abortando.")
        return
    
    # Validar longitud de contraseña para bcrypt (máximo 72 bytes)
    if len(password.encode('utf-8')) > 72:
        print("\n❌ La contraseña es demasiado larga.")
        print("   bcrypt acepta máximo 72 bytes (aproximadamente 72 caracteres).")
        print(f"   Tu contraseña tiene {len(password.encode('utf-8'))} bytes.")
        return
        
    rol = "admin" # Asignar rol de admin

    # Obtener la clave de la BD donde está la tabla de usuarios
    try:
        db_key = config["json_config"]["tabla_usuarios"]["db_key"]
        logger.info(f"Usando la conexión de BD: '{db_key}'")
    except KeyError:
        logger.error("¡Error! No se encontró 'tabla_usuarios' en config.json.")
        print("\n❌ Error: Configuración de tabla_usuarios no encontrada en config.json")
        return

    # Usar el generador correctamente con un contexto
    db = None
    try:
        # Crear el generador
        db_gen = get_db_session(db_key)
        
        # Obtener la conexión (esto inicia la transacción)
        db = next(db_gen)
        
        print(f"\nConectado a la BD. Creando usuario '{username}'...")
        
        # Llamar a la función que crea el usuario
        success = crear_usuario_db(
            db_session=db,
            username=username,
            password_plano=password,
            email=email,
            nombre_completo=nombre_completo,
            rol=rol
        )
        
        if success:
            # Forzar el commit llamando a next() de nuevo
            try:
                next(db_gen)
            except StopIteration:
                pass  # Normal - el generador se agotó después del commit
            
            print("\n🎉 ¡Usuario administrador creado exitosamente!")
            print(f"   Email: {email}")
            print(f"   Username: {username}")
            print(f"   Rol: {rol}")
        else:
            print("\n❌ Error al crear el usuario. Revisa el log para más detalles.")
            print("   Posibles causas:")
            print("   - El email ya existe en la base de datos")
            print("   - El nombre de usuario ya existe")
            print("   - Error de conexión a la base de datos")
            
    except Exception as e:
        logger.error(f"Error en la conexión o creación: {e}", exc_info=True)
        print(f"\n❌ Ocurrió un error general: {e}")
        
        # Intentar hacer rollback cerrando el generador
        if db is not None:
            try:
                db_gen.close()
            except:
                pass

if __name__ == "__main__":
    main()