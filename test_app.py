"""Prueba de app.py sin base de datos (la conexión es falsa): python test_app.py"""
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest

DIAS = (date(2026, 10, 1), 5, 100, 3.0), (date(2026, 10, 3), 7, 50, 6.0)


def datos(*filas):
    return pd.DataFrame(filas, columns=["fecha", "clics", "impresiones", "posicion"])


def paginas(*filas):
    return pd.DataFrame(filas, columns=["pagina", "clics_antes", "clics_ahora", "diferencia"])


def correr(df=None, pag=None, error=None):
    conn = MagicMock()
    # la app hace dos consultas, en este orden: totales por día y páginas
    conn.query.side_effect = error or [df, pag if pag is not None else paginas()]
    with patch.object(st, "connection", return_value=conn), patch.object(st, "line_chart") as grafico:
        return AppTest.from_file("app.py", default_timeout=30).run(), grafico


def test_tabla_vacia():
    at, _ = correr(datos())
    assert not at.exception
    assert at.warning[0].value == "Todavía no hay datos cargados."


def test_error_de_base():
    with patch("logging.exception") as log:
        at, _ = correr(error=Exception("boom"))
    assert not at.exception
    assert at.error[0].value.startswith("No se pudo leer")
    assert log.called


def test_dias_sin_filas_van_en_cero():
    at, grafico = correr(datos(*DIAS))
    assert not at.exception
    d = grafico.call_args.args[0]
    assert list(d["clics"]) == [5, 0, 7]
    assert list(d["impresiones"]) == [100, 0, 50]
    assert at.metric[2].value == "8.0%"  # 12 clics / 150 impresiones
    assert at.metric[3].value == "4.0"  # (3*100 + 6*50) / 150: el día vacío no cuenta


def test_paginas_suben_y_bajan():
    pag = paginas(("a.com", 1, 4, 3), ("b.com", 5, 2, -3), ("c.com", 2, 2, 0), ("d.com", 0, 1, 1), ("e.com", 4, 0, -4))
    at, _ = correr(datos(*DIAS), pag)
    assert not at.exception
    assert list(at.dataframe[0].value["pagina"]) == ["a.com", "d.com"]  # suben, de más a menos; c.com (0) no sale
    assert list(at.dataframe[1].value["pagina"]) == ["e.com", "b.com"]  # bajan, la que más cayó primero


def test_paginas_sin_cambios():
    at, _ = correr(datos(*DIAS))
    assert not at.exception
    assert [c.value for c in at.caption].count("Ninguna.") == 2


if __name__ == "__main__":
    for nombre, prueba in [*globals().items()]:
        if nombre.startswith("test_"):
            prueba()
            print("ok", nombre)
