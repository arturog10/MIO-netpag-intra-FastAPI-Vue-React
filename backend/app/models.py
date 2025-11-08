import logging
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

# --- Modelos para Datos ---

class DataRequest(BaseModel):
    """Lo que el frontend envía al pedir datos"""
    filtros: Dict[str, Dict[str, Any]] = {}
    page: int = 1
    items_per_page: int = 15
    sort_field: Optional[str] = None
    sort_order: Optional[int] = None

class DataResponse(BaseModel):
    """Lo que el backend devuelve al entregar datos"""
    total_rows: int
    all_columns: List[str]
    rows: List[Dict[str, Any]]

# --- Modelos para Estrategias ---

class StrategySaveRequest(BaseModel):
    """Lo que el frontend envía para GUARDAR o ACTUALIZAR una estrategia"""
    nombre_estrategia: str
    columnas_visibles: str  # JSON-string
    filtro_columnas: Optional[str] = "" # El search term del visor_state
    filtros_aplicados: str # JSON-string
    orden_estado: Optional[str] = None

class StrategyLoadResponse(BaseModel):
    """Lo que el backend devuelve al CARGAR una estrategia"""
    columnas_visibles: str
    filtros_aplicados: str
    orden_estado: Optional[str] = None

# --- Modelos para Exportación ---

class ExportRequest(BaseModel):
    """Lo que el frontend envía para solicitar una exportación"""
    filtros: Dict[str, Dict[str, Any]] = {}
    visible_columns: List[str]
    formato: str # "excel" o "csv"

class TokenData(BaseModel):
    email: Optional[str] = None
    rol: Optional[str] = None    

class UserCreate(BaseModel):
    nombre_completo: str
    email: str
    password: str # El password plano
    rol: str

class RoleUpdate(BaseModel):
    rol: str

class StatusUpdate(BaseModel):
    activo: bool

class PasswordReset(BaseModel):
    new_password: str    

class ListaNegraDataRequest(BaseModel):
    """
    Solicitud de datos para la grilla de Lista Negra.
    """
    filtros: Optional[Dict[str, Any]] = None
    page: int = 1
    items_per_page: int = 15
    sort_field: Optional[str] = None
    sort_order: Optional[int] = None # 1 para ASC, -1 para DESC

class ListaNegraDataResponse(BaseModel):
    """
    Respuesta de datos para la grilla de Lista Negra.
    """
    total_rows: int
    all_columns: List[str]
    rows: List[Dict[str, Any]]

class ListaNegraExportRequest(BaseModel):
    """
    Solicitud de exportación de Lista Negra.
    """
    filtros: Optional[Dict[str, Any]] = None
    formato: str = "excel"
    visible_columns: List[str]
    sort_field: Optional[str] = None
    sort_order: Optional[int] = None # 1 para ASC, -1 para DESC    