DECLARE @DiaSemana INT =  ((DATEPART(WEEKDAY, GETDATE()) + @@DATEFIRST + 5) % 7 + 1)

SELECT DISTINCT 
    CONVERT(VARCHAR, RUT) AS RUT
FROM 
    B2C_OPER.DBO.[1009_RTG_0020ACSA_] WITH (NOLOCK)
WHERE 
    -- 1. Filtros básicos de exclusión
    (ISNULL(ULTIMA_GESTION, '') NOT IN ('BLOQUEO ACSA', 'BLOQUEO PAGO')) 
    AND ISNULL(NOMBRE, '') <> 'SIN NOMBRE'
    
    -- 2. Nueva validación estricta: 
    -- Se suman todos los días de la semana. Si la suma es distinta de 0, el RUT se descarta.
    AND (
        CONVERT(INT, ISNULL(MAIL_LUNES, '0')) + 
        CONVERT(INT, ISNULL(MAIL_MARTES, '0')) + 
        CONVERT(INT, ISNULL(MAIL_MIERCOLES, '0')) + 
        CONVERT(INT, ISNULL(MAIL_JUEVES, '0')) + 
        CONVERT(INT, ISNULL(MAIL_VIERNES, '0')) + 
        CONVERT(INT, ISNULL(MAIL_SABADO, '0'))
    ) = 0 -- Solo pasa si la suma total de gestiones es exactamente 0