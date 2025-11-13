DECLARE @DiaSemana INT =  ((DATEPART(WEEKDAY, GETDATE()) + @@DATEFIRST + 5) % 7 + 1)
SELECT DISTINCT 
    RUT
FROM 
    B2C_OPER.DBO.[1009_RTG_0290LIDB_] WITH (NOLOCK)
WHERE 
    ISNULL(ULTIMA_GESTION, '') <> 'BLOQUEO' -- Validar que no esté bloqueado
     AND CONVERT(DECIMAL(18,2), DEUDA) > CONVERT(DECIMAL(18,2), ISNULL([MONTO PAGADO], 0))-- Validar vigencia de deuda
    AND (
        -- Validar según el día de la semana
        CASE 
            -- Si es martes, validar que lunes sea igual a 0
            WHEN @DiaSemana = 2 THEN 
                CASE 
                    WHEN ISNULL(LUNES, '0') = '0' THEN 1 -- Si lunes es 0, es válido
                    ELSE 0 -- Si lunes no es 0, no es válido
                END
            -- Si es miércoles, validar que lunes y martes sean iguales a 0
            WHEN @DiaSemana = 3 THEN 
                CASE 
                    WHEN ISNULL(LUNES, '0') = '0' AND ISNULL(MARTES, '0') = '0' THEN 1 -- Si lunes y martes son 0, es válido
                    ELSE 0 -- Si lunes o martes no son 0, no es válido
                END
            -- Si es jueves, validar que martes y miércoles sean iguales a 0
            WHEN @DiaSemana = 4 THEN 
                CASE 
                    WHEN ISNULL(MARTES, '0') = '0' AND ISNULL(MIERCOLES, '0') = '0' THEN 1 -- Si martes y miércoles son 0, es válido
                    ELSE 0 -- Si martes o miércoles no son 0, no es válido
                END
            -- Si es viernes, validar que jueves y miércoles sean iguales a 0
            WHEN @DiaSemana = 5 THEN 
                CASE 
                    WHEN ISNULL(JUEVES, '0') = '0' AND ISNULL(MIERCOLES, '0') = '0' THEN 1 -- Si jueves y miércoles son 0, es válido
                    ELSE 0 -- Si jueves o miércoles no son 0, no es válido
                END
            -- Si es sábado, validar que viernes y jueves sean iguales a 0
            WHEN @DiaSemana = 6 THEN 
                CASE 
                    WHEN ISNULL(VIERNES, '0') = '0' AND ISNULL(JUEVES, '0') = '0' THEN 1 -- Si viernes y jueves son 0, es válido
                    ELSE 0 -- Si viernes o jueves no son 0, no es válido
                END
            ELSE 1 -- Para otros días, siempre es válido
        END = 1
    )    
	        AND (
        CONVERT(int,LUNES) + CONVERT(int,MARTES) + CONVERT(int,MIERCOLES) + CONVERT(int,JUEVES) + CONVERT(int,VIERNES) + CONVERT(int,SABADO) < 2 -- Validar que la suma de los días sea 0
    )     
