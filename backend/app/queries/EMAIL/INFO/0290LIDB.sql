SELECT DISTINCT 
    RUT
FROM 
    B2C_OPER.DBO.[1009_RTG_0290LIDB_] WITH (NOLOCK)
WHERE 
    ISNULL(ULTIMA_GESTION, '') <> 'BLOQUEO' -- Validar que no esté bloqueado
    --AND DEUDA > ISNULL([MONTO PAGADO], 0) -- Validar vigencia de deuda
    and CONVERT(DECIMAL(18,2), DEUDA) > CONVERT(DECIMAL(18,2), ISNULL([MONTO PAGADO], 0))-- Validar vigencia de deuda
	AND ISNULL(NOMBRE, '') <> 'SIN NOMBRE' -- Validar que el nombre no sea "SIN NOMBRE"
