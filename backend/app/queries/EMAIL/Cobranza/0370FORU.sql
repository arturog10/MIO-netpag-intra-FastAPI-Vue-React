

-- SET DATEFIRST 1;
-- DECLARE @AYER				VARCHAR(8)=CONVERT(VARCHAR,DATEADD(DAY, IIF(DATEPART(WEEKDAY, GETDATE())>1,DATEPART(WEEKDAY, GETDATE())-1,NULL) - DATEPART(WEEKDAY, GETDATE()), CAST(GETDATE() AS DATE)),112)
-- DECLARE @ANTESDEAYER	VARCHAR(8)=CONVERT(VARCHAR,DATEADD(DAY, IIF(DATEPART(WEEKDAY, GETDATE())>2,DATEPART(WEEKDAY, GETDATE())-2,NULL) - DATEPART(WEEKDAY, GETDATE()), CAST(GETDATE() AS DATE)),112)
-- --PRINT @AYER
-- --PRINT @ANTESDEAYER

-- --A ESTOS RUT, "NO" SE LES PUEDE ENVIAR EMAIL. SI NO DA RESULTADO QUIERE DECIR QUE ESA SEMANA AUN NO LE ENVIAN EMAILS
-- SELECT RUT FROM(
-- SELECT RUT,Q=COUNT(*),FECHA_ENVIO=MAX(CONVERT(DATE,FECHA))
-- FROM B2C.DBO.[0900TRAF_202506MASI]WITH(NOLOCK)
-- WHERE CLIENTE ='0370FORU' AND TIPO='MAIL'	AND GESTION IN('Abierto','Sin apertura','ENTREGADO')
-- GROUP BY RUT)X WHERE X.Q>1 OR FECHA_ENVIO IN(@ANTESDEAYER,@AYER)

--select * from B2C_OPER.DBO.[1009_RTG_0370FORU_] -- aqui quedan los reportes de gestiones totales

DECLARE @DiaSemana INT =  ((DATEPART(WEEKDAY, GETDATE()) + @@DATEFIRST + 5) % 7 + 1)
SELECT DISTINCT 
    RUT
FROM 
    B2C_OPER.DBO.[1009_RTG_0370FORU_] WITH (NOLOCK)
WHERE 
    ISNULL(ULTIMA_GESTION, '') <> 'BLOQUEO' -- Validar que no esté bloqueado
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
    )    
	        AND (
        MAIL_LUNES + MAIL_MARTES + MAIL_MIERCOLES + MAIL_JUEVES + MAIL_VIERNES + MAIL_SABADO < 2 -- Validar que la suma de los días sea 0
    )     
