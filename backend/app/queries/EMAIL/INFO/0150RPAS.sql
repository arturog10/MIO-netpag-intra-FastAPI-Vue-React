-- A ESTOS RUT "SÍ" SE LES PUEDE HACER GESTIÓN DE COBRANZA

SELECT DISTINCT 
    RUT
FROM 
    B2C_OPER.DBO.[1009_RTG_0150RPAS_] WITH (NOLOCK) -- 57646
WHERE 
    ISNULL(ULTIMA_GESTION, '') NOT LIKE '%BLOQUEO%' -- Validar que no esté bloqueado
	and CONVERT(DECIMAL(18,2), DEUDA) > CONVERT(DECIMAL(18,2), ISNULL(PAGO, 0))-- Validar vigencia de deuda
    --AND DEUDA > ISNULL(PAGO, 0) -- Validar vigencia de deuda
    AND ISNULL(NOMBRE, '') <> 'SIN NOMBRE' -- Validar que el nombre no sea "SIN NOMBRE"