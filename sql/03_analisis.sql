-- =====================================================
-- Observatorio SEO - 03: Análisis
-- =====================================================

-- Consultas 1 a 4: datos de los CSV de la Etapa 1 (tablas consultas y paginas,
-- cargadas con 02_cargar_datos.sql). No usan la API.

-- 1. Páginas del sitio ordenadas por clics
SELECT url, clics, impresiones, ctr, posicion
FROM paginas
ORDER BY clics DESC;


-- 2. Consultas que más clics traen
-- En un sitio nuevo, casi todos suelen venir de la búsqueda de marca.
SELECT consulta, clics, impresiones, ctr, posicion
FROM consultas
ORDER BY clics DESC
LIMIT 10;


-- 3. Oportunidades de CTR: muchas impresiones y ningún clic
SELECT consulta, impresiones, clics, ctr, posicion
FROM consultas
WHERE impresiones > 50 AND clics = 0
ORDER BY impresiones DESC;


-- 4. "Casi página 1": consultas entre la posición 8 y 20
SELECT consulta, posicion, impresiones
FROM consultas
WHERE posicion BETWEEN 8 AND 20
ORDER BY impresiones DESC;


-- =====================================================
-- Análisis con los datos de la API
-- =====================================================
-- La API se carga con tres cortes (ver schema.sql) y cada consulta lee el que le corresponde:
--   5 y 12 (totales por día)       -> totales_diarios
--   8 y 9  (por página)            -> v_rendimiento_paginas (páginas unificadas)
--   6, 7, 10 y 11 (por consulta)   -> rendimiento_api / v_rendimiento
-- OJO: el corte por consulta omite las consultas anónimas, que en este sitio son ~70 % de los
-- clics, así que las consultas 6, 7, 10 y 11 solo ven las consultas visibles. Los totales y las
-- páginas (5, 8, 9 y 12) sí coinciden con Search Console.
-- Las ventanas ("últimos 7 días") terminan en v_ventana.fin = hoy - 3, el último día con
-- datos completos: si terminaran hoy, tendrían solo 5 días con datos contra 7 de la anterior.

-- 5. Evolución diaria de clics e impresiones
-- Lee totales_diarios (una fila por día, incluye las consultas anónimas).
-- generate_series incluye los días sin filas (con 0) en vez de saltearlos. Termina en v_ventana.fin.
SELECT d::date AS fecha,
       COALESCE(t.clics, 0) AS clics,
       COALESCE(t.impresiones, 0) AS impresiones
FROM generate_series(
       (SELECT MIN(fecha) FROM totales_diarios),
       (SELECT fin FROM v_ventana),
       interval '1 day'
     ) AS d
LEFT JOIN totales_diarios t ON t.fecha = d::date
ORDER BY d;


-- 6. Tráfico de marca vs. sin marca
-- Mide cuánto depende el sitio de la gente que ya conoce al estudio.
SELECT
  CASE
    WHEN consulta ~* '\mr[ií]os\M' AND consulta !~* 'entre r[ií]os' THEN 'Marca'  -- palabra completa (no "salarios") y sin la provincia "Entre Ríos"
    ELSE 'Sin marca'
  END AS tipo,
  SUM(clics) AS clics,
  SUM(impresiones) AS impresiones
FROM rendimiento_api
GROUP BY tipo;


-- 7. Qué consultas llevan a cada página
SELECT pagina, consulta, SUM(clics) AS clics, SUM(impresiones) AS impresiones
FROM v_rendimiento
GROUP BY pagina, consulta
ORDER BY pagina, impresiones DESC;

-- 8. Caídas y subidas de clics por página (últimos 7 días con datos vs. los 7 anteriores)
-- Las primeras filas son las que mas cayeron, las ultimas las que mas subieron
-- Con poco volumen 1 clic de diferencia ya es +-100 %: mirá clics_antes y clics_ahora antes de sacar conclusiones.
WITH actual AS (
  SELECT pagina, SUM(clics) AS clics
  FROM v_rendimiento_paginas, v_ventana
  WHERE fecha > fin - 7 AND fecha <= fin
  GROUP BY pagina
),
anterior AS (
  SELECT pagina, SUM(clics) AS clics
  FROM v_rendimiento_paginas, v_ventana
  WHERE fecha > fin - 14 AND fecha <= fin - 7
  GROUP BY pagina
)
SELECT
  COALESCE(a.pagina, p.pagina) AS pagina,
  COALESCE(p.clics, 0) AS clics_antes,
  COALESCE(a.clics, 0) AS clics_ahora,
  COALESCE(a.clics, 0) - COALESCE(p.clics, 0) AS diferencia
FROM actual a
FULL JOIN anterior p ON a.pagina = p.pagina
ORDER BY diferencia;

--9. Posicion Promedio por Pagina 
SELECT pagina,
       ROUND(SUM(posicion * impresiones) / NULLIF(SUM(impresiones), 0), 1) AS posicion_prom,
       SUM(impresiones) AS impresiones
FROM v_rendimiento_paginas, v_ventana
WHERE fecha > fin - 7 AND fecha <= fin
GROUP BY pagina
ORDER BY impresiones DESC;

--10. Oportunidades: Muchas Impresiones, Pocos clics
-- SEO: mejorar meta description y title 
SELECT consulta, pagina,
       SUM(impresiones) AS impresiones,
       SUM(clics) AS clics,
       ROUND(100.0 * SUM(clics) / NULLIF(SUM(impresiones), 0), 2) AS ctr,
       ROUND(SUM(posicion * impresiones) / NULLIF(SUM(impresiones), 0), 1) AS posicion_prom
FROM v_rendimiento, v_ventana
WHERE fecha > fin - 28 AND fecha <= fin
GROUP BY consulta, pagina
HAVING SUM(impresiones) >= 20
   AND SUM(clics) <= 1
ORDER BY impresiones DESC
LIMIT 20; 

--11. Consultas Nuevas (consultas que no estaban tageadas)
SELECT consulta, SUM(clics) AS clics, SUM(impresiones) AS impresiones
FROM rendimiento_api, v_ventana
WHERE fecha > fin - 7 AND fecha <= fin
  AND consulta NOT IN (
    SELECT DISTINCT consulta
    FROM rendimiento_api, v_ventana
    WHERE fecha <= fin - 7
  )
GROUP BY consulta
ORDER BY impresiones DESC;

--12. Comparación de ayer contra el mismo día de la semana anterior 
-- Los datos de la API tienen de 2 a 3 dias de retraso aproximadamente: "ayer" es v_ventana.fin (hoy - 3).
-- Lee totales_diarios. Un día sin filas se muestra con 0.

SELECT dias.d AS fecha,
       COALESCE(t.clics, 0) AS clics,
       COALESCE(t.impresiones, 0) AS impresiones
FROM v_ventana v
CROSS JOIN LATERAL (VALUES (v.fin - 7), (v.fin)) AS dias(d)
LEFT JOIN totales_diarios t ON t.fecha = dias.d
ORDER BY dias.d;
