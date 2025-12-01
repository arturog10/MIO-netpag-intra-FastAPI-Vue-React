import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.engine import Connection
from typing import List, Annotated

from app import db_reportes_operations
from app.auth_security import get_current_user_email
from app.database import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/reportes",
    tags=["Reportes"],
    dependencies=[Depends(get_current_user_email)]
)

# Dependencia de DB (Usamos 'b2c' según tu configuración)
def get_db():
    yield from get_db_session("b2c")

DBSession = Annotated[Connection, Depends(get_db)]

@router.get("/funnel")
def get_funnel_data(
    db: DBSession,
    fecha_inicio: str = Query(..., example="20251103"),
    periodo: str = Query(..., example="202511")
):
    """Obtiene los datos para el dashboard de Funnel."""
    try:
        data = db_reportes_operations.obtener_datos_funnel_db(db, fecha_inicio, periodo)
        return data
    except Exception as e:
        logger.error(f"Error en endpoint funnel: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener datos del reporte.")
    

@router.get("/rechazos")
async def get_rechazos(fecha_desde: str, fecha_hasta: str, cliente: str = None, db: DBSession = None, user: str = Depends(get_current_user_email)):
    try:
        return db_reportes_operations.obtener_rechazos_historicos(db, fecha_desde, fecha_hasta, cliente)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/gestion")
async def get_gestion(fecha_desde: str, fecha_hasta: str, cliente: str = None, db: DBSession = None, user: str = Depends(get_current_user_email)):
    try:
        return db_reportes_operations.obtener_gestion_diaria(db, fecha_desde, fecha_hasta, cliente)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))    