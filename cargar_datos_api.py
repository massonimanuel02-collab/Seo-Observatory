"""
Observatorio SEO - Etapa 2
Trae los datos de la API de Google Search Console y los guarda en PostgreSQL.
"""

import os
from datetime import date, timedelta

import pg8000.dbapi
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Lee las variables del archivo .env (datos de conexión a Postgres)
load_dotenv()

SITIO = "sc-domain:estudiojuridicorios.com.ar"
DIAS_ATRAS = 90  # cuántos días hacia atrás traer


def conectar_search_console():
    """Se autentica con la cuenta de servicio y devuelve el cliente de la API."""
    credenciales = service_account.Credentials.from_service_account_file(
        "credenciales.json",
        scopes=["https://www.googleapis.com/auth/webmasters.readonly"],
    )
    return build("searchconsole", "v1", credentials=credenciales)


def traer_datos(servicio, fecha_inicio, fecha_fin):
    """Pide a la API los datos por fecha, consulta y página."""
    cuerpo = {
        "startDate": fecha_inicio.isoformat(),
        "endDate": fecha_fin.isoformat(),
        "dimensions": ["date", "query", "page"],
        "rowLimit": 25000,  # máximo por pedido; alcanza de sobra para un sitio chico
    }
    respuesta = servicio.searchanalytics().query(siteUrl=SITIO, body=cuerpo).execute()
    return respuesta.get("rows", [])


def guardar_en_postgres(filas):
    """Inserta las filas en la tabla. Si ya existen, las actualiza."""
    conexion = pg8000.dbapi.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )
    cursor = conexion.cursor()

    for fila in filas:
        fecha, consulta, pagina = fila["keys"]
        cursor.execute(
            """
            INSERT INTO rendimiento_api
                (fecha, consulta, pagina, clics, impresiones, ctr, posicion)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (fecha, consulta, pagina) DO UPDATE SET
                clics = EXCLUDED.clics,
                impresiones = EXCLUDED.impresiones,
                ctr = EXCLUDED.ctr,
                posicion = EXCLUDED.posicion
            """,
            (
                date.fromisoformat(fecha),  # texto "2026-09-30" -> fecha
                consulta,
                pagina,
                int(fila["clicks"]),
                int(fila["impressions"]),
                round(fila["ctr"] * 100, 2),  # la API da 0.42 -> guardamos 42.00
                round(fila["position"], 2),
            ),
        )

    conexion.commit()  # guarda los cambios en la base
    conexion.close()


def main():
    # Search Console tarda 2-3 días en tener los datos completos
    fecha_fin = date.today() - timedelta(days=3)
    fecha_inicio = fecha_fin - timedelta(days=DIAS_ATRAS)

    print(f"Trayendo datos del {fecha_inicio} al {fecha_fin}...")
    servicio = conectar_search_console()
    filas = traer_datos(servicio, fecha_inicio, fecha_fin)
    print(f"La API devolvió {len(filas)} filas.")

    guardar_en_postgres(filas)
    print("Datos guardados en PostgreSQL.")


if __name__ == "__main__":
    main()