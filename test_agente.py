"""Prueba del agente sin base, sin IA y sin Resend reales: python test_agente.py"""
import json
import os
from datetime import date
from unittest.mock import patch

from agente import detectar, estratega, mail
from agente.__main__ import correr

os.environ.update(MAIL_DESTINO="yo@ejemplo.com", RESEND_API_KEY="re_prueba")
FIN = date(2026, 10, 23)


def filas(dias=(7, 7), paginas=(), nuevas=()):
    """Filas como las devuelve cada consulta de detectar.CONSULTAS. dias=(actual, anterior)."""
    totales = [{"semana": "actual", "fin": FIN, "dias": dias[0], "clics": 21, "impresiones": 1171, "ctr": 1.8, "posicion": 4.1}]
    if dias[1]:
        totales.append({"semana": "anterior", "fin": FIN, "dias": dias[1], "clics": 33, "impresiones": 1029, "ctr": 3.2, "posicion": 3.9})
    return {
        "totales": totales if dias[0] else [],
        "paginas": [{"pagina": p, "clics_antes": a, "clics_ahora": b, "diferencia": b - a} for p, a, b in paginas],
        "oportunidades_ctr": [],
        "consultas_nuevas": [{"consulta": c, "clics": 0, "impresiones": i} for c, i in nuevas],
        "marca": [],
    }


SEMANA = filas(paginas=[("sitio.com.ar/blog/amparo", 14, 6)])  # hallazgos: 1 totales, 2 la página que baja


class Diagnosticos:
    """Imita la tabla diagnosticos (UNIQUE cliente + ventana_fin) para lo que hace correr()."""

    def __init__(self):
        self.filas, self.resultado = {}, None

    def execute(self, sql, params):
        orden = sql.split()[0]
        if orden == "SELECT":
            self.resultado = self.filas.get(params[1])
        elif orden == "INSERT":
            _, fin, hallazgos, respuesta, *_ = params
            self.resultado = None if fin in self.filas else {
                "id": len(self.filas) + 1, "enviado": False,
                "hallazgos": json.loads(json.dumps(hallazgos.adapted)),  # ida y vuelta por JSONB
                "respuesta_ia": respuesta and json.loads(json.dumps(respuesta.adapted)),
            }
            if self.resultado:
                self.filas[fin] = self.resultado
        else:  # UPDATE ... SET enviado = TRUE WHERE id = %s
            for fila in self.filas.values():
                fila["enviado"] |= fila["id"] == params[0]

    def fetchone(self):
        return self.resultado


def respuesta_ia(*ids):
    return estratega.Respuesta(
        diagnostico="La semana fue floja.",
        recomendaciones=[{"hallazgo_id": i, "accion": f"Acción {i}", "jev": "hibrido", "motivo": "Porque sí"} for i in ids],
        advertencias=["Poco volumen"],
    )


def correr_con(base, f, ia=None, error_ia=None, error_mail=None):
    """Corre el agente con las filas f. Devuelve (llamadas a la IA, mails enviados como dict)."""
    with patch.object(detectar, "detectar", return_value=detectar.armar(f)), \
         patch.object(estratega.anthropic, "Anthropic") as cliente, \
         patch("urllib.request.urlopen", side_effect=error_mail) as urlopen:
        parse = cliente.return_value.messages.parse
        parse.side_effect = error_ia
        parse.return_value.parsed_output = ia
        try:
            correr(base)
        finally:
            mails = [json.loads(c.args[0].data) for c in urlopen.call_args_list if not error_mail]
    return parse.call_count, mails


def test_semana_sin_datos():
    base = Diagnosticos()
    llamadas, mails = correr_con(base, filas(dias=(0, 0)), ia=respuesta_ia(1))
    assert llamadas == 0 and not base.filas
    assert mails[0]["subject"] == "Observatorio SEO · Sin datos"
    assert "Todavía no hay datos" in mails[0]["text"]


def test_poco_volumen():
    datos = detectar.armar(filas(paginas=[("s.com/a", 1, 2), ("s.com/b", 5, 0), ("s.com/c", 0, 3), ("s.com", 4, 2)],
                                 nuevas=[("ruido", 2), ("despido sin causa parana", 8)]))
    textos = [h["texto"] for h in datos["hallazgos"][1:]]
    assert textos == ["/b baja de 5 a 0 clics", "/c sube de 0 a 3 clics",
                      'Consulta nueva: "despido sin causa parana" (8 impresiones, 0 clics)']
    assert [h["id"] for h in datos["hallazgos"]] == [1, 2, 3, 4]


def test_ventana_incompleta():
    base = Diagnosticos()
    llamadas, mails = correr_con(base, filas(dias=(7, 3), paginas=[("s.com/a", 14, 6)]), ia=respuesta_ia(1))
    assert llamadas == 0
    texto = mails[0]["text"]
    assert "Ventana incompleta: 10 de 14 días" in texto
    assert "21 clics · 1.171 impresiones" in texto and "antes" not in texto and "/a" not in texto
    assert base.filas[FIN.isoformat()]["respuesta_ia"] is None


def test_ia_falla_o_json_invalido():
    for error, salida in [(Exception("se cayó"), None), (None, None)]:  # excepción, o sin JSON válido
        with patch("logging.exception"):
            _, mails = correr_con(Diagnosticos(), SEMANA, ia=salida, error_ia=error)
        texto = mails[0]["text"]
        assert "21 clics (-12) · 1.171 impresiones (+142)" in texto
        assert "/blog/amparo baja de 14 a 6 clics" in texto
        assert "La IA no respondió" in texto and "Qué haría" not in texto


def test_corrida_repetida():
    base = Diagnosticos()
    # 1) guarda el diagnóstico pero Resend falla: queda enviado = FALSE y el job termina con error
    try:
        correr_con(base, SEMANA, ia=respuesta_ia(2), error_mail=OSError("Resend caído"))
        raise AssertionError("tenía que fallar")
    except OSError:
        pass
    assert len(base.filas) == 1 and not base.filas[FIN.isoformat()]["enviado"]
    # 2) reintento: manda lo guardado, sin volver a llamar a la IA ni insertar otra fila
    llamadas, mails = correr_con(base, SEMANA, ia=respuesta_ia(1))
    assert llamadas == 0 and len(mails) == 1 and "🤝 Acción 2" in mails[0]["text"]
    assert len(base.filas) == 1 and base.filas[FIN.isoformat()]["enviado"]
    # 3) otra corrida más: ya está enviado, no hace nada
    llamadas, mails = correr_con(base, SEMANA, ia=respuesta_ia(1))
    assert llamadas == 0 and mails == []


def test_hallazgo_inexistente():
    base = Diagnosticos()
    _, mails = correr_con(base, SEMANA, ia=respuesta_ia(2, 99, 1, 2))
    recomendaciones = base.filas[FIN.isoformat()]["respuesta_ia"]["recomendaciones"]
    assert [r["hallazgo_id"] for r in recomendaciones] == [2, 1, 2]  # el 99 se descarta; tope de 3
    assert "Dato: /blog/amparo baja de 14 a 6 clics" in mails[0]["text"]
    assert "<li>" in mails[0]["html"]


def test_html_escapado():
    datos = detectar.armar(filas(nuevas=[("<script>alert(1)</script>", 9)]))
    _, _, cuerpo = mail.armar(datos, None)
    assert "<script>" not in cuerpo and "&lt;script&gt;" in cuerpo


if __name__ == "__main__":
    for nombre, prueba in [*globals().items()]:
        if nombre.startswith("test_"):
            prueba()
            print("ok", nombre)
