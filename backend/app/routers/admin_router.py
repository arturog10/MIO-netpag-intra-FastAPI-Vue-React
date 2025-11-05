# En un nuevo archivo, ej: app/admin_router.py
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.engine import Connection
from typing import Annotated
from pydantic import BaseModel

from app.database import get_db_session
import app.db_user_operations as db_users
from app.auth_security import get_current_admin_user # Importamos la nueva dependencia

from app.models import (UserCreate, RoleUpdate, StatusUpdate, PasswordReset)



log = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/admin",
    tags=["Administración"],
    # ¡Esta dependencia protege TODAS las rutas en este router!
    dependencies=[Depends(get_current_admin_user)] 
)

# --- Dependencia de BD (igual que en auth_router.py) ---
def get_user_db():
    yield from get_db_session("b2c")

DBSession = Annotated[Connection, Depends(get_user_db)]


# --- Endpoints de Admin ---

@router.get("/users", response_model=list[dict])
async def get_all_users(db: DBSession):
    """Obtiene todos los usuarios (protegido para admins)."""
    users = db_users.get_all_users_db(db)
    return users

@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_new_user(
    user_data: UserCreate, 
    db: DBSession,
    admin_email: str = Depends(get_current_admin_user)
):
    """Crea un nuevo usuario (protegido para admins)."""
    success = db_users.crear_usuario_db(
        db_session=db,
        username=user_data.email, # Asumimos que username es el email
        password_plano=user_data.password,
        email=user_data.email,
        nombre_completo=user_data.nombre_completo,
        rol=user_data.rol
    )
    
    if not success:
        raise HTTPException(status_code=400, detail="El email o nombre de usuario ya existe.")
    
    # Auditoría
    db_users.registrar_accion_db(db, admin_email, "crear_usuario", {"email_creado": user_data.email})
    return {"message": "Usuario creado exitosamente"}

# --- NOTA IMPORTANTE ---
# Las siguientes funciones (update_user_rol_db, update_user_status_db, reset_password_db)
# NO existen en tu 'db_user_operations.py' proporcionado.
# Deberás crearlas usando sentencias 'update' de SQLAlchemy,
# similares a 'crear_usuario_db'.

@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: int, 
    role_data: RoleUpdate, 
    db: DBSession,
    admin_email: str = Depends(get_current_admin_user)
):
    """Actualiza el rol de un usuario."""
    
    # --- IMPLEMENTACIÓN ---
    success = db_users.update_user_field_db(
        db_session=db, 
        user_id=user_id, 
        field_name="rol", 
        new_value=role_data.rol
    )
    if not success:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    # --- FIN IMPLEMENTACIÓN ---
    
    db_users.registrar_accion_db(db, admin_email, "update_rol", {"user_id": user_id, "nuevo_rol": role_data.rol})
    return {"message": "Rol actualizado"}

@router.put("/users/{user_id}/status")
async def update_user_status(
    user_id: int, 
    status_data: StatusUpdate, 
    db: DBSession,
    admin_email: str = Depends(get_current_admin_user)
):
    """Activa o desactiva un usuario."""
    
    # --- IMPLEMENTACIÓN ---
    # Convierte booleano (true/false) a entero (1/0) para la BD
    status_int = 1 if status_data.activo else 0 
    
    success = db_users.update_user_field_db(
        db_session=db, 
        user_id=user_id, 
        field_name="activo", 
        new_value=status_int
    )
    if not success:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    # --- FIN IMPLEMENTACIÓN ---

    db_users.registrar_accion_db(db, admin_email, "update_status", {"user_id": user_id, "nuevo_status": status_data.activo})
    return {"message": "Estado actualizado"}

@router.put("/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: int, 
    password_data: PasswordReset, 
    db: DBSession,
    admin_email: str = Depends(get_current_admin_user)
):
    """Resetea la contraseña de un usuario."""
    
    # --- IMPLEMENTACIÓN ---
    success = db_users.reset_password_db(
        db_session=db, 
        user_id=user_id, 
        new_password_plano=password_data.new_password
    )
    if not success:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    # --- FIN IMPLEMENTACIÓN ---

    db_users.registrar_accion_db(db, admin_email, "reset_password", {"user_id": user_id})
    return {"message": "Contraseña reseteada"}