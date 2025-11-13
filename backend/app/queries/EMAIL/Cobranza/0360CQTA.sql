--select CONVERT(VARCHAR, idempresa) AS idempresa
  select CONVERT(VARCHAR, SUBSTRING(idempresa, PATINDEX('%[0-9]%', idempresa), LEN(idempresa)) ) AS idempresa
    from [B2C_OPER].dbo.[1009_RTG_0360CQTA_] 
    where 	
	(
        ISNULL(ULTIMA_GESTION, '') NOT IN ('BLOQUEO TEMPORAL', 'BLOQUEO PAGO') -- BLOQUEOS RUT
    )
    AND ISNULL(NOMBRE, '') <> 'SIN NOMBRE'