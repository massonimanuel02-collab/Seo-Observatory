"""Observatorio SEO - Etapa 5a: resumen semanal con IA. Se corre con: python -m agente

detectar (SQL) -> estratega (Sonnet, JSON) -> tabla diagnosticos (Neon) -> mail (Resend).
Con SOLO_IMPRIMIR=1 muestra el mail en pantalla: no escribe en la base ni manda nada.
Con --demo arma el mail con los datos ficticios de agente/demo.json: no necesita base, IA ni claves.
"""
import json
import os
import sys
from datetime import date
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import Json, RealDictCursor

from agente import detectar, estratega, mail
from agente.config import CLIENTE, MODELO_ESTRATEGA


def correr(cur, solo_imprimir=False):
    datos = detectar.detectar(cur)

    if solo_imprimir:
        asunto, texto, _ = mail.armar(datos, estratega.recomendar(datos))
        print(asunto, texto, sep="\n\n")
        return

    if datos["fin"] is None:  # base vacía: no hay semana que guardar, solo el aviso
        mail.enviar(*mail.armar(datos, None), f"sin-datos-{date.today()}")
        return

    # Una fila por cliente y semana (UNIQUE): correr dos veces el mismo lunes no duplica nada.
    cur.execute(
        "SELECT id, hallazgos, respuesta_ia, enviado FROM diagnosticos WHERE cliente = %s AND ventana_fin = %s",
        (CLIENTE, datos["fin"]),
    )
    fila = cur.fetchone()
    if fila and fila["enviado"]:
        print(f"El resumen de la semana al {datos['fin']} ya se envió.")
        return

    if fila:
        # Una corrida anterior guardó el diagnóstico pero no pudo mandar el mail: se reenvía lo
        # guardado, sin volver a llamar a la IA (los IDs de sus recomendaciones son de esos hallazgos).
        datos, respuesta = fila["hallazgos"], fila["respuesta_ia"]
    else:
        respuesta = estratega.recomendar(datos)
        cur.execute(
            """
            INSERT INTO diagnosticos (cliente, ventana_fin, hallazgos, respuesta_ia, modelo, version_prompt)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (cliente, ventana_fin) DO NOTHING
            RETURNING id
            """,
            (CLIENTE, datos["fin"], Json(datos), Json(respuesta) if respuesta else None,
             MODELO_ESTRATEGA, estratega.VERSION_PROMPT),
        )
        fila = cur.fetchone()
        if fila is None:
            print("Otra corrida guardó esta semana al mismo tiempo: no se manda nada desde acá.")
            return

    mail.enviar(*mail.armar(datos, respuesta), f"diagnostico-{fila['id']}")
    cur.execute("UPDATE diagnosticos SET enviado = TRUE WHERE id = %s", (fila["id"],))
    print(f"Resumen de la semana al {datos['fin']} enviado.")


def demo():
    """Mismo armado y mismo mail que una semana real, a partir de filas ficticias y una respuesta de ejemplo."""
    ejemplo = json.loads(Path(__file__).with_name("demo.json").read_text(encoding="utf-8"))
    filas = ejemplo["filas"]
    for t in filas["totales"]:
        t["fin"] = date.fromisoformat(t["fin"])  # psycopg2 devuelve fechas, el JSON texto
    datos = detectar.armar(filas)
    respuesta = estratega.Respuesta.model_validate(ejemplo["respuesta_ia"]).model_dump()
    asunto, texto, _ = mail.armar(datos, respuesta)
    print(asunto, texto, sep="\n\n")


def main():
    sys.stdout.reconfigure(encoding="utf-8")  # emojis del mail en consolas de Windows
    if "--demo" in sys.argv[1:]:
        demo()
        return
    load_dotenv()
    # connect_timeout: Neon tarda en despertar si estuvo inactiva
    conexion = psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=30)
    # Cada paso queda guardado al instante: si después falla el mail, el diagnóstico ya está en la base
    conexion.autocommit = True
    try:
        with conexion.cursor(cursor_factory=RealDictCursor) as cur:
            correr(cur, solo_imprimir=os.getenv("SOLO_IMPRIMIR") == "1")
    finally:
        conexion.close()


if __name__ == "__main__":
    main()
