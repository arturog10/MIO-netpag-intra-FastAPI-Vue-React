    -- PARA VALIDAR RUT PARA ENVÍO DE SMS O EMAIL ENTEL
    -- ESTO MOSTRARÁ LOS RUT A LOS QUE "SÍ" SE LES PUEDE ENVIAR MASIVIDAD.
    -- TENER EN CUENTA QUE LA TABLA [1009_RTG_0200ENTE_202502] Y [XXXX_SALDOS_0200ENTE] 
    -- ESTÉN ACTUALIZADAS CON LA ÚLTIMA INFORMACIÓN DEL DÍA.
    -- ESTA TABLA [XXXX_CUENTAS_0200ENTE] TIENE QUE CONTENER TODOS LOS RUT, CUENTAS, 
    -- FOLIOS DE LO ASIGNADO EN EL MES. SE VA LLENANDO CUANDO EL CLIENTE ENVÍA ASIGNACIONES.
    DECLARE @DiaSemana INT =  ((DATEPART(WEEKDAY, GETDATE()) + @@DATEFIRST + 5) % 7 + 1)

    SELECT DISTINCT 
        CONVERT(VARCHAR, RUT) AS RUT
    FROM 
        B2C_OPER.DBO.[1009_RTG_0200ENTE_] WITH (NOLOCK)
    WHERE 
        ISNULL(ULTIMA_GESTION, '') NOT LIKE '%BLOQUEO%'
        AND ISNULL(NOMBRE, '') <> 'SIN NOMBRE' -- Validar que el nombre no sea "SIN NOMBRE"
        AND RUT IN (
            SELECT 
                A1.RUT
            FROM 
                B2C_OPER.DBO.[XXXX_CUENTAS_0200ENTE] A1 WITH (NOLOCK)
            INNER JOIN 
                B2C_OPER.DBO.[XXXX_SALDOS_0200ENTE] A2 WITH (NOLOCK)
            ON 
                A1.FOLIO = A2.[FOLIO DOC]
            GROUP BY 
                A1.RUT
        ) -- ESTO VALIDA LA VIGENCIA DEL RUT
        AND (
            -- Usar CASE para validar según el día de la semana
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
        )      AND (
            CONVERT(int,LUNES) + CONVERT(int,MARTES) + CONVERT(int,MIERCOLES) + CONVERT(int,JUEVES) + CONVERT(int,VIERNES) + CONVERT(int,SABADO) < 2 -- Validar que la suma de los días sea 0
        )    
