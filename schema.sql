-- Observatorio SEO: esquema de la base en Neon
-- Fuente: API de Google Search Console

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