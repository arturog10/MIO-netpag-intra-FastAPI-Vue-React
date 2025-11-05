import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.engine import Connection # Para inyección de dependencia
from typing import Annotated

from app.database import get_db_session # Importamos nuestro gestor de sesión
from app.models import StrategySaveRequest # (Importa modelos Pydantic si creas más)
import app.db_user_operations as db_users # Importamos las operaciones de usuario
from app.auth_security import create_access_token, get_current_user_email

log = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/auth",
    tags=["Autenticación y Auditoría"]
)

# --- Dependencia de Conexión a la BD de Usuarios ---
# (Asume que la tabla 'tabla_usuarios' está en la conexión 'b2c')
def get_user_db():
    """Dependencia para obtener la sesión de BD 'b2c'"""
    yield from get_db_session("b2c")

DBSession = Annotated[Connection, Depends(get_user_db)]

# --- Dependencia de Auditoría ---
# (Se usa en otros endpoints para registrar acciones)
async def log_action(
    usuario: str = Depends(get_current_user_email), # Asegura que el usuario esté logueado
    db: Connection = Depends(get_user_db) # Obtiene la BD de auditoría
):
    """Dependencia para registrar una acción (placeholder)."""
    # Esta dependencia es solo un ejemplo.
    # La lógica real de auditoría debería llamarse *dentro* # de los endpoints que modifican datos (ej. save_strategy).
    try:
        # Ejemplo: db_users.registrar_accion_db(db, usuario, "accion_generica", {})
        pass # La auditoría la llamaremos manualmente
    except Exception as e:
        log.error(f"Error en dependencia de auditoría: {e}")
    # Esta dependencia no hace nada más que verificar el token.
    # El 'usuario' se pasa a la función del endpoint.
    return usuario


# --- Endpoints de Autenticación ---

@router.post("/token")
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DBSession
):
    """
    Endpoint de Login. Recibe 'username' (que es el email) y 'password'
    en un formulario. Devuelve un token JWT.
    """
    # 'form_data.username' es el email (así lo usa OAuth2)
    user_data = db_users.verificar_usuario_db(
        db, email=form_data.username, password_plano=form_data.password
    )
    
    if not user_data:
        # Registro de auditoría para login fallido
        try:
            db_users.registrar_accion_db(db, usuario=form_data.username, accion="login_fallido", detalles={"email": form_data.username})
        except Exception as e:
            log.error(f"Error al registrar login fallido: {e}")
            
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrecta",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Registro de auditoría para login exitoso
    try:
        db_users.registrar_accion_db(db, usuario=user_data['email'], accion="login_exitoso", detalles={})
    except Exception as e:
        log.error(f"Error al registrar login exitoso: {e}")
        
    # Crea el token JWT. Guardamos el email en el campo "sub" (subject)
    access_token = create_access_token(
        data={"sub": user_data['email'], "rol": user_data['rol']}
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/users/me")
async def read_users_me(
    current_user_email: Annotated[str, Depends(get_current_user_email)]
):
    """
    Ruta protegida de ejemplo. Devuelve el email del usuario
    que está en el token.
    """
    return {"email": current_user_email}

# (Aquí puedes añadir más endpoints, como /register, /admin/users, etc.
#  usando las funciones de db_user_operations.py)