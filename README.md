# Observatorio SEO

**A weekly SEO monitor for small sites: Google Search Console → PostgreSQL → SQL findings → an AI-written email with up to three next steps.**

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Neon-4169E1?logo=postgresql&logoColor=white)
![Claude](https://img.shields.io/badge/Claude-Sonnet_5.5-D97757?logo=anthropic&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-dashboard-FF4B4B?logo=streamlit&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-weekly_cron-2088FF?logo=githubactions&logoColor=white)

Every Monday a GitHub Actions job pulls the week's Search Console data into PostgreSQL. SQL works out what changed: pages gaining and losing clicks, searches with many impressions and almost no clicks, new queries. An AI agent turns those findings into a short email: what happened, why it matters and up to three next steps, each labeled with who should do it (the agent, the agent with human approval, or a person).

**Status:** in production with real data for one client, a small site with a few dozen clicks a week. Results aren't measured yet: whether the recommendations move anything is [stage 5d](#roadmap). Every example in this README uses a synthetic dataset.

> Code, comments and the email are in Spanish, the client's language. Full design record (in Spanish): [`arquitectura-agente-observatorio.md`](arquitectura-agente-observatorio.md).

## Try it without credentials

```
pip install -r requirements.txt
python -m agente --demo
```

The demo builds the email from [`agente/demo.json`](agente/demo.json): a fictional physiotherapy clinic, with the rows the SQL queries return for a real week (same columns: clicks, impressions, position, pages). It runs the same code as production from there on: thresholds, finding IDs, text formatting and the email layout. It needs no database, no API key and sends nothing.

Two things it doesn't do: it doesn't run the SQL (that needs Postgres), and it doesn't call Claude. The "Qué pasó", "Qué haría" and "Ojo" text below is a fixed sample response stored in `demo.json`, validated against the same Pydantic schema the model's output goes through.

```
Observatorio SEO · Semana 10/10 – 16/10

Los números
- 34 clics (-7) · 1.480 impresiones (+178) · CTR 2,3 % (antes 3,1 %) · posición 6,2 (antes 6,0)

Qué pasó
- La semana cerró con menos clics aunque el sitio apareció más veces en Google, por eso bajó el porcentaje de clics sobre impresiones. La caída se concentra en dos notas del blog, sobre todo la de ejercicios para la lumbalgia, y la home compensó en parte. Importa porque esas notas son las que traen gente que todavía no conoce el consultorio.

Los datos de la semana
- /blog/ejercicios-para-lumbalgia baja de 14 a 6 clics
- /blog/esguince-de-tobillo-cuando-volver-a-correr baja de 6 a 2 clics
- / (home) sube de 12 a 15 clics
- "physiotherapy near me" → / (home): 140 impresiones y 0 clics en 28 días, posición 1,6
- "ejercicios lumbalgia" → /blog/ejercicios-para-lumbalgia: 96 impresiones y 1 clic en 28 días, posición 8,4
- "cuanto dura la rehabilitacion de lca" → /blog/cuanto-dura-la-rehabilitacion-de-lca: 41 impresiones y 0 clics en 28 días, posición 11,2
- Consulta nueva: "kinesiologo deportivo zona norte" (12 impresiones, 0 clics)
- Consulta nueva: "dolor de rodilla al subir escaleras" (7 impresiones, 1 clic)
- Consultas visibles (sin las anónimas) · marca: 4 clics y 18 impresiones (antes 5 y 21) · sin marca: 6 clics y 402 impresiones (antes 7 y 355)

Qué haría
- 🤝 Reescribir el title y la meta description de /blog/ejercicios-para-lumbalgia para que respondan directo a lo que se busca y digan qué va a encontrar la persona al entrar. El agente prepara dos o tres opciones y una persona del consultorio elige.
  Es la nota que más clics perdió y además aparece seguido para esa búsqueda sin que casi nadie entre. Eso apunta más a un título que no convence que a un problema de posición.
  Dato: /blog/ejercicios-para-lumbalgia baja de 14 a 6 clics
- 👤 Sumar a la página de servicios una sección sobre kinesiología deportiva, escrita por un profesional del consultorio.
  Es una búsqueda nueva de alguien que todavía no eligió dónde atenderse, y hoy el sitio no tiene una página que le responda directamente.
  Dato: Consulta nueva: "kinesiologo deportivo zona norte" (12 impresiones, 0 clics)
- 🤖 Seguir midiendo /blog/esguince-de-tobillo-cuando-volver-a-correr la próxima semana y avisar si sigue bajando, antes de tocar el contenido.
  Partía de pocos clics, así que la baja puede ser una oscilación normal. Conviene confirmarla antes de invertir tiempo en reescribirla.
  Dato: /blog/esguince-de-tobillo-cuando-volver-a-correr baja de 6 a 2 clics
- 🤖 lo hace el agente · 🤝 el agente lo prepara y vos lo aprobás · 👤 lo hacés vos

Ojo
- Las dos notas que bajaron partían de pocos clics: parte de la caída puede ser variación normal y no pérdida de posiciones.
- Parte de la suba de impresiones viene de búsquedas en inglés que llegan a la home y no hacen clic; eso baja el porcentaje de clics sin que sea un problema de las páginas.
```

What the dataset is built to show: every number in the email comes from the rows, not from the AI text. `/turnos` (−1 click), `/blog/cuanto-dura-la-rehabilitacion-de-lca` (+2) and the new query "turno kinesiologia sabado" (3 impressions) are in the data but fall below the thresholds, so they aren't reported. Each recommendation ends with the finding it's based on.

## Architecture

```
Search Console API
       │   GitHub Actions, every Monday 09:00 UTC
       ▼
cargar_datos_api.py ──────────►  Neon PostgreSQL  ◄──────────  app.py
(ingestion, 3 API cuts)          data tables + views           Streamlit dashboard
                                 diagnosticos                  (read-only role)
                                     │      ▲
                         reads data  ▼      │  saves the diagnosis
                                 python -m agente   (runs only if ingestion succeeded)
                                 detectar.py   → SQL findings, each with an ID
                                 estratega.py  → Claude Sonnet, validated JSON
                                 mail.py       → weekly email via Resend
```

## Design decisions

### 26 clicks vs. 96: the API drops anonymized queries

The first dashboard showed 26 clicks for a period where the Search Console panel showed 96. The property type was fine (domain property). The cause: when a request includes the `query` dimension, the API silently omits anonymized queries, which on this site are about 70 % of clicks.

Ingestion now makes three requests per run and stores each in its own table:

| Table | API dimensions | Use |
|---|---|---|
| `totales_diarios` | `date` | Totals. Matches the panel. |
| `rendimiento_paginas` | `date`, `page` | Pages. Clicks match; impressions are ~1 % higher, because the API counts them per page. |
| `rendimiento_api` | `date`, `query`, `page` | Queries only, knowing it covers the visible ones. |

Totals and page tables now match the panel. With the old data the pages table showed the opposite of what was happening: one page dropping from 2 clicks to 0, while four blog posts were actually going up. Query-based findings in the email are labeled "consultas visibles (sin las anónimas)", and the model's instructions say not to draw site-wide conclusions from them.

### SQL computes, the AI interprets

- Every number in the email comes from SQL. The model never writes quantities: it returns fixed-shape JSON (validated with Pydantic) and points each recommendation to a finding ID.
- A recommendation citing an ID that doesn't exist is dropped, and there are never more than three.
- The model's instructions live in [`agente/reglas_seo.md`](agente/reglas_seo.md). A hash of that file is stored with every diagnosis as the prompt version.
- One Sonnet call over findings already computed in SQL, rather than a chain of models: a cheaper first pass added nothing on top of clean JSON.

### Honest statistics at low volume

At a few dozen clicks a week, one click is ±100 %. The pipeline is built not to report noise as news:

- **Thresholds.** A page has to move at least 3 clicks week over week, and a new query needs at least 5 impressions, to be reported. Calibrated on the real client's volume (`agente/config.py`).
- **Before and after, not just the delta.** "baja de 6 a 2 clics" rather than "−67 %".
- **Windows end on the last loaded day** (`MAX(fecha)`), not today. Search Console lags 2–3 days; with windows ending today, the current week had 5 days of data against 7 and an unchanged site showed a fake 29 % drop.
- **Incomplete window** (fewer than 14 days of data): no comparison and no AI call. The email goes out with the numbers and a warning.
- **URL variants are merged** (`www`, `http`/`https`, trailing `/`) in views, at query time. Otherwise one page's clicks split across variants look like rises and drops.
- **CTR and position are recomputed, never averaged.** CTR = `SUM(clics) / SUM(impresiones)`; position weighted by impressions.
- **The "Ojo" section only covers this week.** In the first dry run it restated the general caveats (anonymized queries, Search Console lag). They'd repeat every Monday and the reader would learn to skip the section, so the instructions now limit it to what changes the reading of that particular week, three at most.

### Least privilege

Each component has its own Postgres role:

| Role | Can read | Can write |
|---|---|---|
| owner (schema and ingestion) | everything | everything |
| `dashboard_ro` | `totales_diarios`, `v_rendimiento_paginas` | nothing |
| `agente_rw` | `totales_diarios`, `v_rendimiento_paginas`, `v_rendimiento` | `diagnosticos` (insert, update; no delete) |

Roles are created with SQL, not from the Neon console: console-created roles inherit `neon_superuser`, which can read and write everything. I checked that `dashboard_ro` can't write, create tables or read any other object. GitHub Actions runs with `contents: read`, and the agent job gets the `agente_rw` connection, not the owner's.

### Fallbacks and idempotency

- If the AI fails or returns invalid JSON, the email goes out with the numbers alone and a note saying so.
- If the email fails, the diagnosis is already saved. The next run resends what's stored, without calling the AI again.
- `UNIQUE (cliente, ventana_fin)` on `diagnosticos` plus an `enviado` flag and a Resend idempotency key: running twice on the same Monday doesn't duplicate the row or the email.
- The agent job only runs if ingestion succeeded (`needs: ingesta`).
- Everything from the AI or from search queries is HTML-escaped in the email: anyone can type anything into Google.

## Tests

No database, no LLM and no email API needed. Each runs as a plain script:

```
python test_agente.py
python test_app.py
```

`test_agente.py` mocks Postgres (a fake `diagnosticos` table that enforces the `UNIQUE` constraint), the Anthropic client and Resend, and covers:

- no data at all, and an incomplete window (no comparison, no AI call)
- low volume: changes below the thresholds aren't reported
- the AI failing, or returning invalid JSON: the email goes out with the numbers alone
- a repeated run, including a failed send that gets retried without calling the AI again
- a recommendation citing a finding that doesn't exist
- HTML escaping of search queries
- the demo running end to end

`test_app.py` mocks the dashboard's connection: an empty table, the database being down, days without rows (filled with 0) and the order of the pages going up and down.

Not covered: the SQL itself runs against Postgres and has no automated test. The window and URL-merging fixes were checked on a temporary database with synthetic data.

## Running it on a real site

1. Install the dependencies: `pip install -r requirements.txt`
2. Create a Google Cloud service account, enable the Search Console API, download its key as `credenciales.json` and add the account's email as a user on the Search Console property. Set the property in `SITIO` (`cargar_datos_api.py`).
3. Copy `.env.example` to `.env` and fill in `DATABASE_URL` (in Neon: *Connection string*).
4. Create the tables and views (safe to run again): `python crear_tablas.py`
5. Load the data: `python cargar_datos_api.py`
6. Dashboard. Create the read-only role once:
   ```sql
   CREATE ROLE dashboard_ro WITH LOGIN PASSWORD 'a-long-password';
   GRANT CONNECT ON DATABASE neondb TO dashboard_ro;
   GRANT USAGE ON SCHEMA public TO dashboard_ro;
   GRANT SELECT ON totales_diarios, v_rendimiento_paginas TO dashboard_ro;
   ```
   Save its connection in `.streamlit/secrets.toml` (never committed; the `+psycopg2` is required):
   ```toml
   [connections.neon]
   url = "postgresql+psycopg2://dashboard_ro:a-long-password@HOST/neondb?sslmode=require"
   ```
   Then `streamlit run app.py`.
7. Weekly AI summary. Create the agent's role once:
   ```sql
   CREATE ROLE agente_rw WITH LOGIN PASSWORD 'another-long-password';
   GRANT CONNECT ON DATABASE neondb TO agente_rw;
   GRANT USAGE ON SCHEMA public TO agente_rw;
   GRANT SELECT ON totales_diarios, v_rendimiento_paginas, v_rendimiento TO agente_rw;
   GRANT SELECT, INSERT, UPDATE ON diagnosticos TO agente_rw;
   GRANT USAGE ON SEQUENCE diagnosticos_id_seq TO agente_rw;
   ```
   Fill in `ANTHROPIC_API_KEY`, `RESEND_API_KEY` and `MAIL_DESTINO` in `.env` (without a verified domain, Resend only sends to your own account's address), then try it without writing to the database or sending anything:
   ```
   SOLO_IMPRIMIR=1 python -m agente
   ```

To run every Monday on GitHub Actions, add these under *Settings → Secrets and variables → Actions*: `DATABASE_URL` and `GOOGLE_CREDENTIALS_JSON` (the contents of `credenciales.json`) for ingestion; `AGENTE_DATABASE_URL` (the `agente_rw` connection), `ANTHROPIC_API_KEY`, `RESEND_API_KEY` and `MAIL_DESTINO` for the agent.

Connection checks: `python probar_searchconsole.py` (API) and `python probar_db.py` (database).

## Roadmap

| Stage | What it adds | Status |
|---|---|---|
| 1 | Local PostgreSQL: Search Console CSV import and first analysis | ✅ Done |
| 2 | Ingestion straight from the Search Console API | ✅ Done |
| 3 | Cloud database (Neon) and a weekly run on GitHub Actions | ✅ Done |
| 4 | Streamlit dashboard with a read-only role | ✅ Done (runs locally) |
| 5a | Weekly AI summary: SQL findings → Claude → email | ✅ In production |
| 5b | Recommendations become tracked tasks | 🗓️ Planned |
| 5c | The agent opens pull requests on the client's site; a person reviews and merges | 🗓️ Planned |
| 5d | Results loop: each finished task measured 28 days before vs. after | 🗓️ Planned |
| 5e | Published dashboard with a tab to approve or discard tasks | 🗓️ Planned |
| 6 | GA4 conversions: leads per week, cost per lead | 🗓️ Planned |
| 7 | More than one site per pipeline | 🗓️ Planned |

Today it's one pipeline for one site. Client-specific values (the Search Console property, the brand pattern, the description in the model's instructions) are still in the code; moving them to configuration is part of stage 7.

## Problems found along the way

- **Windows blocked a library.** Smart App Control blocked the `.dll` that `psycopg` needs. Rather than turn off a system protection, I switched to a pure-Python driver for a while; the project later moved to `psycopg2-binary`, which works fine.
- **The first GitHub Actions run failed** with `FileNotFoundError: credenciales.json`: the repository secrets were still empty, so the script fell back to the local file, which is never committed on purpose.
- **Neon goes to sleep** when idle and takes a few seconds to wake up. Every connection uses `connect_timeout=30`.
- **A password one `git add .` away from being committed:** `.streamlit/secrets.toml` wasn't in `.gitignore`.
- **An empty or unreachable database broke the dashboard** (invalid date, division by zero, and a full error with the SQL and the server). It now shows a clear message and logs the details.
- **The wrong driver in SQLAlchemy 2.1:** a `postgresql://` URL defaults to `psycopg` 3. The URL now names the driver (`postgresql+psycopg2://`).
- **Testing email before paying for the AI:** a one-off send through Resend with no AI call confirmed delivery before any API credits were loaded.

## Tech stack

Python 3.12 · PostgreSQL on Neon · SQL (CTEs, views, `FULL JOIN`, `generate_series`, upserts) · Google Search Console API · GitHub Actions · Streamlit · Claude API (structured outputs with Pydantic) · Resend · pandas · SQLAlchemy · psycopg2

## Repository structure

```
observatorio_seo/
├── .github/workflows/
│   └── semanal.yml           # Every Monday: ingestion job, then the agent job
├── datos/                    # Search Console CSV exports for stage 1 (synthetic sample)
├── sql/
│   ├── 01_crear_tablas.sql   # Query and page tables (staging + final)
│   ├── 02_cargar_datos.sql   # CSV cleaning and loading
│   └── 03_analisis.sql       # Analysis queries
├── schema.sql                # API tables, views and the agent's diagnosticos table
├── crear_tablas.py           # Applies schema.sql to the database
├── cargar_datos_api.py       # Pulls the Search Console API into PostgreSQL
├── agente/                   # Weekly AI summary: python -m agente
│   ├── detectar.py           # Runs the SQL and builds the week's findings
│   ├── estratega.py          # Claude interprets the findings (validated JSON)
│   ├── reglas_seo.md         # The model's instructions: data rules and output format
│   ├── mail.py               # Builds the email and sends it with Resend
│   └── demo.json             # Synthetic week for python -m agente --demo
├── app.py                    # Streamlit dashboard
├── test_app.py               # Dashboard tests, no database needed
├── test_agente.py            # Agent tests, no database, AI or email needed
├── probar_searchconsole.py   # Search Console API connection check
├── probar_db.py              # Database connection check
├── requirements.txt          # Pinned Python dependencies
└── .env.example              # Configuration template
```
