import logging
import json
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    text, select, func, cast, String, column, Table,
    MetaData, Numeric, Date, and_
)
from app.config import config

logger = logging.getLogger(__name__)


# --- OPERACIONES DE REPORTES (DASHBOARD) ---    
def obtener_datos_funnel_db(db_session, fecha_inicio: str, periodo: str) -> list[dict]:
    """
    Ejecuta la consulta del Funnel de Cobranza.
    """
    try:
        # Nota: La query original estaba hardcodeada para '0020ACSA'. 
        # Si quieres que sea dinámico, pasa 'cliente' como argumento.
        query = text("""
            DECLARE @FECHA_INICIO VARCHAR(10)=:fecha_inicio;
            DECLARE @PERIODO VARCHAR(10)=:periodo;
            
            WITH TodasLasGestiones AS (
                SELECT traf.CLIENTE, asig.CARTERA, traf.FECHA, traf.RUT, traf.TIPIFICACION, traf.gestion 
                FROM b2c.dbo.[0900TRAF_202511MASI] traf
                INNER JOIN B2C.dbo.[0900EFIC_BASEASIG] asig ON traf.IC = asig.IC
                WHERE traf.CLIENTE='0020ACSA'
                AND traf.TIPO='BOT'
                AND asig.PERIODO = @PERIODO
                AND traf.fecha >= @FECHA_INICIO
            )
            SELECT
                CLIENTE,
                FECHA,
                MAX(CARTERA) as CARTERA,
                COUNT(*) AS [Q.Gestiones],
                COUNT(DISTINCT RUT) AS [Q.Deudores],
                COUNT(DISTINCT CASE WHEN TIPIFICACION = 'CD' THEN RUT END) AS [Q.CD],
                COUNT(DISTINCT CASE WHEN Gestion='Compromiso' THEN RUT END) AS [Q.Compromisos]
            FROM
                TodasLasGestiones
            GROUP BY
                CLIENTE,FECHA,CARTERA
            ORDER BY
                CLIENTE,FECHA,CARTERA;
        """)
        
        result = db_session.execute(query, {"fecha_inicio": fecha_inicio, "periodo": periodo})
        return [dict(row._mapping) for row in result.fetchall()]
        
    except Exception as e:
        logger.error(f"Error obteniendo datos del funnel: {e}", exc_info=True)
        raise e    