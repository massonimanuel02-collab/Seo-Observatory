"""Corre las consultas de análisis en Neon y arma los hallazgos (con ID) que lee el estratega.

SQL hace todas las cuentas; acá solo se filtra por umbral y se arma cada texto con esos números.
Las ventanas terminan en el último día cargado (MAX(fecha) de totales_diarios), igual que el
dashboard: la ingesta es semanal y Search Console tarda 2-3 días en consolidar.
"""
from datetime import timedelta

from agente.config import MAX_POR_TIPO, UMBRAL_CLICS, UMBRAL_IMPRESIONES

VENTANA = "WITH v AS (SELECT MAX(fecha) AS fin FROM totales_diarios)"

CONSULTAS = {
    # Totales de la semana actual (últimos 7 días con datos) y de la anterior. Incluyen las
    # consultas anónimas. CTR y posición se recalculan por semana, no se promedian.
    "totales": VENTANA + """
        SELECT CASE WHEN fecha > fin - 7 THEN 'actual' ELSE 'anterior' END AS semana, fin,
               COUNT(*) AS dias, SUM(clics) AS clics, SUM(impresiones) AS impresiones,
               ROUND(100.0 * SUM(clics) / NULLIF(SUM(impresiones), 0), 1)::float AS ctr,
               ROUND(SUM(posicion * impresiones) / NULLIF(SUM(impresiones), 0), 1)::float AS posicion
        FROM totales_diarios, v
        WHERE fecha > fin - 14 AND fecha <= fin
        GROUP BY semana, fin
    """,
    # Consulta 8 de sql/03_analisis.sql: páginas que suben y bajan (URLs unificadas)
    "paginas": VENTANA + """,
        actual AS (
          SELECT pagina, SUM(clics) AS clics FROM v_rendimiento_paginas, v
          WHERE fecha > fin - 7 AND fecha <= fin GROUP BY pagina
        ),
        anterior AS (
          SELECT pagina, SUM(clics) AS clics FROM v_rendimiento_paginas, v
          WHERE fecha > fin - 14 AND fecha <= fin - 7 GROUP BY pagina
        )
        SELECT COALESCE(a.pagina, p.pagina) AS pagina,
               COALESCE(p.clics, 0) AS clics_antes,
               COALESCE(a.clics, 0) AS clics_ahora,
               COALESCE(a.clics, 0) - COALESCE(p.clics, 0) AS diferencia
        FROM actual a FULL JOIN anterior p ON a.pagina = p.pagina
        ORDER BY diferencia, pagina
    """,
    # Consulta 10: muchas impresiones y casi ningún clic en 28 días (solo consultas visibles)
    "oportunidades_ctr": VENTANA + """
        SELECT consulta, pagina, SUM(impresiones) AS impresiones, SUM(clics) AS clics,
               ROUND(SUM(posicion * impresiones) / NULLIF(SUM(impresiones), 0), 1)::float AS posicion
        FROM v_rendimiento, v
        WHERE fecha > fin - 28 AND fecha <= fin
        GROUP BY consulta, pagina
        HAVING SUM(impresiones) >= 20 AND SUM(clics) <= 1
        ORDER BY impresiones DESC, consulta
    """,
    # Consulta 11: consultas de esta semana que nunca habían aparecido (solo consultas visibles)
    "consultas_nuevas": VENTANA + """
        SELECT consulta, SUM(clics) AS clics, SUM(impresiones) AS impresiones
        FROM v_rendimiento, v
        WHERE fecha > fin - 7 AND fecha <= fin
          AND consulta NOT IN (SELECT consulta FROM v_rendimiento, v WHERE fecha <= fin - 7)
        GROUP BY consulta
        ORDER BY impresiones DESC, consulta
    """,
    # Consulta 6, por semana: marca ("ríos" como palabra, sin la provincia) vs. sin marca
    "marca": VENTANA + r"""
        SELECT CASE WHEN consulta ~* '\mr[ií]os\M' AND consulta !~* 'entre r[ií]os'
                    THEN 'marca' ELSE 'sin marca' END AS tipo,
               COALESCE(SUM(clics) FILTER (WHERE fecha > fin - 7), 0) AS clics_ahora,
               COALESCE(SUM(clics) FILTER (WHERE fecha <= fin - 7), 0) AS clics_antes,
               COALESCE(SUM(impresiones) FILTER (WHERE fecha > fin - 7), 0) AS impresiones_ahora,
               COALESCE(SUM(impresiones) FILTER (WHERE fecha <= fin - 7), 0) AS impresiones_antes
        FROM v_rendimiento, v
        WHERE fecha > fin - 14 AND fecha <= fin
        GROUP BY tipo
        ORDER BY tipo
    """,
}


def detectar(cur):
    """Corre las consultas con un cursor que devuelve diccionarios (RealDictCursor)."""
    filas = {}
    for nombre, sql in CONSULTAS.items():
        cur.execute(sql)
        filas[nombre] = cur.fetchall()
    return armar(filas)


def num(x, decimales=0):
    """Formato argentino: 1120 -> '1.120'; 3.04 -> '3,0'."""
    return f"{x or 0:,.{decimales}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def clics(n):
    return f"{n} clic" if n == 1 else f"{n} clics"


def ruta(pagina):
    """'sitio.com.ar/blog/x' -> '/blog/x'; 'sitio.com.ar' -> '/ (home)'. La vista ya sacó protocolo y www."""
    return "/" + pagina.partition("/")[2] if "/" in pagina else "/ (home)"


def armar(filas):
    """Arma {fin, desde, completa, aviso, hallazgos} a partir de las filas de cada consulta.

    Devuelve solo tipos que JSON sabe guardar (fechas como texto): va tal cual a la tabla diagnosticos.
    """
    if not filas["totales"]:
        return {"fin": None, "desde": None, "completa": False, "hallazgos": [],
                "aviso": "Todavía no hay datos cargados en totales_diarios."}

    fin = filas["totales"][0]["fin"]
    semanas = {f["semana"]: {k: v for k, v in f.items() if k not in ("semana", "fin")} for f in filas["totales"]}
    ahora, antes = semanas["actual"], semanas.get("anterior")
    dias = ahora["dias"] + (antes["dias"] if antes else 0)
    datos = {"fin": fin.isoformat(), "desde": (fin - timedelta(days=6)).isoformat(),
             "completa": dias == 14, "aviso": None}

    totales = {"id": 1, "tipo": "totales", "actual": ahora, "anterior": antes}
    if not datos["completa"]:
        datos["aviso"] = f"Ventana incompleta: {dias} de 14 días con datos. No se compara con la semana anterior."
        totales["texto"] = (f"{num(ahora['clics'])} clics · {num(ahora['impresiones'])} impresiones · "
                            f"CTR {num(ahora['ctr'], 1)} % · posición {num(ahora['posicion'], 1)}")
        datos["hallazgos"] = [totales]
        return datos

    totales["texto"] = (
        f"{num(ahora['clics'])} clics ({ahora['clics'] - antes['clics']:+d}) · "
        f"{num(ahora['impresiones'])} impresiones ({ahora['impresiones'] - antes['impresiones']:+d}) · "
        f"CTR {num(ahora['ctr'], 1)} % (antes {num(antes['ctr'], 1)} %) · "
        f"posición {num(ahora['posicion'], 1)} (antes {num(antes['posicion'], 1)})"
    )
    hallazgos = [totales]

    for p in filas["paginas"]:
        if abs(p["diferencia"]) >= UMBRAL_CLICS:
            verbo = "sube" if p["diferencia"] > 0 else "baja"
            hallazgos.append({"tipo": f"pagina_{verbo}", **p, "pagina": ruta(p["pagina"]),
                              "texto": f"{ruta(p['pagina'])} {verbo} de {p['clics_antes']} a {clics(p['clics_ahora'])}"})

    for o in filas["oportunidades_ctr"][:MAX_POR_TIPO]:
        hallazgos.append({"tipo": "oportunidad_ctr", **o, "pagina": ruta(o["pagina"]),
                          "texto": f"\"{o['consulta']}\" → {ruta(o['pagina'])}: {num(o['impresiones'])} impresiones "
                                   f"y {clics(o['clics'])} en 28 días, posición {num(o['posicion'], 1)}"})

    nuevas = [c for c in filas["consultas_nuevas"] if c["impresiones"] >= UMBRAL_IMPRESIONES]
    for c in nuevas[:MAX_POR_TIPO]:
        hallazgos.append({"tipo": "consulta_nueva", **c,
                          "texto": f"Consulta nueva: \"{c['consulta']}\" ({num(c['impresiones'])} impresiones, {clics(c['clics'])})"})

    if filas["marca"]:
        partes = [f"{m['tipo']}: {clics(m['clics_ahora'])} y {num(m['impresiones_ahora'])} impresiones "
                  f"(antes {m['clics_antes']} y {num(m['impresiones_antes'])})" for m in filas["marca"]]
        hallazgos.append({"tipo": "marca_vs_sin_marca", "grupos": filas["marca"],
                          "texto": "Consultas visibles (sin las anónimas) · " + " · ".join(partes)})

    for i, h in enumerate(hallazgos, start=1):
        h["id"] = i
    datos["hallazgos"] = hallazgos
    return datos
