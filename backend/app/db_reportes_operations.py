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
    
def obtener_rechazos_historicos(db, fecha_desde, fecha_hasta, cliente=None):
    """
    Consulta la tabla de rechazos (RechazosHistoricos).
    Usa conversión explicita estilo 120 (ODBC) para evitar errores de fecha.
    """
    try:
        # Usamos >= y <= con CONVERT explícito para evitar problemas de región
        sql = """
            SELECT 
                CONVERT(VARCHAR, fecha_proceso, 103) + ' ' + CONVERT(VARCHAR, fecha_proceso, 108) as fecha,
                cliente, 
                rut, 
                telefono, 
                mail, 
                motivo_rechazo, 
                archivo_origen
            FROM B2C.dbo.RechazosHistoricos
            WHERE fecha_proceso >= CONVERT(DATETIME, :f_inicio, 120) 
              AND fecha_proceso <= CONVERT(DATETIME, :f_fin, 120)
        """
        
        # Aseguramos formato string compatible con estilo 120 (yyyy-mm-dd hh:mm:ss)
        params = {
            "f_inicio": f"{fecha_desde} 00:00:00", 
            "f_fin": f"{fecha_hasta} 23:59:59"
        }
        
        if cliente:
            sql += " AND cliente = :cli"
            params["cli"] = cliente
            
        sql += " ORDER BY fecha_proceso DESC"
        
        result = db.execute(text(sql), params).fetchall()
        return [dict(row._mapping) for row in result]
        
    except Exception as e:
        logger.error(f"Error consultando rechazos: {e}")
        raise e

def obtener_gestion_diaria(db, fecha_desde, fecha_hasta, cliente=None):
    """
    Consulta la tabla masiv_dia para ver lo gestionado.
    """
    try:
        sql = """
            SELECT 
                CONVERT(VARCHAR, fecha_ges, 103) + ' ' + ISNULL(CONVERT(VARCHAR(5), hora_ges), '') as fecha,
                cliente, 
                rut, 
                fono as telefono, 
                mail, 
                tipo_ges as gestion,
                ic,
                id_emp
            FROM B2C.dbo.masiv_dia WITH(NOLOCK)
            WHERE fecha_ges >= CONVERT(DATE, :f_inicio, 120) 
              AND fecha_ges <= CONVERT(DATE, :f_fin, 120)
        """
        
        # fecha_ges es DATE, así que basta con la fecha
        params = {
            "f_inicio": fecha_desde, 
            "f_fin": fecha_hasta
        }
        
        if cliente:
            sql += " AND cliente = :cli"
            params["cli"] = cliente
            
        sql += " ORDER BY fecha_ges DESC, hora_ges DESC"
        
        result = db.execute(text(sql), params).fetchall()
        return [dict(row._mapping) for row in result]
        
    except Exception as e:
        logger.error(f"Error consultando gestión (masiv_dia): {e}")
        raise e