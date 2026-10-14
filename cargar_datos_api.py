"""
Observatorio SEO - Etapa 3
Trae los datos de la API de Google Search Console (totales por día, por página y por
consulta) y los guarda en PostgreSQL (Neon).
"""

import json
import os
from datetime import date, timedelta
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Lee las variables del archivo .env (DATABASE_URL)
load_dotenv()

RAIZ = Path(__file__).parent  # carpeta del proyecto, sin importar desde dónde se ejecute

SITIO = "sc-domain:estudiojuridicorios.com.ar"
DIAS_ATRAS = int(os.getenv("DIAS_ATRAS", "90"))  # cuántos días hacia atrás traer
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
FILAS_POR_PEDIDO = 25000  # máximo que permite la API por pedido

# Tabla donde se guarda -> dimensiones que se piden a la API.
# Pedir "query" hace que Search Console omita las consultas anónimas (en este sitio, ~70 % de
# los clics), así que rendimiento_api suma menos que el panel. Los pedidos por "date" y por
# "date" + "page" no las omiten: coinciden con el panel.
CARGAS = {
    "totales_diarios": ["date"],
    "rendimiento_paginas": ["date", "page"],
    "rendimiento_api": ["date", "query", "page"],
}
COLUMNA = {"date": "fecha", "query": "consulta", "page": "pagina"}  # dimensión de la API -> columna


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
            RAIZ / "credenciales.json", scopes=SCOPES
        )
    return build("searchconsole", "v1", credentials=credenciales)


def traer_datos(servicio, dimensiones, fecha_inicio, fecha_fin):
    """Pide a la API los datos agrupados por esas dimensiones (con paginación)."""
    filas = []
    inicio = 0
    while True:
        cuerpo = {
            "startDate": fecha_inicio.isoformat(),
            "endDate": fecha_fin.isoformat(),
            "dimensions": dimensiones,
            "rowLimit": FILAS_POR_PEDIDO,
            "startRow": inicio,
        }
        # num_retries: reintenta solo si Google responde 5xx o 429 (error pasajero)
        respuesta = servicio.searchanalytics().query(siteUrl=SITIO, body=cuerpo).execute(num_retries=3)
        lote = respuesta.get("rows", [])
        filas.extend(lote)
        if len(lote) < FILAS_POR_PEDIDO:
            break  # ya no hay más páginas
        inicio += FILAS_POR_PEDIDO
    return filas


def guardar_en_postgres(datos):
    """Inserta en Neon las filas de cada tabla ({tabla: filas}). Si ya existen, las actualiza."""
    if not any(datos.values()):
        print("No hay filas para guardar.")
        return

    # connect_timeout: Neon tarda en despertar si estuvo inactiva
    conexion = psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=30)
    try:
        # "with conexion" guarda los cambios de las tres tablas si todo salió bien
        # y los deshace si hubo un error
        with conexion:
            with conexion.cursor() as cursor:
                for tabla, filas in datos.items():
                    claves = ", ".join(COLUMNA[d] for d in CARGAS[tabla])  # lo que identifica una fila
                    valores = [
                        (
                            date.fromisoformat(fila["keys"][0]),  # texto "2026-09-30" -> fecha
                            *fila["keys"][1:],                    # consulta y/o página, si se pidieron
                            int(fila["clicks"]),
                            int(fila["impressions"]),
                            round(fila["ctr"] * 100, 2),          # la API da 0.42 -> guardamos 42.00
                            round(fila["position"], 2),
                        )
                        for fila in filas
                    ]
                    execute_values(
                        cursor,
                        f"""
                        INSERT INTO {tabla}
                            ({claves}, clics, impresiones, ctr, posicion)
                        VALUES %s
                        ON CONFLICT ({claves}) DO UPDATE SET
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
    datos = {}
    for tabla, dimensiones in CARGAS.items():
        datos[tabla] = traer_datos(servicio, dimensiones, fecha_inicio, fecha_fin)
        print(f"{tabla}: la API devolvió {len(datos[tabla])} filas.")

    guardar_en_postgres(datos)
    print("Datos guardados en Neon.")


if __name__ == "__main__":
    main()
