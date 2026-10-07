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