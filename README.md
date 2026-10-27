# SEO Observatory + AI Marketing & Finance Agent

**An end-to-end SEO monitoring pipeline with an AI marketing agent on top, built stage by stage on real Google Search Console data from a law firm in Paraná, Argentina.**

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Neon-4169E1?logo=postgresql&logoColor=white)
![Claude](https://img.shields.io/badge/Claude-Sonnet_5.5-D97757?logo=anthropic&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-dashboard-FF4B4B?logo=streamlit&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-weekly_cron-2088FF?logo=githubactions&logoColor=white)

Every Monday a GitHub Actions job pulls the week's Search Console data into PostgreSQL. SQL works out what changed: pages gaining and losing clicks, searches with many impressions and almost no clicks, new queries. An AI agent then turns those findings into a short email: what happened, why it matters and up to three next steps, each labeled with who should do it (the agent, the agent with human approval, or a person).

The client is Estudio Jurídico Ríos (`estudiojuridicorios.com.ar`), a small law firm with about 25 clicks a week. That low volume makes it a good test of whether a pipeline can tell signal from noise.

> Code, comments and the weekly email are in Spanish, the client's language. Full design and decision record (in Spanish): [`arquitectura-agente-observatorio.md`](arquitectura-agente-observatorio.md).

## Highlights

- **Numbers that match the source of truth.** The dashboard showed 26 clicks where Search Console showed 96. I traced it to the API silently dropping anonymized queries (about 70 % of clicks on this site) whenever the `query` dimension is requested, and redesigned ingestion into three API cuts. Totals now match the Search Console panel exactly (96 clicks, 3,199 impressions).
- **SQL computes, the AI interprets.** Every number in the email comes from SQL. The model returns fixed-shape JSON validated with Pydantic, and each recommendation must point to a finding ID; recommendations that cite a finding that doesn't exist are dropped.
- **There is always a fallback.** If the AI fails, the email goes out with the numbers alone. If the email fails, the diagnosis is already saved in Postgres and the next run resends it, without calling the AI again and without duplicates (`UNIQUE` constraint plus an idempotency key).
- **Least privilege.** Ingestion, dashboard and agent each use their own Postgres role. The dashboard can read two objects; the agent can read three and write to one table, and cannot delete.
- **Honest statistics at low volume.** Weekly windows end on the last loaded day (Search Console lags 2–3 days), URL variants are merged, CTR and position are recomputed instead of averaged, and changes below a threshold aren't reported: at this volume one click is ±100 %.
- **Tests without infrastructure.** The dashboard and agent tests run with the database, the LLM and the email API mocked.

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

## Sample output

Real output (three of the CTR lines trimmed) of `SOLO_IMPRIMIR=1 python -m agente` for the week of October 17–23, 2026 (a dry run: nothing is saved or sent). It ran before the Anthropic key was set up, so it shows the numbers-only fallback. With the AI on, the email adds *Qué pasó* (what happened), *Qué haría* (up to three actions labeled 🤖 / 🤝 / 👤) and *Ojo* (caveats about the data).

```
Observatorio SEO · Semana 17/10 – 23/10

Los números
- 21 clics (-12) · 1.171 impresiones (+142) · CTR 1,8 % (antes 3,2 %) · posición 5,6 (antes 5,0)

Los datos de la semana
- /blog/cuanto-tarda-un-amparo-de-salud baja de 14 a 6 clics
- /blog/oser-iosper-no-cubre-medicamento baja de 5 a 0 clics
- /blog/pami-rechazo-internacion-geriatrica baja de 4 a 0 clics
- / (home) sube de 4 a 10 clics
- "rechazo conformado pami" → /blog/pami-rechazo-internacion-geriatrica: 67 impresiones y 0 clics en 28 días, posición 10,2
- "cuanto tarda un amparo de salud" → /blog/cuanto-tarda-un-amparo-de-salud: 28 impresiones y 0 clics en 28 días, posición 6,5
- Consultas visibles (sin las anónimas) · marca: 0 clics y 7 impresiones (antes 1 y 4) · sin marca: 3 clics y 193 impresiones (antes 0 y 169)

Sin análisis
- La IA no respondió esta semana: van los números solos.
```

## Roadmap

| Stage | What it adds | Status |
|---|---|---|
| 1 | Local PostgreSQL: manual Search Console CSV import and first analysis | ✅ Done |
| 2 | Python ingestion straight from the Search Console API | ✅ Done |
| 3 | Cloud database (Neon) and a weekly automatic run on GitHub Actions | ✅ Done |
| 4 | Streamlit dashboard: trend, pages going up and down, read-only role | ✅ Done |
| 5a | Weekly AI summary: SQL findings → Claude → email | 🚧 Built and tested; going live once its API keys are set |
| 5b | Recommendations become tracked tasks; agent state in LangGraph | 🗓️ Planned |
| 5c | The agent opens pull requests on the client's site; a person reviews and merges | 🗓️ Planned |
| 5d | Results loop: each finished task measured 28 days before vs. after | 🗓️ Planned |
| 5e | Published dashboard with an agent tab to approve or discard tasks | 🗓️ Planned |
| 6 | GA4 conversions and **finance**: leads per week, cost per lead, ROI | 🗓️ Planned |
| 7 | Multi-client: one pipeline, many sites | 🗓️ Planned |

## Tech stack

Python 3.12 · PostgreSQL on Neon · SQL (CTEs, views, `FULL JOIN`, `generate_series`, upserts) · Google Search Console API · GitHub Actions · Streamlit · Claude API (structured outputs with Pydantic) · Resend · pandas · SQLAlchemy · psycopg2

## Repository structure

```
observatorio_seo/
├── .github/workflows/
│   └── semanal.yml           # Every Monday: ingestion job, then the agent job
├── datos/                    # Search Console CSV exports (Stage 1)
├── sql/
│   ├── 01_crear_tablas.sql   # Query and page tables (staging + final)
│   ├── 02_cargar_datos.sql   # CSV cleaning and loading
│   └── 03_analisis.sql       # Analysis queries
├── schema.sql                # API tables, views and the agent's diagnosticos table
├── crear_tablas.py           # Applies schema.sql to the database
├── cargar_datos_api.py       # Pulls the Search Console API into PostgreSQL
├── agente/                   # Weekly AI summary (Stage 5a): python -m agente
│   ├── detectar.py           # Runs the SQL and builds the week's findings
│   ├── estratega.py          # Claude interprets the findings (validated JSON)
│   ├── reglas_seo.md         # The model's instructions: data rules and output format
│   └── mail.py               # Builds the email and sends it with Resend
├── app.py                    # Streamlit dashboard (Stage 4)
├── test_app.py               # Dashboard tests, no database needed
├── test_agente.py            # Agent tests, no database, AI or email needed
├── probar_searchconsole.py   # Search Console API connection check
├── probar_db.py              # Database connection check
├── requirements.txt          # Pinned Python dependencies
├── .env.example              # Configuration template
└── README.md
```

## Getting started

1. Install the dependencies:
   ```
   pip install -r requirements.txt
   ```
2. Create a Google Cloud service account, enable the Google Search Console API, download its key as `credenciales.json` and add the account's email as a user in Search Console.
3. Copy `.env.example` to `.env` and fill in `DATABASE_URL` with the PostgreSQL connection string (in Neon: *Connection string*).
4. Create the tables and views (safe to run again):
   ```
   python crear_tablas.py
   ```
5. Load the data:
   ```
   python cargar_datos_api.py
   ```
6. Dashboard. Create a read-only user once, in the database:
   ```sql
   CREATE ROLE dashboard_ro WITH LOGIN PASSWORD 'a-long-password';
   GRANT CONNECT ON DATABASE neondb TO dashboard_ro;
   GRANT USAGE ON SCHEMA public TO dashboard_ro;
   GRANT SELECT ON totales_diarios, v_rendimiento_paginas TO dashboard_ro;
   ```
   Save its connection in `.streamlit/secrets.toml` (never committed). The `+psycopg2` is required:
   ```toml
   [connections.neon]
   url = "postgresql+psycopg2://dashboard_ro:a-long-password@HOST/neondb?sslmode=require"
   ```
   And open it:
   ```
   streamlit run app.py
   ```
7. Weekly AI summary. Create the agent's role once, with SQL (roles created from the Neon console inherit `neon_superuser`, which can read and write everything):
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

Connection checks: `python probar_searchconsole.py` (API) and `python probar_db.py` (database). The tests need neither: `python test_app.py` and `python test_agente.py`.

## Notes on the data

- **`rendimiento_api` adds up to far less than the Search Console panel; `totales_diarios` and `rendimiento_paginas` don't.** When the `query` dimension is requested, Search Console omits anonymized queries, about 70 % of clicks on this site (on October 9: 26 clicks by query against 96 in total). So totals and pages are stored from separate requests without the query, and they match the panel. `rendimiento_api` is for analyzing queries, knowing it only covers the visible ones. Impressions by page add up to about 1 % more than the totals, because the API counts per page; clicks match.
- **The same page can show up more than once** (with and without `www`, `http` or `https`, trailing `/`), because it's a domain property. They're merged when querying, not when storing: the analysis reads the `v_rendimiento` and `v_rendimiento_paginas` views.
- **The windows in `sql/03_analisis.sql` end on `v_ventana.fin` (today − 3), not today.** Search Console takes 2–3 days to consolidate; if "the last 7 days" ended today they'd hold 5 days of data against 7 for the week before, and everything would look like a drop. Run `cargar_datos_api.py` before analyzing: days not yet loaded show as 0.
- **The dashboard and the agent anchor their windows to the last loaded day** (`MAX(fecha)`), not to `v_ventana.fin`. They can run on any day of the week while ingestion is weekly: with today − 3, the current window would include days not loaded yet.
- **CTR and position are never averaged.** When grouping, recompute them: CTR = `SUM(clics) / SUM(impresiones)`; position weighted by impressions.

## Build log

Each stage, as it happened: what I did, the problems I ran into and what came out of it.

<details>
<summary><b>Stage 1: Loading and first analysis of Search Console data in PostgreSQL</b></summary>

**Goal**
Build the base of the monitoring system with real Google Search Console data from Estudio Jurídico Ríos's website, using PostgreSQL as the database.

**What I did**

1. **Table design:** created the `consultas` (queries) and `paginas` (pages) tables, with a suitable data type for each metric (clicks, impressions, CTR and position).
2. **Import through staging tables:** Search Console exports carry CTR as text with a `%` (e.g. `3.45%`), which can't be loaded straight into a numeric column. So I first imported the CSVs into `_raw` tables with every column as text.
3. **Cleaning and transformation:** moved the data into the final tables with `INSERT ... SELECT`, stripping the `%` with `REPLACE` and casting with `::INTEGER` and `::NUMERIC`.
4. **Data validation:** checking with `COUNT(*)`, I found the `paginas` table had 82 rows instead of 4: the queries file had been loaded by mistake. I emptied the tables with `TRUNCATE`, redid the import and confirmed the result.
5. **Analysis:** wrote SQL queries to find the searches bringing the most clicks, CTR opportunities and keywords close to the first page of results.

**Findings**

- **Brand dependence:** of 26 visits from Google, 24 (92 %) came from searching the firm's name. Today the site mostly attracts people who already knew it.
- **First sign of local acquisition:** "abogados laborales en parana" (employment lawyers in Paraná) ranks 3rd. It's a non-brand search from someone who hasn't chosen a lawyer yet, and the main growth opportunity.
- **A generic search with room to grow:** "estudio juridico" (law firm) has 40 impressions at position 6. Climbing a few spots would noticeably increase clicks.
- **Irrelevant traffic identified:** "medical malpractice lawyer" (in English) generates impressions that don't match the firm's audience, so it's left out of the conclusions.

**Conclusion**
The site is new and its organic visibility depends almost entirely on the brand, but it's starting to appear in local legal-services searches. The recommended strategy is to create specific content for each practice area in Paraná, starting with employment law.

**Skills:** PostgreSQL · SQL (CREATE, INSERT…SELECT, TRUNCATE, casting) · data cleaning · validation · Google Search Console · SEO analysis

</details>

<details>
<summary><b>Stage 2: Automatic loading from the Search Console API</b></summary>

**Goal**
Replace the manual CSV export with a Python script that connects directly to the Google Search Console API and stores the data in PostgreSQL.

**What I did**

1. **Service-account authentication:** created a Google Cloud project, enabled the Search Console API and generated a service account with read-only access to the property. I chose a service account over OAuth because it lets the script run without a manual login, which the Stage 3 automation needs.
2. **Connection test:** wrote `probar_searchconsole.py` to confirm access before building the full script.
3. **New `rendimiento_api` table:** unlike the CSVs, the API returns data day by day, combining query and page. I designed a table with those three dimensions and a `UNIQUE (fecha, consulta, pagina)` constraint.
4. **Loading script (`cargar_datos_api.py`):** pulls the last 90 days, leaving a 3-day margin because Search Console takes time to consolidate. It converts CTR from a fraction (0.42) to a percentage (42.00) to keep Stage 1's format.
5. **Loading without duplicates:** `INSERT ... ON CONFLICT DO UPDATE`. If the script runs more than once over the same dates, it updates the existing rows instead of repeating them.
6. **Credential protection:** the Google key and the database password live in `credenciales.json` and `.env`, excluded from the repository with `.gitignore`. The repo includes a `.env.example` template.

**Problems I solved**

- **Windows blocked a library:** Windows 11 Smart App Control blocked the `.dll` that `psycopg` needs. Instead of turning off a system security protection, I switched to `pg8000`, a pure-Python connector with no `.dll` files. (In Stage 3 the project moved to `psycopg2-binary`, which is what `requirements.txt` lists today and works fine.)
- **Name conflict:** before creating the new table I checked its structure with `information_schema.columns` and found an existing `rendimiento_diario` table holding Stage 1's data. Instead of replacing it, I created `rendimiento_api` to keep that record.

**Result**
In a single run, the script loaded 291 rows covering July 4 to October 2, 2026, with no manual export.

**Skills:** Python · Google Search Console API · Google Cloud (service accounts) · PostgreSQL · SQL (UPSERT with ON CONFLICT, UNIQUE constraints, information_schema) · secure credential handling · environment troubleshooting

</details>

<details>
<summary><b>Stage 3: Cloud database and an automatic weekly run</b></summary>

**Goal**
Get the system off my computer: keep the data in a cloud PostgreSQL database and pull it from the API every week, with no manual steps.

**What I did**

1. **Neon database:** created a PostgreSQL project on Neon (version 18, São Paulo region) and switched the connector to `psycopg2-binary`. The connection string lives in the `DATABASE_URL` variable: in `.env` on my computer and as a *Secret* on GitHub. The code contains no passwords.
2. **Versioned schema:** `schema.sql` defines the `totales_diarios`, `rendimiento_paginas` and `rendimiento_api` tables (the last one with `UNIQUE (fecha, consulta, pagina)` and an index on page and date) plus their views, and `crear_tablas.py` applies it to the database. It can run any number of times without breaking anything.
3. **The same script locally and in the cloud:** `cargar_datos_api.py` reads the Google key from the `GOOGLE_CREDENTIALS_JSON` variable when it exists (on GitHub Actions) and from `credenciales.json` otherwise.
4. **More robust loading:** it requests three cuts from the API (by date, by date + page, and by date + query + page) and inserts each in batches with `execute_values`, all in one transaction: if anything fails, nothing is left half-written. The API call retries on its own after transient Google errors (5xx and 429).
5. **Weekly run on GitHub Actions:** `.github/workflows/semanal.yml` runs `cargar_datos_api.py` every Monday at 09:00 UTC (06:00 in Argentina) and has a *Run workflow* button to launch it by hand. Each run pulls the last 10 days (`DIAS_ATRAS=10`): Search Console revises recent days later, and `ON CONFLICT DO UPDATE` overwrites the old values without duplicating them. It uses minimal permissions (`contents: read`) and a 15-minute limit.
6. **Analysis queries on the API data:** in `sql/03_analisis.sql` I wrote queries 5 to 12: daily trend, brand vs. non-brand traffic, pages going up and down, position per page, CTR opportunities, new queries and a comparison with the previous week.

**Problems I solved**

- **Neon goes to sleep:** the database suspends when idle and takes a few seconds to wake up. Every connection uses `connect_timeout=30` to wait instead of failing.
- **The first GitHub run failed:** the first manual attempt (October 9) ended with `FileNotFoundError: credenciales.json`. The repository Secrets were still empty, so the script looked for the local file, which on purpose is never uploaded. I added `DATABASE_URL` and `GOOGLE_CREDENTIALS_JSON` and the next two runs went fine.
- **Windows that didn't match ingestion:** "the last 7 days" ended today, but ingestion only reaches today − 3. The current week had 5 days of data against 7 for the week before, and an unchanged site showed a fake drop of about 29 %. Windows now end on the last day with complete data (`v_ventana.fin`).
- **One page, several URLs:** with and without `www`, `http` and `https`, with and without a trailing `/`. Clicks were split across variants and looked like rises or drops. The `v_rendimiento` view merges them at query time, without touching what's stored.
- **Days without rows disappeared:** the daily trend skipped days with no data. With `generate_series` they now show up as 0.

I tested these last three fixes on a temporary database with synthetic data.

**Result**
On Monday, October 12, 2026 the workflow ran on its own and brought Neon up to date (GitHub launched it a few hours after the scheduled time, which is normal for Actions cron jobs). After that run, `rendimiento_api` held 409 rows, from August 24 to October 9, 2026.

**Skills:** Cloud PostgreSQL (Neon) · GitHub Actions (cron, Secrets) · Python (psycopg2, `execute_values`, retries) · SQL (views, `generate_series`, time windows) · environment variables and credential handling · diagnosing from CI logs

</details>

<details>
<summary><b>Stage 4: Dashboard with the trend and the pages going up and down</b></summary>

**Goal**
Show the data in Neon on a dashboard that makes sense at a glance, without running SQL queries.

**What I did**

1. **Streamlit dashboard (`app.py`):** a page that reads Neon and shows the period's four headline numbers (clicks, impressions, CTR and average position), the daily trend with an impressions/clicks selector, and two tables: pages going up and pages going down.
2. **Correct math when aggregating:** CTR is recomputed as clicks / impressions and average position is weighted by impressions, as Search Console does, instead of averaging averages.
3. **Pages going up and down:** compares the last 7 days with data against the 7 before, with merged URLs (`v_rendimiento_paginas`). It shows clicks before and after, not only the difference: with few clicks, a difference of 1 is already ±100 %. The window ends on the last loaded day rather than today − 3, because the dashboard is viewed on any day of the week and ingestion is weekly: with today − 3, the current window would include days not loaded yet.
4. **Read-only user:** the dashboard connects with its own role, `dashboard_ro`, which can only `SELECT` from `totales_diarios` and `v_rendimiento_paginas`. It doesn't use the ingestion owner's password: if it leaked, nothing could be deleted or modified. I verified it can't write, create tables or read any other table or view.
5. **Credentials outside the code:** the role's URL lives in `.streamlit/secrets.toml`, excluded from the repository with `.gitignore`.
6. **One-hour cache:** the dashboard doesn't query the database on every click. That lets Neon sleep and saves free-plan compute.
7. **A test without a database** (`test_app.py`): it mocks the connection and checks the key cases: an empty table, the database being down, days without rows and the order of the pages going up and down.

**Problems I solved**
Before closing the stage I reviewed the code and the architecture, and fixed:

- **Missing dependencies:** `streamlit` and `sqlalchemy` weren't in `requirements.txt`, so the app wouldn't start on a fresh install.
- **A password one `git add .` away from being uploaded:** `.streamlit/secrets.toml` wasn't in `.gitignore`.
- **Empty or unreachable database:** with an empty table the page broke (invalid date and division by zero), and a database outage showed the full error, including the SQL and the server. Now it shows a clear message and the details go to the log.
- **Days without data the chart skipped:** it joined the neighboring points with a line, as if nothing were missing. Those days are now filled with 0.
- **The numbers didn't match Search Console:** the dashboard showed 26 clicks and 958 impressions against 96 and 3.2k in the panel. I ruled out the `siteUrl` (it was already the domain property): when the query is requested, the API drops anonymized queries, about 70 % of clicks on this site. Ingestion now also requests totals by date and by date + page, which do include them, and the numbers and tables come from there: they match the panel. With the old data the pages table even showed the opposite of reality: a drop from 2 clicks to 0, when in fact four blog pages were going up.
- **The wrong driver in SQLAlchemy 2.1:** running the app against Neon showed that a `postgresql://` URL defaults to `psycopg` 3, while the project uses `psycopg2`. I declared the driver in the URL (`postgresql+psycopg2://`).

**Result**
As of October 9, 2026 the numbers match the Search Console panel: 96 clicks, 3,199 impressions, 3.0 % CTR and an average position of 3.8. With data through October 11, the dashboard shows 98 clicks, 3,327 impressions, 2.9 % CTR and position 3.9. That last week four blog pages went up (the biggest from 0 to 9 clicks) and the main page went down from 3 to 2. For now it runs on my computer (`streamlit run app.py`); it will be published as part of Stage 5e.

**Skills:** Streamlit · Python (pandas, SQLAlchemy) · SQL (CTEs, `FULL JOIN`, time windows) · PostgreSQL roles and permissions (least privilege) · secrets management · tests with a mocked connection · code and architecture review

</details>

<details>
<summary><b>Stage 5a (in progress): Weekly AI summary</b></summary>

**Goal**
Every Monday, an email with the numbers, a diagnosis and up to three recommendations, each labeled 🤖 (the agent does it), 🤝 (the agent prepares it and a person approves) or 👤 (a person does it).

**What I did**

1. **An `agente/` package run as `python -m agente`,** as a second job in the weekly workflow that only runs when ingestion succeeds (`needs: ingesta`).
2. **`detectar.py`:** runs the SQL (this week's totals vs. last week's, pages going up and down, CTR opportunities, new queries, brand vs. non-brand) and builds a list of findings, each with an ID and its sentence for the email written from the SQL numbers.
3. **`estratega.py`:** a single call to Claude Sonnet with structured output (a Pydantic schema). The model's instructions live in `agente/reglas_seo.md`: the data rules from the notes above, plus the output format. A hash of that file is stored with every diagnosis as the prompt version.
4. **`mail.py`:** a plain-text and HTML email sent through Resend's API. Everything that comes from the AI or from search queries is HTML-escaped, since anyone can type anything into Google.
5. **A `diagnosticos` table** with `UNIQUE (cliente, ventana_fin)` and an `enviado` flag: running twice on the same Monday doesn't duplicate the row or the email.
6. **A dedicated `agente_rw` role:** reads three objects, writes only to `diagnosticos` and can't delete. It was created with SQL rather than from the Neon console, because console-created roles inherit `neon_superuser`.
7. **`test_agente.py`:** 7 cases with the database, the AI and Resend mocked: no data, low volume, an incomplete window, an AI failure or invalid JSON, a repeated run (including a failed send that gets retried), a recommendation citing a finding that doesn't exist, and HTML escaping.

**Design decisions**

- **One Sonnet call over findings computed in SQL,** instead of a chain of two models: a cheaper first model added nothing on top of already-clean JSON.
- **Thresholds calibrated on real data:** the week to October 23 had 21 clicks in total, so a page has to move at least 3 clicks and a new query needs at least 5 impressions to be reported.
- **Incomplete window** (fewer than 14 days with data): no comparison and no AI call; the email goes out with a warning.

**Pending**
API keys and GitHub secrets, and the first real run with the AI on.

**Skills:** Claude API (structured outputs) · Pydantic · prompt design · idempotent jobs · PostgreSQL roles (least privilege) · email delivery (Resend) · testing with mocks

</details>
