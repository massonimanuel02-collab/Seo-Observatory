 =====================================================
-- Observatorio SEO - 02: Carga y limpieza de datos
-- =====================================================


-- Carga o actualiza el rendimiento de un día.
-- Si la fecha ya existe, reemplaza los valores (Search Console ajusta los últimos días).
INSERT INTO rendimiento_diario (fecha, clics, impresiones, ctr, posicion)
VALUES ('2026-10-02', 18, 530, 3.40, 17.50)
ON CONFLICT (fecha) DO UPDATE SET
    clics       = EXCLUDED.clics,
    impresiones = EXCLUDED.impresiones,
    ctr         = EXCLUDED.ctr,
    posicion    = EXCLUDED.posicion;

-- :: convierte un tipo en otro. '2026-10-01'::DATE toma un texto y lo vuelve fecha.
-- REPLACE(ctr, '%', '') saca el %. El otro REPLACE cambia comas por puntos, por si tu Search Console exporta los decimales con coma
-- TRIM saca los espacios que puedan quedar en los bordes.
-- INSERT ... SELECT: en vez de escribir los valores a mano con VALUES, los toma del resultado de una consulta.

-- DATA RENDIMIENTO DIARIO 
INSERT INTO rendimiento_diario (fecha, clics, impresiones, ctr, posicion)
SELECT
    fecha::DATE,
    clics::INTEGER,
    impresiones::INTEGER,
    TRIM(REPLACE(REPLACE(ctr, '%', ''), ',', '.'))::NUMERIC,
    TRIM(REPLACE(posicion, ',', '.'))::NUMERIC
FROM stg_fechas
ON CONFLICT (fecha) DO UPDATE SET
    clics       = EXCLUDED.clics,
    impresiones = EXCLUDED.impresiones,
    ctr         = EXCLUDED.ctr,
    posicion    = EXCLUDED.posicion;

-- DATA CONSULTAS 
INSERT INTO consultas (consulta, clics, impresiones, ctr, posicion)
SELECT
  consulta,
  clics::INTEGER,
  impresiones::INTEGER,
  REPLACE(ctr, '%', '')::NUMERIC,
  posicion::NUMERIC
FROM consultas_raw;

--REPLACE saca el % 
-- :: convierte el texto a número. Después repetís lo mismo con paginas_raw → paginas

--DATA PAGINAS 
INSERT INTO paginas (url, clics, impresiones, ctr, posicion)
SELECT
  url,
  clics::INTEGER,
  impresiones::INTEGER,
  REPLACE(ctr, '%', '')::NUMERIC,
  posicion::NUMERIC
FROM paginas_raw;
