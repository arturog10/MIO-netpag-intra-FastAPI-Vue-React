-- -- PARA VALIDAR RUT PARA ENVÍO DE SMS O EMAIL ENTEL
-- -- ESTA QUERY MUESTRA LOS RUT A LOS QUE "SÍ" SE LES PUEDE MANDAR SMS O EMAIL.
-- -- HAY QUE FIJARSE EN EL DÍA DE AYER Y ANTES DE AYER EN LA QUERY.
DECLARE @DiaSemana INT =  ((DATEPART(WEEKDAY, GETDATE()) + @@DATEFIRST + 5) % 7 + 1)

SELECT DISTINCT 
    CONVERT(VARCHAR, RUT) AS RUT

FROM 
    B2C_OPER.DBO.[1009_RTG_0020ACSA_] WITH (NOLOCK)
WHERE 
    (
        ISNULL(ULTIMA_GESTION, '') NOT IN ('BLOQUEO ACSA', 'BLOQUEO PAGO') -- BLOQUEOS RUT
    )
    AND ISNULL(NOMBRE, '') <> 'SIN NOMBRE' -- Validar que el nombre no sea "SIN NOMBRE"
    AND (
        -- Validar según el día de la semana
        CASE 
            -- Si es martes, validar que lunes sea igual a 0
            WHEN @DiaSemana = 2 THEN 
                CASE 
                    WHEN ISNULL(MAIL_LUNES, '0') = '0' THEN 1 -- Si lunes es 0, es válido
                    ELSE 0 -- Si lunes no es 0, no es válido
                END
            -- Si es miércoles, validar que lunes y martes sean iguales a 0
            WHEN @DiaSemana = 3 THEN 
                CASE 
                    WHEN ISNULL(MAIL_LUNES, '0') = '0' AND ISNULL(MAIL_MARTES, '0') = '0' THEN 1 -- Si lunes y martes son 0, es válido
                    ELSE 0 -- Si lunes o martes no son 0, no es válido
                END
            -- Si es jueves, validar que martes y miércoles sean iguales a 0
            WHEN @DiaSemana = 4 THEN 
                CASE 
                    WHEN ISNULL(MAIL_MARTES, '0') = '0' AND ISNULL(MAIL_MIERCOLES, '0') = '0' THEN 1 -- Si martes y miércoles son 0, es válido
                    ELSE 0 -- Si martes o miércoles no son 0, no es válido
                END
            -- Si es viernes, validar que jueves y miércoles sean iguales a 0
            WHEN @DiaSemana = 5 THEN 
                CASE 
                    WHEN ISNULL(MAIL_JUEVES, '0') = '0' AND ISNULL(MAIL_MIERCOLES, '0') = '0' THEN 1 -- Si jueves y miércoles son 0, es válido
                    ELSE 0 -- Si jueves o miércoles no son 0, no es válido
                END
            -- Si es sábado, validar que viernes y jueves sean iguales a 0
            WHEN @DiaSemana = 6 THEN 
                CASE 
                    WHEN ISNULL(MAIL_VIERNES, '0') = '0' AND ISNULL(MAIL_JUEVES, '0') = '0' THEN 1 -- Si viernes y jueves son 0, es válido
                    ELSE 0 -- Si viernes o jueves no son 0, no es válido
                END
            ELSE 1 -- Para otros días, siempre es válido
        END = 1
    ) AND (
        CONVERT(int,MAIL_LUNES) + CONVERT(int,MAIL_MARTES) + CONVERT(int,MAIL_MIERCOLES) + CONVERT(int,MAIL_JUEVES) + CONVERT(int,MAIL_VIERNES) + CONVERT(int,MAIL_SABADO) < 2 -- Validar que la suma de los días sea 0
    )     
-- SELECT CONVERT(VARCHAR, RUT) AS RUT
-- FROM b2c.dbo.masiv_dia 
-- WHERE cliente = '0020ACSA' 
-- AND fecha_ges = CONVERT(VARCHAR(10), GETDATE(), 23) 
-- AND hora >= CONVERT(TIME, GETDATE())