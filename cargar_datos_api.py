"""
Observatorio SEO - Etapa 3
Trae los datos de la API de Google Search Console y los guarda en PostgreSQL (Neon).
"""

import json
import os
from datetime import date, timedelta

import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Lee las variables del archivo .env (DATABASE_URL)
load_dotenv()

SITIO = "sc-domain:estudiojuridicorios.com.ar"
DIAS_ATRAS = int(os.getenv("DIAS_ATRAS", "90"))  # cuántos días hacia atrás traer
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
FILAS_POR_PEDIDO = 25000  # máximo que permite la API por pedido


def conectar_search_console():
    """Se autentica con la cuenta de servicio y devuelve el cliente de la API."""
    credenciales_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if credenciales_json:
        # En la nube (GitHub Actions): las credenciales vienen de una variable
        credenciales = service_account.Credentials.from_service_account_info(
            json.loads(credenciales_json), scopes=SCOPES
        )
    else:
        # En tu compu: las credenciales vienen del archivo
        credenciales = service_account.Credentials.from_service_account_file(
            "credenciales.json", scopes=SCOPES
        )
    return build("searchconsole", "v1", credentials=credenciales)


def traer_datos(servicio, fecha_inicio, fecha_fin):
    """Pide a la API los datos por fecha, consulta y página (con paginación)."""
    filas = []
    inicio = 0
    while True:
        cuerpo = {
            "startDate": fecha_inicio.isoformat(),
            "endDate": fecha_fin.isoformat(),
            "dimensions": ["date", "query", "page"],
            "rowLimit": FILAS_POR_PEDIDO,
            "startRow": inicio,
        }
        respuesta = servicio.searchanalytics().query(siteUrl=SITIO, body=cuerpo).execute()
        lote = respuesta.get("rows", [])
        filas.extend(lote)
        if len(lote) < FILAS_POR_PEDIDO:
            break  # ya no hay más páginas
        inicio += FILAS_POR_PEDIDO
    return filas


def guardar_en_postgres(filas):
    """Inserta las filas en Neon. Si ya existen, las actualiza."""
    if not filas:
        print("No hay filas para guardar.")
        return

    valores = [
        (
            date.fromisoformat(fila["keys"][0]),  # texto "2026-09-30" -> fecha
            fila["keys"][1],                      # consulta
            fila["keys"][2],                      # página
            int(fila["clicks"]),
            int(fila["impressions"]),
            round(fila["ctr"] * 100, 2),          # la API da 0.42 -> guardamos 42.00
            round(fila["position"], 2),
        )
        for fila in filas
    ]

    conexion = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        # "with conexion" guarda los cambios si todo salió bien
        # y los deshace si hubo un error
        with conexion:
            with conexion.cursor() as cursor:
                execute_values(
                    cursor,
                    """
                    INSERT INTO rendimiento_api
                        (fecha, consulta, pagina, clics, impresiones, ctr, posicion)
                    VALUES %s
                    ON CONFLICT (fecha, consulta, pagina) DO UPDATE SET
                        clics = EXCLUDED.clics,
                        impresiones = EXCLUDED.impresiones,
                        ctr = EXCLUDED.ctr,
                        posicion = EXCLUDED.posicion
                    """,
                    valores,
                    page_size=1000,
                )
    finally:
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
    print("Datos guardados en Neon.")


if __name__ == "__main__":
    main()