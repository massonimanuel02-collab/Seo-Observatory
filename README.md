# Observatorio SEO

Sistema de monitoreo SEO construido con datos reales de Google Search Console, PostgreSQL y Python. Proyecto de aprendizaje desarrollado por etapas a lo largo de ~6 meses, usando como caso real el sitio de Estudio Jurídico Ríos.

## Etapas del proyecto

- [x] **Etapa 1** — PostgreSQL local: carga manual de CSV de Search Console y primer análisis
- [x] **Etapa 2** — Python trae los datos solo desde la API de Search Console
- [ ] **Etapa 3** — Base en la nube y ejecución diaria automática
- [ ] **Etapa 4** — Dashboard con la evolución, páginas que suben y páginas que bajan
- [ ] **Etapa 5** — Capa de IA: detección de caídas con SQL y resumen semanal automático
- [ ] **Etapa 6** — Documentación final y video demo

## Estructura del repositorio

```
observatorio_seo/
├── datos/                    # Exportaciones CSV de Search Console (Etapa 1)
├── sql/
│   ├── 01_crear_tablas.sql   # Tablas de consultas y páginas (staging + finales)
│   ├── 02_cargar_datos.sql   # Limpieza y carga de los CSV
│   ├── 03_analisis.sql       # Consultas de análisis
│   └── 04_creartabla_api.sql # Tabla para los datos de la API
├── cargar_datos_api.py       # Script que trae los datos de la API a PostgreSQL
├── test_conexion.py          # Prueba de conexión con la API
├── requirements.txt          # Librerías de Python necesarias
├── .env.example              # Plantilla de configuración de la base de datos
└── README.md
```

## Cómo usarlo

1. Instalar las librerías:
   ```
   pip install -r requirements.txt
   ```
2. Crear una cuenta de servicio en Google Cloud, habilitar la Google Search Console API, descargar la clave como `credenciales.json` y agregar el email de la cuenta como usuario en Search Console.
3. Copiar `.env.example` como `.env` y completar los datos de conexión a PostgreSQL.
4. Crear la tabla ejecutando `sql/04_creartabla_api.sql`.
5. Ejecutar:
   ```
   python cargar_datos_api.py
   ```

---

## Etapa 1: Carga y primer análisis de Search Console en PostgreSQL

**Objetivo**
Construir la base del sistema de monitoreo usando datos reales de Google Search Console del sitio de Estudio Jurídico Ríos y PostgreSQL como base de datos.

**Qué hice**

1. **Diseño de tablas:** creé las tablas `consultas` y `paginas` con tipos de datos adecuados para cada métrica (clics, impresiones, CTR y posición).
2. **Importación con tablas borrador (staging):** las exportaciones de Search Console traen el CTR como texto con `%` (ej. `3.45%`), lo que impide cargarlo directo en una columna numérica. Para resolverlo, importé primero los CSV a tablas `_raw` con todas las columnas en texto.
3. **Limpieza y transformación:** pasé los datos a las tablas finales con `INSERT ... SELECT`, quitando el `%` con `REPLACE` y convirtiendo tipos con `::INTEGER` y `::NUMERIC`.
4. **Validación de datos:** al verificar con `COUNT(*)`, detecté que la tabla `paginas` tenía 82 filas en lugar de 4: se habían cargado las consultas por error. Vacié las tablas con `TRUNCATE`, repetí la importación y confirmé el resultado correcto.
5. **Análisis:** escribí consultas SQL para identificar las búsquedas con más clics, oportunidades de CTR y keywords cerca de la primera página de resultados.

**Hallazgos**

- **Dependencia de la marca:** de las 26 visitas desde Google, 24 (92%) llegaron por la búsqueda del nombre del estudio. El sitio hoy atrae sobre todo a personas que ya lo conocían.
- **Primera señal de captación local:** "abogados laborales en parana" aparece en posición 3. Es una búsqueda sin marca, de alguien que todavía no eligió abogado, y es la principal oportunidad de crecimiento.
- **Búsqueda genérica con margen:** "estudio juridico" suma 40 impresiones en posición 6. Subir algunos puestos aumentaría los clics de forma notable.
- **Tráfico irrelevante identificado:** "medical malpractice lawyer" (en inglés) genera impresiones que no corresponden al público del estudio, por lo que se excluye de las conclusiones.

**Conclusión**
El sitio es nuevo y su visibilidad orgánica depende casi por completo de la marca, pero ya empieza a aparecer en búsquedas locales de servicios legales. La estrategia recomendada es crear contenido específico por área de práctica en Paraná, empezando por derecho laboral.

**Habilidades aplicadas:** PostgreSQL · SQL (CREATE, INSERT…SELECT, TRUNCATE, casting) · limpieza de datos · validación · Google Search Console · análisis SEO

---

## Etapa 2: Carga automática desde la API de Search Console

**Objetivo**
Reemplazar la exportación manual de CSV por un script de Python que se conecta directamente a la API de Google Search Console y guarda los datos en PostgreSQL.

**Qué hice**

1. **Autenticación con cuenta de servicio:** creé un proyecto en Google Cloud, habilité la Google Search Console API y generé una cuenta de servicio con permiso de solo lectura sobre la propiedad. Elegí una cuenta de servicio en lugar de OAuth porque permite que el script se ejecute sin iniciar sesión manualmente, algo necesario para automatizarlo en la Etapa 3.
2. **Prueba de conexión:** escribí `test_conexion.py` para confirmar el acceso antes de construir el script completo.
3. **Nueva tabla `rendimiento_api`:** a diferencia de los CSV, la API entrega los datos día por día y combinando consulta y página. Diseñé una tabla con esas tres dimensiones y una restricción `UNIQUE (fecha, consulta, pagina)`.
4. **Script de carga (`cargar_datos_api.py`):** trae los últimos 90 días de datos, dejando un margen de 3 días porque Search Console tarda en consolidar la información. Convierte el CTR de fracción (0.42) a porcentaje (42.00) para mantener el mismo formato que la Etapa 1.
5. **Carga sin duplicados:** uso `INSERT ... ON CONFLICT DO UPDATE`. Si el script corre más de una vez sobre las mismas fechas, actualiza las filas existentes en lugar de repetirlas.
6. **Protección de credenciales:** la clave de Google y la contraseña de la base viven en `credenciales.json` y `.env`, excluidos del repositorio con `.gitignore`. El repo incluye un `.env.example` como plantilla.

**Problemas que resolví**

- **Bloqueo de Windows:** el Control inteligente de aplicaciones de Windows 11 bloqueó el archivo `.dll` que necesita la librería `psycopg`. En lugar de desactivar una protección de seguridad del sistema, reemplacé la librería por `pg8000`, un conector escrito íntegramente en Python que no depende de archivos `.dll`.
- **Conflicto de nombres:** antes de crear la tabla nueva, revisé su estructura con `information_schema.columns` y detecté que ya existía una tabla `rendimiento_diario` con los datos de la Etapa 1. En lugar de reemplazarla, creé `rendimiento_api` para conservar ese registro.

**Resultado**
En una sola ejecución, el script cargó 291 filas con los datos del 4 de julio al 2 de octubre de 2026, sin ninguna exportación manual.

**Habilidades aplicadas:** Python · API de Google Search Console · Google Cloud (cuentas de servicio) · PostgreSQL · SQL (UPSERT con ON CONFLICT, restricciones UNIQUE, information_schema) · manejo seguro de credenciales · resolución de problemas de entorno