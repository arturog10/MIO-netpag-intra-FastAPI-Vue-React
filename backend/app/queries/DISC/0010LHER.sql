DECLARE @DiaSemana INT =  ((DATEPART(WEEKDAY, GETDATE()) + @@DATEFIRST + 5) % 7 + 1)
SELECT DISTINCT 
    RUT
FROM 
    B2C_OPER.DBO.[1009_RTG_0024LHER_] WITH (NOLOCK)
WHERE 
    ISNULL(ULTIMA_GESTION, '') <> 'BLOQUEO' -- Validar que no esté bloqueado
   -- AND DEUDA > ISNULL([PAGO], 0) -- Validar vigencia de deuda
    AND CONVERT(DECIMAL(18,2), DEUDA) > CONVERT(DECIMAL(18,2), ISNULL([PAGO], 0))
    -- 2. Nueva validación estricta: 
    -- Se suman todos los días de la semana. Si la suma es distinta de 0, el RUT se descarta.
    AND (
        CONVERT(INT, ISNULL(LUNES, '0')) + 
        CONVERT(INT, ISNULL(MARTES, '0')) + 
        CONVERT(INT, ISNULL(MIERCOLES, '0')) + 
        CONVERT(INT, ISNULL(JUEVES, '0')) + 
        CONVERT(INT, ISNULL(VIERNES, '0')) + 
        CONVERT(INT, ISNULL(SABADO, '0'))
    ) = 0 -- Solo pasa si la suma total de gestiones es exactamente 0