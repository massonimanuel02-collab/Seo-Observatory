# Arquitectura del Agente de Marketing sobre Observatorio SEO (desde la Etapa 5)

> Repo base: `massonimanuel02-collab/Observatorio-Seo`
> Caso real: un cliente, propiedad de dominio de Search Console
> Estado: **Aprobada** (ver ADR-001 al final)
> Última actualización: 26/10/2026

---

## 0. Punto de partida (Etapas 1–4, ya hechas)

| Pieza | Archivo | Qué hace |
|---|---|---|
| Ingesta | `cargar_datos_api.py` | Search Console → Neon (3 cortes, upsert, reintentos) |
| Reloj | `.github/workflows/semanal.yml` | Corre la ingesta cada lunes 09:00 UTC |
| Memoria | `schema.sql` (Neon) | `totales_diarios`, `rendimiento_paginas`, `rendimiento_api` + vistas |
| Análisis | `sql/03_analisis.sql` | Caídas/subidas, CTR, consultas nuevas, marca vs. sin marca |
| Dashboard | `app.py` (Streamlit) | KPIs y páginas que suben/bajan, rol `dashboard_ro` |

### Reglas de datos que el agente DEBE respetar (van a `agente/reglas_seo.md`)

1. `rendimiento_api` omite las consultas anónimas (~70 % de los clics). Totales y páginas salen de `totales_diarios` y `rendimiento_paginas`.
2. Search Console tarda 2–3 días: las ventanas terminan en el último día cargado, nunca en hoy.
3. Misma página con y sin `www`, `http/https` y `/` final: usar las vistas `v_rendimiento*`.
4. CTR y posición **no se promedian**: CTR = clics / impresiones; posición ponderada por impresiones.
5. Poco volumen: 1 clic de diferencia = ±100 %. No reportar cambios por debajo del umbral mínimo.

---

## 1. Principios de diseño

1. **SQL calcula, la IA interpreta.** El modelo nunca hace cuentas ni escribe números: los números del mail/dashboard salen siempre de SQL.
2. **Salida estructurada.** El modelo devuelve un JSON con forma fija (validado), nunca HTML ni texto libre que se publique directo.
3. **Siempre hay respaldo.** Si falla la IA → sale igual el mail con los números. Si falla el mail → queda guardado en Neon.
4. **Humano en el loop** para todo lo que cambie algo afuera (sitio, anuncios, plata).
5. **Mínimo privilegio.** Cada pieza tiene su propio rol de base de datos y sus propios secrets.
6. **Idempotente.** Correr dos veces el mismo lunes no duplica nada ni manda dos mails.
7. **Todo queda registrado** (modelo, versión de prompt, resultado): ese historial es el moat.

---

## 2. Diagrama general (modelo final)

```
                    ┌──────────────────────── GitHub Actions (cron lunes) ─────────────────────────┐
                    │                                                                               │
  Search Console ──►│ job: ingesta ──► job: agente (needs: ingesta) ──► job: resultados (Etapa 5d) │
  GA4 (Etapa 6)  ──►│                                                                               │
                    └───────────────┬───────────────────────┬──────────────────────────────────────┘
                                    │                       │
                                    ▼                       ▼
                    ┌───────────────────────────┐   ┌──────────────────────┐
                    │      Neon (Postgres)      │   │   API de Claude      │
                    │ datos · diagnosticos ·    │   │ Sonnet: estratega    │
                    │ tareas · resultados ·     │   │ Haiku: lector (Et.6) │
                    │ estado LangGraph · clientes│  └──────────────────────┘
                    └───────┬───────────┬───────┘
                            │           │
              ┌─────────────┘           └──────────────┐
              ▼                                        ▼
   ┌─────────────────────┐                ┌───────────────────────────────┐
   │ Resend → mail semanal│               │ Dashboard Streamlit (publicado)│
   └─────────────────────┘                │ KPIs · Agente · Finanzas       │
                                          └───────────────────────────────┘
              ┌──────────────────────────────────────────────┐
              │ Repo del sitio del cliente (Etapa 5c)        │
              │ El agente abre PR → Manuuu revisa → merge →  │
              │ Vercel publica                               │
              └──────────────────────────────────────────────┘
```

---

## 3. Estructura del repo (modelo final)

```
observatorio-seo/
├── cargar_datos_api.py            # (existe) ingesta Search Console
├── cargar_ga4.py                  # 🆕 Etapa 6: ingesta de conversiones GA4
├── schema.sql                     # (existe) + tablas del agente
├── agente/                        # 🆕
│   ├── __main__.py                # punto de entrada: python -m agente
│   ├── config.py                  # modelos, umbrales, cliente activo (desde env)
│   ├── reglas_seo.md              # reglas de datos (sección 0) = instrucciones del modelo
│   ├── detectar.py                # corre SQL y arma el JSON de hallazgos (con IDs)
│   ├── estratega.py               # Sonnet: diagnóstico + recomendaciones + JEV (JSON)
│   ├── lector.py                  # Etapa 6: Haiku para datos desordenados
│   ├── grafo.py                   # Etapa 5b: LangGraph (estado en Neon)
│   ├── acciones.py                # Etapa 5c: abre PRs en el repo del sitio
│   ├── resultados.py              # Etapa 5d: mide tareas hechas a las 4 semanas
│   └── mail.py                    # plantilla HTML + Resend
├── app.py                         # (existe) + pestañas "Agente" y "Finanzas"
├── test_app.py                    # (existe)
├── test_agente.py                 # 🆕
└── .github/workflows/semanal.yml  # (existe) + jobs agente y resultados
```

---

## 4. Etapas

### Etapa 5a — Resumen semanal con IA (FASE 1, la próxima)

**Objetivo:** cada lunes llega un mail con números, diagnóstico y hasta 3 recomendaciones etiquetadas 🤖 / 🤝 / 👤.

**Flujo:**
```
detectar.py (SQL) → estratega.py (Sonnet, salida JSON) → diagnosticos (Neon) → mail.py (Resend)
```

**detectar.py** devuelve hallazgos con ID:
- Totales semana actual vs. anterior (`totales_diarios`)
- Páginas que suben/bajan (consulta 8) — filtrado por umbral mínimo de clics
- Oportunidades de CTR (consulta 10)
- Consultas nuevas (consulta 11)
- Marca vs. sin marca (consulta 6)
- Ventana: `MAX(fecha)` de `totales_diarios`; exige 14 días con datos o avisa "ventana incompleta"

**Salida del modelo (forma fija):**
```json
{
  "diagnostico": "Texto corto de qué pasó y por qué importa",
  "recomendaciones": [
    { "hallazgo_id": 3, "accion": "Reescribir el title de /blog/ejercicios-para-lumbalgia", "jev": "hibrido", "motivo": "Aparece seguido y casi nadie entra" }
  ],
  "advertencias": ["Con este volumen, ±2 clics no es tendencia"]
}
```
`jev` ∈ `agente` | `hibrido` | `persona`. Máximo 3 recomendaciones.

**Tabla nueva:**
```sql
CREATE TABLE IF NOT EXISTS diagnosticos (
    id              SERIAL PRIMARY KEY,
    cliente         TEXT NOT NULL,
    ventana_fin     DATE NOT NULL,
    hallazgos       JSONB NOT NULL,      -- lo que calculó SQL
    respuesta_ia    JSONB,               -- NULL si falló la IA
    modelo          TEXT,
    version_prompt  TEXT,
    enviado         BOOLEAN NOT NULL DEFAULT FALSE,
    creado          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (cliente, ventana_fin)        -- no duplica si el workflow corre dos veces
);
```

**Mail (ejemplo):**
> **Asunto:** Observatorio SEO · Semana 13/10 – 19/10
> **Los números:** 34 clics (+6) · 1.120 impresiones · CTR 3,0 % · Posición 3,8
> **Qué pasó:** 2 páginas del blog suben; la home baja de 12 a 9 clics. Consulta nueva sin marca: "kinesiologo deportivo zona norte".
> **Qué haría:**
> 🤝 Reescribir el title de /blog/ejercicios-para-lumbalgia
> 👤 Pedir reseñas en Google Business Profile
> 🤖 Seguir "kinesiologo deportivo zona norte" la próxima semana
> *Ojo: con este volumen, ±2 clics no es tendencia.*

**Manejo de fallas:**
| Falla | Qué pasa |
|---|---|
| Ingesta falla | El job `agente` no corre (`needs: ingesta`) |
| Ventana incompleta | El mail sale con aviso, sin comparar |
| IA falla | Mail con los números solos; `respuesta_ia = NULL` |
| Resend falla | Queda `enviado = FALSE`; se reintenta en la próxima corrida manual |
| Corrida repetida | `UNIQUE` + `enviado` evitan mail duplicado |

**Modo prueba:** `SOLO_IMPRIMIR=1 python -m agente` muestra el mail en pantalla sin enviarlo ni llamar a Resend.

**Dependencias nuevas:** `langchain-anthropic`, `resend` (versiones fijas en `requirements.txt`).

---

### Etapa 5b — JEV + tareas + LangGraph

**Objetivo:** cada recomendación se vuelve una tarea con estado, y el agente recuerda en qué quedó.

- Se suma `langgraph` con checkpointer en Postgres (Neon).
- Grafo: `detectar → diagnosticar → clasificar_jev → planificar → guardar_tareas → notificar`.
- Clasificación JEV con 5 criterios (puntaje 1–5 cada uno):

| Criterio | Pregunta |
|---|---|
| Repetitiva | ¿Se hace igual muchas veces? |
| Datos disponibles | ¿El agente tiene la info necesaria? |
| Riesgo | ¿Cuánto cuesta un error? |
| Juicio humano | ¿Necesita creatividad, relación o negociación? |
| ROI de automatizar | ¿Ahorra tiempo o plata de verdad? |

```sql
CREATE TABLE IF NOT EXISTS tareas (
    id              SERIAL PRIMARY KEY,
    diagnostico_id  INTEGER REFERENCES diagnosticos(id),
    cliente         TEXT NOT NULL,
    pagina          TEXT,
    tipo            TEXT NOT NULL,   -- title_meta, contenido_nuevo, gbp, enlazado, etc.
    descripcion     TEXT NOT NULL,
    jev             TEXT NOT NULL CHECK (jev IN ('agente','hibrido','persona')),
    puntaje_jev     JSONB,
    estado          TEXT NOT NULL DEFAULT 'propuesta'
                    CHECK (estado IN ('propuesta','aprobada','en_curso','hecha','descartada')),
    fecha_hecha     DATE,
    creado          TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

### Etapa 5c — Acciones con Pull Request (requiere permiso, hoy NO activo)

**Objetivo:** el agente propone cambios concretos en el sitio y vos aprobás con un merge.

- Solo tareas `hibrido` de tipo `title_meta` (al principio).
- `acciones.py` crea una rama en el repo del sitio, edita el HTML y abre un PR con el antes/después y el motivo (datos de SQL).
- Merge = aprobación → Vercel publica → la tarea pasa a `hecha` con `fecha_hecha`.
- Token de GitHub con permiso **solo** sobre ese repo (fine-grained token), guardado como secret.
- Nunca hace merge solo.

---

### Etapa 5d — Ciclo de resultados (el moat)

**Objetivo:** saber qué acciones funcionan.

- Job `resultados` semanal: para cada tarea `hecha` hace 28 días, compara clics/impresiones/CTR/posición de esa página 28 días antes vs. 28 días después.
- El resultado alimenta el prompt del estratega ("en este sitio, cambiar titles subió el CTR un X % en promedio").

```sql
CREATE TABLE IF NOT EXISTS resultados (
    tarea_id        INTEGER PRIMARY KEY REFERENCES tareas(id),
    antes           JSONB NOT NULL,   -- métricas 28 días antes
    despues         JSONB NOT NULL,   -- métricas 28 días después
    veredicto       TEXT CHECK (veredicto IN ('mejoro','igual','empeoro','sin_datos')),
    medido          DATE NOT NULL DEFAULT CURRENT_DATE
);
```

---

### Etapa 5e — Dashboard publicado

- Publicar `app.py` en **Streamlit Community Cloud** (Streamlit no corre en Vercel).
- Pestaña **Agente**: último diagnóstico, tareas por estado, botón Aprobar/Descartar (requiere un rol con `UPDATE` solo sobre `tareas.estado`).
- Pestaña **Resultados**: tabla de `resultados` con veredictos.
- Si algún día se quiere en Vercel: reescribir en Next.js (fuera de alcance por ahora).

---

### Etapa 6 — GA4 (conversiones) + Finanzas

**Objetivo:** medir consultas reales, no solo clics, y calcular ROI.

- `cargar_ga4.py`: API de GA4 (Data API) con la misma cuenta de servicio → tabla `conversiones_diarias (fecha, canal, pagina, evento, cantidad)`. Las conversiones ya están configuradas en GA4.
- **Acá entra Haiku** (`lector.py`): normaliza eventos y nombres de páginas desordenados antes de que llegue a SQL/Sonnet.
- Tabla `finanzas (fecha, cliente, concepto, tipo ['gasto','ingreso'], monto, moneda)`: hosting, horas, honorarios.
- Métricas nuevas: consultas por semana, tasa de conversión orgánica, costo por consulta, ROI.
- Ojo Argentina: guardar moneda y, si hay pesos, tipo de cambio del día para no comparar montos nominales.

---

### Etapa 7 — Multi-cliente

- Hoy `SITIO` está fijo en `cargar_datos_api.py`. Pasa a una tabla `clientes (id, nombre, sitio_gsc, ga4_property, mail_destino, repo_sitio, activo)`.
- Todas las tablas suman la columna `cliente` (las del agente ya la traen desde 5a).
- El workflow recorre los clientes activos (matrix de GitHub Actions o un loop en Python).
- Resend con **dominio verificado** para mandar mails a clientes.
- Si GitHub Actions queda chico (webhooks, tiempo real, muchos clientes): mover el cerebro a un contenedor en Cloud Run / Railway.

---

## 5. Modelos (roles y evolución)

| Rol | Modelo | Desde | Para qué |
|---|---|---|---|
| Lector (detector) | **SQL** | 5a | Calcula todo. Gratis y exacto. |
| Estratega | `claude-sonnet-5-5` | 5a | Diagnóstico, JEV, plan (salida JSON validada) |
| Lector IA | `claude-haiku-5-5` | 6 | Normalizar datos desordenados (GA4, contenido, SERPs) |
| Estratega pesado (opcional) | `claude-opus-5-5` | 7 | Diagnósticos complejos multi-canal |

Los nombres de modelo van en variables de entorno (`MODELO_ESTRATEGA`, `MODELO_LECTOR`), no fijos en el código.

---

## 6. Despliegue

| Pieza | Dónde |
|---|---|
| Reloj | GitHub Actions (cron lunes + botón manual) |
| Cerebro | GitHub Actions (5a–6) → Cloud Run / Railway (7, si hace falta) |
| Memoria y estado | Neon (Postgres) |
| Mail | Resend |
| Dashboard | Streamlit Community Cloud |
| Monitoreo (recomendado desde 5b) | LangSmith |

**Esqueleto del workflow:**
```yaml
jobs:
  ingesta:
    # (lo que ya existe)
  agente:
    needs: ingesta
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12", cache: pip }
      - run: pip install -r requirements.txt
      - run: python -m agente
        env:
          DATABASE_URL: ${{ secrets.AGENTE_DATABASE_URL }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          RESEND_API_KEY: ${{ secrets.RESEND_API_KEY }}
          MAIL_DESTINO: ${{ secrets.MAIL_DESTINO }}
```

---

## 7. Seguridad y secrets

| Secret | Etapa | Dónde |
|---|---|---|
| `DATABASE_URL` (dueño, ingesta) | existe | GitHub Actions |
| `GOOGLE_CREDENTIALS_JSON` | existe | GitHub Actions |
| `AGENTE_DATABASE_URL` (rol `agente_rw`) | 5a | GitHub Actions |
| `ANTHROPIC_API_KEY` | 5a | GitHub Actions + `.env` local |
| `RESEND_API_KEY` | 5a | GitHub Actions + `.env` local |
| `MAIL_DESTINO` | 5a | GitHub Actions + `.env` local |
| `GITHUB_TOKEN_SITIO` (fine-grained, solo repo del sitio) | 5c | GitHub Actions |
| Conexión `dashboard_ro` / rol de aprobaciones | existe / 5e | Streamlit secrets |

**Rol del agente (mínimo privilegio):**
```sql
CREATE ROLE agente_rw WITH LOGIN PASSWORD 'una-clave-larga';
GRANT CONNECT ON DATABASE neondb TO agente_rw;
GRANT USAGE ON SCHEMA public TO agente_rw;
GRANT SELECT ON totales_diarios, rendimiento_paginas, rendimiento_api,
                v_rendimiento, v_rendimiento_paginas TO agente_rw;
GRANT SELECT, INSERT, UPDATE ON diagnosticos TO agente_rw;
GRANT USAGE ON SEQUENCE diagnosticos_id_seq TO agente_rw;
-- 5b en adelante: sumar tareas y resultados
```

`.gitignore` ya excluye `.env`, `credenciales.json` y `.streamlit/secrets.toml`.

---

## 8. Pruebas (`test_agente.py`)

Sin base ni IA reales (mocks, mismo estilo que `test_app.py`):
1. Semana sin datos → mail con aviso, sin llamar a la IA.
2. Poco volumen → cambios bajo el umbral no aparecen.
3. Ventana incompleta (< 14 días) → aviso, sin comparación.
4. IA falla o devuelve JSON inválido → mail con números solos.
5. Corrida repetida → no inserta ni envía dos veces.
6. `hallazgo_id` inexistente en la respuesta de la IA → se descarta esa recomendación.

---

## 9. Costos estimados

| Servicio | Costo |
|---|---|
| API de Claude (1 llamada/semana, JSON chico) | centavos de dólar por mes |
| GitHub Actions | gratis (repo público) |
| Neon | plan gratis |
| Resend | plan gratis |
| Streamlit Community Cloud | gratis |

---

## 10. Riesgos y cómo se mitigan

| Riesgo | Mitigación |
|---|---|
| La IA inventa números | Los números salen de SQL; la IA solo referencia `hallazgo_id` |
| Ruido por poco volumen | Umbral mínimo en SQL + advertencias en el mail |
| Cron de Actions atrasado | Ventana anclada a `MAX(fecha)`, no a la hora de corrida |
| Cambios en APIs de Google | Reintentos + pruebas de conexión (`probar_*.py`) |
| Cambio de precio/modelo de Claude | Modelo en variable de entorno; respaldo sin IA |
| Agente rompe el sitio (5c) | Solo PRs, nunca merge automático; token limitado a un repo |

---

## ADR-001 (resumen de la decisión)

**Estado:** Aprobada con cambios — 26/10/2026

**Decisión:** en la Etapa 5a se usa **una sola llamada a Sonnet con salida estructurada**, sobre hallazgos calculados en SQL, con respaldo sin IA. Haiku entra en la Etapa 6 cuando haya datos desordenados.

**Cambios respecto del plan original:**
1. Una llamada a Sonnet en vez de Haiku + Sonnet (Haiku no aportaba sobre un JSON ya limpio).
2. La IA no escribe números ni HTML: devuelve JSON validado; los números van por plantilla desde SQL.
3. El agente es un job separado con `needs: ingesta`.
4. `diagnosticos` con `UNIQUE (cliente, ventana_fin)` + `enviado` → sin duplicados.
5. Ventana anclada a `MAX(fecha)` y chequeo de 14 días con datos.
6. Se guardan `modelo` y `version_prompt` por diagnóstico.
7. (Recomendado) Rol `agente_rw` con mínimo privilegio.

---

## Checklist de la Fase 1 (Etapa 5a)

- [ ] Crear `agente/` con `__main__.py`, `config.py`, `reglas_seo.md`, `detectar.py`, `estratega.py`, `mail.py`
- [ ] Agregar tabla `diagnosticos` a `schema.sql` y correr `python crear_tablas.py`
- [ ] Crear rol `agente_rw` en Neon
- [ ] Sumar `langchain-anthropic` y `resend` a `requirements.txt`
- [ ] Agregar job `agente` (`needs: ingesta`) en `semanal.yml`
- [ ] Escribir `test_agente.py` (6 casos de la sección 8)
- [ ] Conseguir API key de Anthropic (console.anthropic.com) y de Resend
- [ ] Cargar secrets en GitHub y en `.env` local
- [ ] Probar local con `SOLO_IMPRIMIR=1 python -m agente`
- [ ] Correr a mano en Actions (botón *Run workflow*) y verificar el mail
