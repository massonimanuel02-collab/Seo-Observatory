=====================================================
-- Observatorio SEO - 04: Tabla para los datos de la API
-- =====================================================
-- A diferencia de los CSV, la API trae los datos día por día,
-- combinando consulta y página. Esta tabla guarda ese historial.
-- (La tabla rendimiento_diario ya existe con los datos de fechas.csv
-- de la Etapa 1, por eso esta se llama distinto.)
 
CREATE TABLE rendimiento_api (
  id SERIAL PRIMARY KEY,
  fecha DATE NOT NULL,
  consulta TEXT NOT NULL,
  pagina TEXT NOT NULL,
  clics INTEGER,
  impresiones INTEGER,
  ctr NUMERIC(5,2),       -- en porcentaje (ej. 42.11)
  posicion NUMERIC(6,2),
 
  -- Evita duplicados: no puede haber dos filas con la misma
  -- fecha + consulta + página. Si el script corre dos veces,
  -- actualiza la fila en vez de repetirla.
  UNIQUE (fecha, consulta, pagina)
);
 
 
-- Verificación después de correr el script:
-- clics totales por día
SELECT fecha, SUM(clics) AS clics, SUM(impresiones) AS impresiones
FROM rendimiento_api
GROUP BY fecha
ORDER BY fecha;
 