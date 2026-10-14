-- Observatorio SEO: esquema de la base en Neon
-- Fuente: API de Google Search Console
--
-- La API se pide con tres cortes distintos, y cada uno guarda cosas distintas:
--   totales_diarios      dimensión "date"                  -> coincide con el panel de Search Console
--   rendimiento_paginas  dimensiones "date" + "page"       -> coincide con el panel (clics)
--   rendimiento_api      dimensiones "date"+"query"+"page" -> OMITE las consultas anónimas
-- Pedir la consulta hace que Search Console descarte las anónimas: en este sitio son ~70 % de
-- los clics. Por eso rendimiento_api sirve para analizar consultas, no para sacar totales.

-- Por consulta y página (omite las consultas anónimas, ver arriba)
CREATE TABLE IF NOT EXISTS rendimiento_api (
    id          SERIAL PRIMARY KEY,
    fecha       DATE NOT NULL,
    consulta    TEXT NOT NULL,
    pagina      TEXT NOT NULL,
    clics       INTEGER,
    impresiones INTEGER,
    ctr         NUMERIC(5,2),   -- en porcentaje (ej. 42.11)
    posicion    NUMERIC(6,2),

    -- Evita duplicados: si el script corre dos veces el mismo día,
    -- actualiza la fila en vez de repetirla.
    UNIQUE (fecha, consulta, pagina)
);

-- Para el dashboard: comparar el rendimiento de una página a lo largo del tiempo
CREATE INDEX IF NOT EXISTS idx_rendimiento_pagina_fecha
    ON rendimiento_api (pagina, fecha);

-- Totales del sitio por día. Incluye las consultas anónimas: es lo que muestra el panel.
CREATE TABLE IF NOT EXISTS totales_diarios (
    fecha       DATE PRIMARY KEY,
    clics       INTEGER,
    impresiones INTEGER,
    ctr         NUMERIC(5,2),   -- en porcentaje
    posicion    NUMERIC(6,2)
);

-- Por página y día. Incluye las consultas anónimas. Los clics suman lo mismo que
-- totales_diarios; las impresiones, ~1 % más (la API cuenta por página, no por sitio).
CREATE TABLE IF NOT EXISTS rendimiento_paginas (
    fecha       DATE NOT NULL,
    pagina      TEXT NOT NULL,
    clics       INTEGER,
    impresiones INTEGER,
    ctr         NUMERIC(5,2),   -- en porcentaje
    posicion    NUMERIC(6,2),
    PRIMARY KEY (fecha, pagina)
);

-- Vista para el análisis: unifica la misma página con y sin "www", con http/https
-- y con "/" final (la propiedad es de dominio, Search Console las reporta por separado).
-- Las consultas de sql/03_analisis.sql leen esta vista en vez de la tabla.
CREATE OR REPLACE VIEW v_rendimiento AS
SELECT fecha, consulta, clics, impresiones, posicion,
       regexp_replace(pagina, '^https?://(www\.)?|/$', '', 'g') AS pagina
FROM rendimiento_api;

-- Lo mismo para rendimiento_paginas. Agrupar por página al consultar (SUM de clics).
CREATE OR REPLACE VIEW v_rendimiento_paginas AS
SELECT fecha, clics, impresiones, posicion,
       regexp_replace(pagina, '^https?://(www\.)?|/$', '', 'g') AS pagina
FROM rendimiento_paginas;

-- Último día con datos completos. Search Console tarda 2-3 días en consolidar,
-- así que las ventanas ("últimos 7 días") terminan acá y no en hoy.
-- Debe coincidir con el margen de cargar_datos_api.py (timedelta(days=3)).
-- ponytail: ancla fija a hoy - 3; si se analiza sin haber corrido la ingesta, los días sin cargar se ven como 0.
--   Para reproducir una semana pasada, guardar la fecha de la última ingesta y leerla acá.
CREATE OR REPLACE VIEW v_ventana AS
SELECT CURRENT_DATE - 3 AS fin;
