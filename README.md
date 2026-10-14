# Observatorio SEO

Sistema de monitoreo SEO construido con datos reales de Google Search Console, PostgreSQL y Python. Proyecto de aprendizaje desarrollado por etapas a lo largo de ~6 meses, usando como caso real el sitio de Estudio Jurídico Ríos.

## Etapas del proyecto

- [x] **Etapa 1** — PostgreSQL local: carga manual de CSV de Search Console y primer análisis
- [x] **Etapa 2** — Python trae los datos solo desde la API de Search Console
- [x] **Etapa 3** — Base en la nube y ejecución semanal automática
- [x] **Etapa 4** — Dashboard con la evolución, páginas que suben y páginas que bajan
- [ ] **Etapa 5** — Capa de IA: detección de caídas con SQL y resumen semanal automático
- [ ] **Etapa 6** — Documentación final y video demo

## Estructura del repositorio

```
observatorio_seo/
├── .github/workflows/
│   └── semanal.yml           # Ingesta automática: cada lunes corre cargar_datos_api.py (Etapa 3)
├── datos/                    # Exportaciones CSV de Search Console (Etapa 1)
├── sql/
│   ├── 01_crear_tablas.sql   # Tablas de consultas y páginas (staging + finales)
│   ├── 02_cargar_datos.sql   # Limpieza y carga de los CSV
│   └── 03_analisis.sql       # Consultas de análisis
├── schema.sql                # Tablas de la API (totales_diarios, rendimiento_paginas, rendimiento_api) y sus vistas
├── crear_tablas.py           # Crea las tablas y vistas de schema.sql en la base
├── cargar_datos_api.py       # Script que trae los datos de la API a PostgreSQL
├── app.py                    # Dashboard en Streamlit (Etapa 4)
├── test_app.py               # Prueba del dashboard, sin base de datos
├── probar_searchconsole.py   # Prueba de conexión con la API de Search Console
├── probar_db.py              # Prueba de conexión con la base de datos
├── requirements.txt          # Librerías de Python necesarias (versiones fijas)
├── .env.example              # Plantilla de configuración (DATABASE_URL)
└── README.md
```

## Cómo usarlo

1. Instalar las librerías:
   ```
   pip install -r requirements.txt
   ```
2. Crear una cuenta de servicio en Google Cloud, habilitar la Google Search Console API, descargar la clave como `credenciales.json` y agregar el email de la cuenta como usuario en Search Console.
3. Copiar `.env.example` como `.env` y completar `DATABASE_URL` con la cadena de conexión a PostgreSQL (en Neon: *Connection string*).
4. Crear las tablas y las vistas (se puede repetir sin problema):
   ```
   python crear_tablas.py
   ```
5. Ejecutar:
   ```
   python cargar_datos_api.py
   ```
6. Ver el dashboard (Etapa 4). Crear una vez, en la base, un usuario de solo lectura:
   ```sql
   CREATE ROLE dashboard_ro WITH LOGIN PASSWORD 'una-clave-larga';
   GRANT CONNECT ON DATABASE neondb TO dashboard_ro;
   GRANT USAGE ON SCHEMA public TO dashboard_ro;
   GRANT SELECT ON totales_diarios, v_rendimiento_paginas TO dashboard_ro;
   ```
   Guardar su conexión en `.streamlit/secrets.toml` (no se sube al repositorio). El `+psycopg2` es necesario:
   ```toml
   [connections.neon]
   url = "postgresql+psycopg2://dashboard_ro:una-clave-larga@HOST/neondb?sslmode=require"
   ```
   Y abrirlo:
   ```
   streamlit run app.py
   ```

Para que la ingesta corra sola cada lunes (GitHub Actions), cargar `DATABASE_URL` y `GOOGLE_CREDENTIALS_JSON` (el contenido de `credenciales.json`) en *Settings → Secrets and variables → Actions*.

Para verificar cada conexión por separado: `python probar_searchconsole.py` (API) y `python probar_db.py` (base de datos). La prueba del dashboard no necesita base: `python test_app.py`.

### Notas sobre los datos

- **`rendimiento_api` suma mucho menos que el panel de Search Console; `totales_diarios` y `rendimiento_paginas` no.** Al pedir la dimensión `query`, Search Console omite las consultas anónimas, que en este sitio son ~70 % de los clics (al 9 de octubre: 26 clics por consulta contra 96 en total). Por eso los totales y las páginas se guardan con pedidos aparte, sin consulta, y coinciden con el panel. `rendimiento_api` sirve para analizar consultas, sabiendo que cubre solo las visibles. Las impresiones por página suman ~1 % más que los totales, porque la API cuenta por página; los clics coinciden.
- **Una misma página puede aparecer dos veces** (con y sin `www`), porque la propiedad es de dominio. Conviene unificarlas al consultar, no al guardar: las consultas de `sql/03_analisis.sql` leen las vistas `v_rendimiento` y `v_rendimiento_paginas`, que las unifican.
- **Las ventanas semanales terminan en `v_ventana.fin` (hoy − 3), no en hoy.** Search Console tarda 2-3 días en consolidar; si "los últimos 7 días" terminaran hoy, tendrían solo 5 días con datos contra 7 de la semana anterior y todo parecería una caída. Antes de analizar conviene correr `cargar_datos_api.py`: los días sin cargar se ven como 0.
- **El dashboard ancla su ventana al último día cargado** (`MAX(fecha)`), no a `v_ventana.fin`. Se mira cualquier día de la semana y la ingesta es semanal: con hoy − 3 la ventana actual incluiría días todavía sin cargar.
- **CTR y posición no se promedian.** Para agrupar, recalcular: CTR = `SUM(clics) / SUM(impresiones)`; posición ponderada por impresiones.

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
2. **Prueba de conexión:** escribí `probar_searchconsole.py` para confirmar el acceso antes de construir el script completo.
3. **Nueva tabla `rendimiento_api`:** a diferencia de los CSV, la API entrega los datos día por día y combinando consulta y página. Diseñé una tabla con esas tres dimensiones y una restricción `UNIQUE (fecha, consulta, pagina)`.
4. **Script de carga (`cargar_datos_api.py`):** trae los últimos 90 días de datos, dejando un margen de 3 días porque Search Console tarda en consolidar la información. Convierte el CTR de fracción (0.42) a porcentaje (42.00) para mantener el mismo formato que la Etapa 1.
5. **Carga sin duplicados:** uso `INSERT ... ON CONFLICT DO UPDATE`. Si el script corre más de una vez sobre las mismas fechas, actualiza las filas existentes en lugar de repetirlas.
6. **Protección de credenciales:** la clave de Google y la contraseña de la base viven en `credenciales.json` y `.env`, excluidos del repositorio con `.gitignore`. El repo incluye un `.env.example` como plantilla.

**Problemas que resolví**

- **Bloqueo de Windows:** el Control inteligente de aplicaciones de Windows 11 bloqueó el archivo `.dll` que necesita la librería `psycopg`. En lugar de desactivar una protección de seguridad del sistema, reemplacé la librería por `pg8000`, un conector escrito íntegramente en Python que no depende de archivos `.dll`. (Más adelante, en la Etapa 3, el proyecto pasó a `psycopg2-binary`, que es el que figura hoy en `requirements.txt` y funciona sin problema.)
- **Conflicto de nombres:** antes de crear la tabla nueva, revisé su estructura con `information_schema.columns` y detecté que ya existía una tabla `rendimiento_diario` con los datos de la Etapa 1. En lugar de reemplazarla, creé `rendimiento_api` para conservar ese registro.

**Resultado**
En una sola ejecución, el script cargó 291 filas con los datos del 4 de julio al 2 de octubre de 2026, sin ninguna exportación manual.

**Habilidades aplicadas:** Python · API de Google Search Console · Google Cloud (cuentas de servicio) · PostgreSQL · SQL (UPSERT con ON CONFLICT, restricciones UNIQUE, information_schema) · manejo seguro de credenciales · resolución de problemas de entorno

---

## Etapa 3: Base en la nube y ejecución semanal automática

**Objetivo**
Sacar el sistema de mi computadora: guardar los datos en una base PostgreSQL en la nube y traerlos de la API todas las semanas, sin intervención manual.

**Qué hice**

1. **Base en Neon:** creé un proyecto de PostgreSQL en Neon (versión 18, región São Paulo) y cambié el conector a `psycopg2-binary`. La cadena de conexión vive en la variable `DATABASE_URL`: en `.env` en mi computadora y como *Secret* en GitHub. El código no contiene ninguna contraseña.
2. **Esquema versionado:** `schema.sql` define las tablas `totales_diarios`, `rendimiento_paginas` y `rendimiento_api` (esta con `UNIQUE (fecha, consulta, pagina)` y un índice por página y fecha), más sus vistas, y `crear_tablas.py` lo aplica en la base. Se puede correr las veces que haga falta sin romper nada.
3. **El mismo script en mi computadora y en la nube:** `cargar_datos_api.py` lee la clave de Google de la variable `GOOGLE_CREDENTIALS_JSON` si existe (en GitHub Actions) y, si no, del archivo `credenciales.json`.
4. **Carga más robusta:** pide a la API tres cortes (por fecha, por fecha + página y por fecha + consulta + página) e inserta cada uno por lotes con `execute_values`, todo dentro de una sola transacción (si algo falla, no queda nada a medias). La llamada a la API reintenta sola ante errores pasajeros de Google (5xx y 429).
5. **Ejecución semanal con GitHub Actions:** `.github/workflows/semanal.yml` corre `cargar_datos_api.py` todos los lunes a las 09:00 UTC (06:00 en Argentina) y tiene un botón *Run workflow* para lanzarlo a mano. En cada corrida trae los últimos 10 días (`DIAS_ATRAS=10`): Search Console corrige los días recientes más tarde, y el `ON CONFLICT DO UPDATE` pisa los valores viejos sin duplicar. Usa permisos mínimos (`contents: read`) y un límite de 15 minutos.
6. **Consultas de análisis sobre la API:** en `sql/03_analisis.sql` escribí las consultas 5 a 12: evolución diaria, tráfico de marca vs. sin marca, páginas que suben y bajan, posición por página, oportunidades de CTR, consultas nuevas y comparación contra la semana anterior.

**Problemas que resolví**

- **Neon se duerme:** la base se suspende cuando no se usa y tarda unos segundos en despertar. Todas las conexiones usan `connect_timeout=30` para esperar en lugar de fallar.
- **Primera corrida en GitHub fallida:** el primer intento manual (9 de octubre) terminó con `FileNotFoundError: credenciales.json`. Los Secrets del repositorio todavía estaban vacíos, así que el script buscó el archivo local, que a propósito no se sube. Cargué `DATABASE_URL` y `GOOGLE_CREDENTIALS_JSON` y las dos corridas siguientes salieron bien.
- **Ventanas que no coincidían con la ingesta:** "los últimos 7 días" terminaban en hoy, pero la ingesta llega hasta hoy − 3. La semana actual tenía 5 días con datos contra 7 de la anterior, y un sitio sin cambios aparecía con una caída falsa de ~29 %. Ahora las ventanas terminan en el último día con datos completos (`v_ventana.fin`).
- **Una misma página con varias URLs:** con y sin `www`, `http` y `https`, con y sin `/` final. Los clics se repartían entre variantes y parecían subidas o caídas. La vista `v_rendimiento` las unifica al consultar, sin tocar lo que se guarda.
- **Días sin filas que desaparecían:** la evolución diaria salteaba los días sin datos. Con `generate_series` ahora aparecen con 0.

Probé estos tres últimos arreglos en una base temporal con datos sintéticos.

**Resultado**
El lunes 12 de octubre de 2026 el workflow se ejecutó solo y dejó los datos al día en Neon (GitHub lo lanzó unas horas después de la hora programada, algo normal en los cron de Actions). En esa corrida, `rendimiento_api` quedó con 409 filas, del 24 de agosto al 9 de octubre de 2026.

**Habilidades aplicadas:** PostgreSQL en la nube (Neon) · GitHub Actions (cron, Secrets) · Python (psycopg2, `execute_values`, reintentos) · SQL (vistas, `generate_series`, ventanas de tiempo) · variables de entorno y manejo de credenciales · diagnóstico a partir de logs de CI

---

## Etapa 4: Dashboard con la evolución y las páginas que suben y bajan

**Objetivo**
Mostrar los datos de Neon en un tablero que se entienda de un vistazo, sin tener que correr consultas SQL.

**Qué hice**

1. **Dashboard en Streamlit (`app.py`):** una página que lee Neon y muestra los cuatro números del período (clics, impresiones, CTR y posición media), la evolución diaria con un selector de impresiones o clics, y dos tablas: páginas que suben y páginas que bajan.
2. **Cuentas correctas al agrupar:** el CTR se recalcula como clics / impresiones y la posición media se pondera por impresiones, como hace Search Console, en lugar de promediar promedios.
3. **Páginas que suben y bajan:** compara los últimos 7 días con datos contra los 7 anteriores, con las URLs unificadas (`v_rendimiento_paginas`). Muestra los clics de antes y de ahora, no solo la diferencia: con pocos clics, 1 de diferencia ya es ±100 %. La ventana termina en el último día cargado y no en hoy − 3, porque el dashboard se mira cualquier día de la semana y la ingesta es semanal: con hoy − 3 la ventana actual incluiría días todavía sin cargar.
4. **Usuario de solo lectura:** el dashboard se conecta con un rol propio, `dashboard_ro`, que solo puede hacer `SELECT` en `totales_diarios` y `v_rendimiento_paginas`. No usa la contraseña de dueño de la ingesta: si se filtrara, no podría borrar ni modificar nada. Comprobé que no puede escribir, crear tablas ni leer otras tablas o vistas.
5. **Credenciales fuera del código:** la URL del rol vive en `.streamlit/secrets.toml`, excluido del repositorio con `.gitignore`.
6. **Caché de 1 hora:** el dashboard no consulta la base en cada clic. Así Neon puede dormirse y se cuida el cómputo del plan gratuito.
7. **Una prueba sin base de datos** (`test_app.py`): simula la conexión y comprueba los casos clave: tabla vacía, caída de la base, días sin filas y el orden de las páginas que suben y bajan.

**Problemas que resolví**
Antes de dar la etapa por cerrada revisé el código y la arquitectura, y corregí:

- **Dependencias faltantes:** `streamlit` y `sqlalchemy` no estaban en `requirements.txt`, así que la app no arrancaba en una instalación nueva.
- **Una contraseña a un `git add .` de subirse:** `.streamlit/secrets.toml` no estaba en `.gitignore`.
- **Base vacía o caída:** con la tabla vacía la página se rompía (fecha inválida y división por cero), y una caída de la base mostraba el error completo, con el SQL y el servidor. Ahora muestra un mensaje claro y el detalle queda en el log.
- **Días sin datos que el gráfico saltaba:** unía los puntos vecinos con una línea, como si no faltara nada. Ahora esos días se rellenan con 0.
- **Los números no coincidían con Search Console:** el dashboard mostraba 26 clics y 958 impresiones contra 96 y 3,2 mil del panel. Descarté que fuera el `siteUrl` (ya era la propiedad de dominio): al pedir la consulta, la API descarta las consultas anónimas, que en este sitio son ~70 % de los clics. Ahora la ingesta pide también los totales por fecha y por fecha + página, que sí las incluyen, y de ahí salen los números y las tablas: coinciden con el panel. Con los datos anteriores, además, la tabla de páginas mostraba lo contrario de la realidad: una caída de 2 clics a 0 cuando en verdad cuatro páginas del blog subían.
- **Conector equivocado en SQLAlchemy 2.1:** al correr la app contra Neon vi que una URL `postgresql://` usa por defecto `psycopg` 3, y el proyecto usa `psycopg2`. Declaré el driver en la URL (`postgresql+psycopg2://`).

**Resultado**
Al 9 de octubre de 2026 los números coinciden con el panel de Search Console: 96 clics, 3.199 impresiones, CTR de 3,0 % y posición media de 3,8. Con los datos hasta el 11 de octubre, el dashboard muestra 98 clics, 3.327 impresiones, CTR de 2,9 % y posición de 3,9. En la última semana cuatro páginas del blog subieron (la que más, de 0 a 9 clics) y la principal bajó de 3 a 2. Por ahora corre en mi computadora (`streamlit run app.py`); lo voy a publicar al terminar todas las etapas.

**Habilidades aplicadas:** Streamlit · Python (pandas, SQLAlchemy) · SQL (CTE, `FULL JOIN`, ventanas de tiempo) · roles y permisos en PostgreSQL (mínimo privilegio) · manejo de secretos · pruebas con conexión simulada · revisión de código y de arquitectura
