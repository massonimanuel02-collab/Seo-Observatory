-- =====================================================
-- Observatorio SEO - 01: Creación de tablas
-- Fuente: Google Search Console 
-- =====================================================

-- Tabla con el rendimiento diario del sitio (datos de Search Console)

CREATE TABLE IF NOT EXISTS rendimiento_diario(
     fecha        DATE PRIMARY KEY,
    clics        INTEGER NOT NULL,
    impresiones  INTEGER NOT NULL,
    ctr          NUMERIC(5,2),
    posicion     NUMERIC(5,2)
);

-- TABLA DE PASO, POSTGRE NO ACEPTA '2,5%' LO CONVERTIMOS A TXT(STRING)
CREATE TABLE IF NOT EXISTS stg_fechas (
    fecha        TEXT,
    clics        TEXT,
    impresiones  TEXT,
    ctr          TEXT,
    posicion     TEXT
);

-- TABLA DE PASO CONSULTAS 
CREATE TABLE IF NOT EXISTS consultas_raw (
  consulta TEXT,
  clics TEXT,
  impresiones TEXT,
  ctr TEXT,
  posicion TEXT
);

-- TABLA DE PASO PAGINAS 

CREATE TABLE IF NOT EXISTS paginas_raw (
  url TEXT,
  clics TEXT,
  impresiones TEXT,
  ctr TEXT,
  posicion TEXT
);

-- TABLAS FINALES (se llenan desde las tablas de paso en 02_cargar_datos.sql)
CREATE TABLE IF NOT EXISTS consultas (
  consulta     TEXT,
  clics        INTEGER,
  impresiones  INTEGER,
  ctr          NUMERIC(5,2),
  posicion     NUMERIC(5,2)
);

CREATE TABLE IF NOT EXISTS paginas (
  url          TEXT,
  clics        INTEGER,
  impresiones  INTEGER,
  ctr          NUMERIC(5,2),
  posicion     NUMERIC(5,2)
);
