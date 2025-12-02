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
