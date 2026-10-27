"""Sonnet lee los hallazgos calculados en SQL y devuelve diagnóstico y hasta 3 recomendaciones.

La IA no escribe números ni HTML: devuelve un JSON con forma fija (validado con pydantic) y el mail
pone los números desde SQL. Si algo falla devuelve None, y el mail sale igual con los números solos.
"""
import hashlib
import json
import logging
from pathlib import Path
from typing import Literal

import anthropic
from pydantic import BaseModel

from agente.config import MODELO_ESTRATEGA

INSTRUCCIONES = Path(__file__).with_name("reglas_seo.md").read_text(encoding="utf-8")
# Cambia solo cuando cambian las reglas: queda guardada con cada diagnóstico.
VERSION_PROMPT = hashlib.sha256(INSTRUCCIONES.encode()).hexdigest()[:8]


class Recomendacion(BaseModel):
    hallazgo_id: int
    accion: str
    jev: Literal["agente", "hibrido", "persona"]
    motivo: str


class Respuesta(BaseModel):
    diagnostico: str
    recomendaciones: list[Recomendacion]
    advertencias: list[str]


def recomendar(datos):
    """Devuelve la respuesta como dict, o None si la ventana está incompleta o la IA falla."""
    if not datos["completa"]:
        return None
    try:
        # timeout corto: con 2 reintentos no pasa de ~6 minutos y el job (15) llega a mandar el mail igual
        respuesta = anthropic.Anthropic(timeout=120).messages.parse(
            model=MODELO_ESTRATEGA,
            max_tokens=16000,
            system=INSTRUCCIONES,
            messages=[{"role": "user", "content": json.dumps(
                {"semana": f"{datos['desde']} al {datos['fin']}", "hallazgos": datos["hallazgos"]},
                ensure_ascii=False,
            )}],
            output_format=Respuesta,
        )
        if respuesta.parsed_output is None:
            raise ValueError(f"La IA no devolvió el JSON esperado (stop_reason={respuesta.stop_reason})")
        resultado = respuesta.parsed_output.model_dump()
    except Exception:
        logging.exception("Falló la IA: el mail sale con los números solos")
        return None

    # Solo recomendaciones apoyadas en un hallazgo real, y no más de 3
    ids = {h["id"] for h in datos["hallazgos"]}
    resultado["recomendaciones"] = [r for r in resultado["recomendaciones"] if r["hallazgo_id"] in ids][:3]
    return resultado
