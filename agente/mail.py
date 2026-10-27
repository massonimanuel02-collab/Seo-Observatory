"""Arma el mail semanal (números de SQL, interpretación de la IA) y lo manda con la API de Resend."""
import html
import json
import os
import urllib.request
from datetime import date

from agente.config import REMITENTE

JEV ={"agente": "🤖", "hibrido": "🤝", "persona": "👤"}
LEYENDA = "🤖 lo hace el agente · 🤝 el agente lo prepara y vos lo aprobás · 👤 lo hacés vos"


def armar(datos, respuesta):
    """Devuelve (asunto, texto, html). respuesta es lo que devolvió el estratega, o None."""
    if datos["fin"]:
        desde, fin = date.fromisoformat(datos["desde"]), date.fromisoformat(datos["fin"])
        asunto = f"Observatorio SEO · Semana {desde:%d/%m} – {fin:%d/%m}"
    else:
        asunto = "Observatorio SEO · Sin datos"

    hallazgos = {h["id"]: h for h in datos["hallazgos"]}
    secciones = []  # (título, [líneas])
    if datos["aviso"]:
        secciones.append(("Aviso", [datos["aviso"]]))
    if hallazgos:
        secciones.append(("Los números", [hallazgos[1]["texto"]]))
    if respuesta:
        secciones.append(("Qué pasó", [respuesta["diagnostico"]]))
    if len(hallazgos) > 1:
        secciones.append(("Los datos de la semana", [h["texto"] for h in datos["hallazgos"][1:]]))
    if respuesta and respuesta["recomendaciones"]:
        secciones.append(("Qué haría", [
            f"{JEV[r['jev']]} {r['accion']}\n{r['motivo']}\nDato: {hallazgos[r['hallazgo_id']]['texto']}"
            for r in respuesta["recomendaciones"]
        ] + [LEYENDA]))
    if respuesta and respuesta["advertencias"]:
        secciones.append(("Ojo", respuesta["advertencias"]))
    if datos["completa"] and not respuesta:
        secciones.append(("Sin análisis", ["La IA no respondió esta semana: van los números solos."]))

    texto = "\n\n".join(
        f"{titulo}\n" + "\n".join("- " + linea.replace("\n", "\n  ") for linea in lineas)  # sangría en las líneas de continuación
        for titulo, lineas in secciones
    )
    # Todo se escapa: las consultas las escribe cualquiera en Google y el diagnóstico lo escribe la IA
    cuerpo = "".join(
        f"<h3>{html.escape(titulo)}</h3><ul>"
        + "".join(f"<li>{html.escape(linea).replace(chr(10), '<br>')}</li>" for linea in lineas)
        + "</ul>"
        for titulo, lineas in secciones
    )
    return asunto, texto, f'<div style="font-family:sans-serif;max-width:640px">{cuerpo}</div>'


def enviar(asunto, texto, cuerpo_html, clave_idempotencia):
    """Manda el mail. Si Resend responde con error, urlopen lanza HTTPError y el job falla.

    La clave de idempotencia hace que Resend no lo mande dos veces si se reintenta en 24 horas.
    """
    pedido = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps({
            "from": REMITENTE,
            "to": [os.environ["MAIL_DESTINO"]],
            "subject": asunto,
            "text": texto,
            "html": cuerpo_html,
        }).encode(),
        headers={
            "Authorization": f"Bearer {os.environ['RESEND_API_KEY']}",
            "Content-Type": "application/json",
            "Idempotency-Key": clave_idempotencia,
            "User-Agent": "observatorio-seo",
        },
    )
    urllib.request.urlopen(pedido, timeout=30).close()
