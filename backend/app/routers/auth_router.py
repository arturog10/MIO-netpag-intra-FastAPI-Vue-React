import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.engine import Connection
from typing import Annotated

from app.database import get_db_session
from app.models import StrategySaveRequest
import app.db_user_operations as db_users
from app.auth_security import create_access_token, get_current_user_email

# --- IMPORTAR LOS DICCIONARIOS DE TAREAS DE LOS OTROS MÓDULOS ---
# Asegúrate de que estas rutas sean correctas según tu estructura
from app.pipelines.pipeline_campana import tasks_db as campanas_tasks
from app.routers.trazabilidad_router import tasks_db as trazabilidad_tasks

log = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/auth",
    tags=["Autenticación y Auditoría"]
)

# ... (Dependencias get_user_db y log_action se mantienen igual) ...
def get_user_db():
    yield from get_db_session("intranet")

DBSession = Annotated[Connection, Depends(get_user_db)]

# ... (Endpoint /token se mantiene igual) ...
@router.post("/token")
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DBSession
):
    # ... (mismo código de login que ya tenías) ...
    user_data = db_users.verificar_usuario_db(db, email=form_data.username, password_plano=form_data.password)
    if not user_data:
        # ... registro auditoria fallo ...
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    
    # ... registro auditoria exito ...
    
    access_token = create_access_token(data={"sub": user_data['email'], "rol": user_data['rol']})
    return {"access_token": access_token, "token_type": "bearer"}


# --- NUEVO ENDPOINT: LOGOUT Y LIMPIEZA ---
@router.post("/logout")
async def logout_user(
    current_user_email: str = Depends(get_current_user_email),
    db: Connection = Depends(get_user_db)
):
    """
    Cierra la sesión y CANCELA todos los procesos en ejecución del usuario.
    """
    log.info(f"Usuario {current_user_email} cerrando sesión. Iniciando limpieza de tareas...")
    
    count_cancelled = 0

    # 1. Cancelar Tareas de Campañas
    # Iteramos sobre una copia para evitar errores si el diccionario cambia
    for task_id, task_info in list(campanas_tasks.items()):
        # Verificamos si la tarea pertenece al usuario (necesitamos que el pipeline guarde el usuario)
        # O si no guardamos el usuario, asumimos limpieza total por seguridad (opcional)
        # Lo ideal es que pipeline guarde "user": email.
        # Si no lo tienes, agregaremos un "parche" abajo para que lo guarde.
        
        task_owner = task_info.get("user_email")
        if task_owner == current_user_email and task_info["status"] == "running":
            campanas_tasks[task_id]["status"] = "cancelled"
            count_cancelled += 1

    # 2. Cancelar Tareas de Trazabilidad
    for task_id, task_info in list(trazabilidad_tasks.items()):
        # Trazabilidad router normalmente no guarda el email en el dict principal,
        # pero podemos asumir que si tienes la sesión abierta, eres tú. 
        # O mejor, vamos a asegurarnos de guardar el email al crear la tarea.
        
        # Si logramos guardar el 'user' en el dict de tareas:
        task_owner = task_info.get("user") 
        if task_owner == current_user_email and task_info["status"] == "running":
            trazabilidad_tasks[task_id]["status"] = "cancelled"
            count_cancelled += 1

    # 3. Auditoría
    try:
        db_users.registrar_accion_db(
            db, 
            current_user_email, 
            "logout", 
            {"tareas_canceladas": count_cancelled}
        )
    except Exception:
        pass

    log.info(f"Sesión cerrada para {current_user_email}. Procesos cancelados: {count_cancelled}")
    return {"message": "Sesión cerrada y procesos limpiados."}