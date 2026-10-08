-- =====================================================
-- Observatorio SEO - 03: Análisis
-- =====================================================

-- 1. Páginas del sitio ordenadas por clics
SELECT url, clics, impresiones, ctr, posicion
FROM paginas
ORDER BY clics DESC;


-- 2. Consultas que más clics traen
-- Hallazgo: 24 de 26 clics (92%) vienen de la búsqueda de marca
-- "Estudio juridico rios y asociados".
SELECT consulta, clics, impresiones, ctr, posicion
FROM consultas
ORDER BY clics DESC
LIMIT 10;


-- 3. Oportunidades de CTR: muchas impresiones y ningún clic
-- (Sin resultados en esta primera carga: sitio nuevo, poco volumen)
SELECT consulta, impresiones, clics, ctr, posicion
FROM consultas
WHERE impresiones > 50 AND clics = 0
ORDER BY impresiones DESC;


-- 4. "Casi página 1": consultas entre la posición 8 y 20
-- (Sin resultados en esta primera carga: sitio nuevo, poco volumen)
SELECT consulta, posicion, impresiones
FROM consultas
WHERE posicion BETWEEN 8 AND 20
ORDER BY impresiones DESC;


-- =====================================================
-- Análisis con los datos de la API (tabla rendimiento_api)
-- =====================================================

-- 5. Evolución diaria de clics e impresiones
SELECT fecha, SUM(clics) AS clics, SUM(impresiones) AS impresiones
FROM rendimiento_api
GROUP BY fecha
ORDER BY fecha;


-- 6. Tráfico de marca vs. sin marca
-- Mide cuánto depende el sitio de la gente que ya conoce al estudio.
SELECT
  CASE
    WHEN consulta ~* '\mr[ií]os\M' THEN 'Marca'  -- palabra completa: no cuenta "salarios" ni "honorarios"
    ELSE 'Sin marca'
  END AS tipo,
  SUM(clics) AS clics,
  SUM(impresiones) AS impresiones
FROM rendimiento_api
GROUP BY tipo;


-- 7. Qué consultas llevan a cada página
SELECT pagina, consulta, SUM(clics) AS clics, SUM(impresiones) AS impresiones
FROM rendimiento_api
GROUP BY pagina, consulta
ORDER BY pagina, impresiones DESC;

-- 8. Caídas y subidas de clics por página (últimos 7 días vs. los 7 anteriores)
-- Las primeras filas son las que mas cayeron, las ultimas las que mas subieron
WITH actual AS (
  SELECT pagina, SUM(clics) AS clics
  FROM rendimiento_api
  WHERE fecha >= CURRENT_DATE - 7
  GROUP BY pagina
),
anterior AS (
  SELECT pagina, SUM(clics) AS clics
  FROM rendimiento_api
  WHERE fecha >= CURRENT_DATE - 14 AND fecha < CURRENT_DATE - 7
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
FROM rendimiento_api
WHERE fecha >= CURRENT_DATE - 7
GROUP BY pagina
ORDER BY impresiones DESC;

--10. Oportunidades: Muchas Impresiones, Pocos clics
-- SEO: mejorar meta description y title 
SELECT consulta, pagina,
       SUM(impresiones) AS impresiones,
       SUM(clics) AS clics,
       ROUND(100.0 * SUM(clics) / NULLIF(SUM(impresiones), 0), 2) AS ctr,
       ROUND(SUM(posicion * impresiones) / NULLIF(SUM(impresiones), 0), 1) AS posicion_prom
FROM rendimiento_api
WHERE fecha >= CURRENT_DATE - 28
GROUP BY consulta, pagina
HAVING SUM(impresiones) >= 20
   AND SUM(clics) <= 1
ORDER BY impresiones DESC
LIMIT 20; 

--11. Consultas Nuevas (consultas que no estaban tageadas)
SELECT consulta, SUM(clics) AS clics, SUM(impresiones) AS impresiones
FROM rendimiento_api
WHERE fecha >= CURRENT_DATE - 7
  AND consulta NOT IN (
    SELECT DISTINCT consulta
    FROM rendimiento_api
    WHERE fecha < CURRENT_DATE - 7
  )
GROUP BY consulta
ORDER BY impresiones DESC;

--12. Comparación de ayer contra el mismo día de la semana anterior 
-- Los datos de la API tienen de 2 a 3 dias de retraso aproximadamente, para eso --> CURRENT_DATE - 3

SELECT fecha, SUM(clics) AS clics, SUM(impresiones) AS impresiones
FROM rendimiento_api
WHERE fecha IN (CURRENT_DATE - 3, CURRENT_DATE - 10)
GROUP BY fecha
ORDER BY fecha;
