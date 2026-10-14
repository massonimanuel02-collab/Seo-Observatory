import logging

import pandas as pd
import streamlit as st

# --- Configuración de la página ---
st.set_page_config(page_title="Observatorio SEO", page_icon="📈", layout="wide")
st.title("📈 Observatorio SEO")

# --- 1. Conexión a Neon y consultas ---
# Los datos de acceso NO van acá: Streamlit los lee de .streamlit/secrets.toml
# (en Streamlit Cloud, de Settings > Secrets), con un usuario de SOLO LECTURA:
#   [connections.neon]
#   url = "postgresql+psycopg2://dashboard_ro:CLAVE@HOST/BASE?sslmode=require"
# El "+psycopg2" es necesario: SQLAlchemy 2.1 usa psycopg 3 por defecto y acá está instalado psycopg2.
# connect_timeout: Neon tarda en despertar si estuvo inactiva (igual que en cargar_datos_api.py).
# Si esta app lee otra tabla o vista, hay que darle GRANT SELECT a dashboard_ro en Neon.
#
# Los totales salen de totales_diarios y las páginas de rendimiento_paginas: son los cortes de la
# API que incluyen las consultas anónimas, así que coinciden con el panel de Search Console.
# (rendimiento_api, que también trae la consulta, las omite: en este sitio son ~70 % de los clics.)
#
# La posición del período se promedia "ponderada por impresiones": un día con 500 impresiones
# pesa más que uno con 5. Es como lo calcula Search Console.
# ttl="1h" = Streamlit guarda el resultado una hora y no le pega a la base en cada clic.
try:
    conn = st.connection("neon", type="sql", connect_args={"connect_timeout": 30})
    diario = conn.query(
        """
        SELECT fecha, clics, impresiones, posicion::float AS posicion
        FROM totales_diarios
        ORDER BY fecha
        """,
        ttl="1h",
    )
    # Misma cuenta que la consulta 8 de sql/03_analisis.sql, pero con la ventana anclada al
    # último día cargado y no a hoy - 3 (v_ventana): este dashboard se mira cualquier día y la
    # ingesta es semanal, así que con hoy - 3 la ventana "actual" tendría días todavía sin cargar.
    paginas = conn.query(
        """
        WITH ventana AS (SELECT MAX(fecha) AS fin FROM totales_diarios),
        actual AS (
          SELECT pagina, SUM(clics) AS clics
          FROM v_rendimiento_paginas, ventana
          WHERE fecha > fin - 7 AND fecha <= fin
          GROUP BY pagina
        ),
        anterior AS (
          SELECT pagina, SUM(clics) AS clics
          FROM v_rendimiento_paginas, ventana
          WHERE fecha > fin - 14 AND fecha <= fin - 7
          GROUP BY pagina
        )
        SELECT COALESCE(a.pagina, p.pagina) AS pagina,
               COALESCE(p.clics, 0) AS clics_antes,
               COALESCE(a.clics, 0) AS clics_ahora,
               COALESCE(a.clics, 0) - COALESCE(p.clics, 0) AS diferencia
        FROM actual a
        FULL JOIN anterior p ON a.pagina = p.pagina
        """,
        ttl="1h",
    )
except Exception:
    # Sin traceback en pantalla (mostraría el SQL y el host): el detalle queda en el log.
    logging.exception("No se pudo consultar la base")
    st.error("No se pudo leer la base de datos. Probá de nuevo en un minuto.")
    st.stop()

# Tabla vacía (todavía sin ingesta) o sin impresiones: corta acá para no romper
# con NaT o con divisiones por 0 más abajo.
if diario["impresiones"].sum() == 0:
    st.warning("Todavía no hay datos cargados.")
    st.stop()

# Los días sin filas no salen del SQL: se rellenan con 0 para que el gráfico no los salte.
diario["fecha"] = pd.to_datetime(diario["fecha"])
diario = diario.set_index("fecha").asfreq("D").fillna({"clics": 0, "impresiones": 0}).reset_index()

desde = diario["fecha"].min()
hasta = diario["fecha"].max()
st.caption(
    f"Estudio Jurídico Ríos · datos del {desde:%d/%m/%Y} al {hasta:%d/%m/%Y} · "
    "Fuente: API de Search Console (propiedad de dominio)."
)

# --- 2. Números grandes del período ---
total_clics = int(diario["clics"].sum())
total_impresiones = int(diario["impresiones"].sum())
ctr = total_clics / total_impresiones * 100
posicion_media = (diario["posicion"] * diario["impresiones"]).sum() / total_impresiones

col1, col2, col3, col4 = st.columns(4)
col1.metric("Clics", total_clics)
col2.metric("Impresiones", total_impresiones)
col3.metric("CTR", f"{ctr:.1f}%")
col4.metric("Posición media", f"{posicion_media:.1f}")

# --- 3. Evolución diaria ---
st.subheader("Evolución diaria")
metrica = st.radio("Métrica", ["impresiones", "clics"], horizontal=True)
st.line_chart(diario, x="fecha", y=metrica)

# --- 4. Páginas que suben y que bajan ---
st.subheader("Páginas que suben y que bajan")
st.caption(
    f"Últimos 7 días con datos ({hasta - pd.Timedelta(days=6):%d/%m} al {hasta:%d/%m}) contra los 7 anteriores. "
    "Con pocos clics, 1 de diferencia ya es ±100 %: mirá los clics, no solo la diferencia."
)
suben = paginas[paginas["diferencia"] > 0].sort_values(["diferencia", "pagina"], ascending=[False, True])
bajan = paginas[paginas["diferencia"] < 0].sort_values(["diferencia", "pagina"])
columnas = {"pagina": "Página", "clics_antes": "Clics antes", "clics_ahora": "Clics ahora", "diferencia": "Diferencia"}

col_suben, col_bajan = st.columns(2)
for col, titulo, df in [(col_suben, "Suben", suben), (col_bajan, "Bajan", bajan)]:
    col.markdown(f"**{titulo}**")
    if df.empty:
        col.caption("Ninguna.")
    else:
        col.dataframe(df, hide_index=True, width="stretch", column_config=columnas)
