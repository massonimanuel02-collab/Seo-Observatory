=====================================================
-- Observatorio SEO - 01: Creación de tablas
-- Fuente: Google Search Console 
-- =====================================================

-- Tabla con el rendimiento diario del sitio (datos de Search Console)

CREATE TABLE rendimiento_diario(
     fecha        DATE PRIMARY KEY,
    clics        INTEGER NOT NULL,
    impresiones  INTEGER NOT NULL,
    ctr          NUMERIC(5,2),
    posicion     NUMERIC(5,2)
);

-- TABLA DE PASO, POSTGRE NO ACEPTA '2,5%' LO CONVERTIMOS A TXT(STRING)
CREATE TABLE stg_fechas (
    fecha        TEXT,
    clics        TEXT,
    impresiones  TEXT,
    ctr          TEXT,
    posicion     TEXT
);

-- TABLA DE PASO CONSULTAS 
CREATE TABLE consultas_raw (
  consulta TEXT,
  clics TEXT,
  impresiones TEXT,
  ctr TEXT,
  posicion TEXT
);

-- TABLA DE PASO PAGINAS 

CREATE TABLE paginas_raw (
  url TEXT,
  clics TEXT,
  impresiones TEXT,
  ctr TEXT,
  posicion TEXT
);
