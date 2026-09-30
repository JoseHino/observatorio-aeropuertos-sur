# -*- coding: utf-8 -*-
"""Gobierno de Gibraltar - Air Traffic Survey (Statistics Office).

Gibraltar no esta en la red de Aena ni en Eurostat (el Reino Unido dejo de
reportar tras el Brexit). La unica fuente oficial es el informe anual que la
oficina de estadistica presenta al Parlamento, en PDF:

    https://www.gibraltar.gov.gi/uploads/statistics/AAAA/Reports/Air Traffic Survey AAAA.pdf

Cada informe trae la serie completa desde 2001: tablas mensuales de plazas
ocupadas y ofertadas (en miles, un decimal) por destino - Reino Unido regular,
Espana y Tanger cuando hubo ruta, y vuelos charter -, la tabla 1.01 con los
totales anuales, la 6.01 con las llegadas de aeronaves y la 7.01 con la carga.

"Plazas ocupadas" = pasajeros de pago en vuelos regulares y charter. La
resolucion es de 100 pasajeros (miles con un decimal). La suma mensual cuadra
con la tabla anual desde 2008; antes faltan los charter, por eso la serie
mensual arranca en 2008.

Actualizacion: el informe de un ano sale a mitad del siguiente. Se prueba el
del ano en curso y, si no existe todavia, el del anterior.
"""

import io
import re
import urllib.parse

from .comun import get, ok, aviso

URL = "https://www.gibraltar.gov.gi/uploads/statistics/{a}/Reports/{f}"
FICHEROS = ["Air Traffic Survey {a}.pdf", "Air Traffic Survey Report {a}.pdf"]
MESES = ["January", "February", "March", "April", "May", "June", "July", "August",
         "September", "October", "November", "December"]
NUM = r"(?:-|\d+(?:\.\d+)?)"
PRIMER_ANIO_MENSUAL = 2008


def _v(s):
    return 0.0 if s == "-" else float(s)


def descargar(anio_actual):
    """(ano_del_informe, bytes) del informe mas reciente publicado."""
    for a in range(anio_actual, anio_actual - 3, -1):
        for f in FICHEROS:
            url = URL.format(a=a, f=urllib.parse.quote(f.format(a=a)))
            try:
                b = get(url, timeout=180, reintentos=2)
            except Exception:                                     # noqa: BLE001
                continue
            if b[:4] == b"%PDF":
                return a, b, url
    raise RuntimeError("no se encuentra ningun Air Traffic Survey reciente")


def interpretar(b):
    import pypdf
    r = pypdf.PdfReader(io.BytesIO(b))
    textos = [(p.extract_text() or "") for p in r.pages]
    mensual = {}                 # (tabla, 'AAAA-MM') -> (ocupadas, ofertadas) en miles
    anual, aeronaves, carga = {}, {}, {}
    for t in textos:
        lineas = [l.strip() for l in t.splitlines()]
        tabla, anios = None, None
        for l in lineas:
            m = re.match(r"^Table (\d\.\d\d)\b", l)
            if m:
                tabla, anios = m.group(1), None
                continue
            # Tablas 2.x/3.x (regulares) y 4.x/5.x (charter): cabecera con los
            # anos repetidos tres veces (ocupadas, ofertadas, % ocupacion).
            if tabla and tabla[0] in "2345" and anios is None:
                if re.fullmatch(r"(?:20\d\d\s*)+", l):
                    ys = re.findall(r"20\d\d", l)
                    anios = ys[:len(ys) // 3]
                continue
            if tabla and anios:
                mm = re.match(r"^(" + "|".join(MESES) + r")\s+(.*)$", l)
                if mm:
                    vals = re.findall(NUM, mm.group(2))
                    n = len(anios)
                    if len(vals) < 2 * n:
                        continue
                    mes = MESES.index(mm.group(1)) + 1
                    for i, y in enumerate(anios):
                        mensual[(tabla, f"{y}-{mes:02d}")] = (_v(vals[i]), _v(vals[n + i]))
        if "Table 1.01" in t:
            for l in lineas:
                m = re.match(r"^(20\d\d)\s+(.*)$", l)
                if m:
                    # Las columnas llegan a veces pegadas ("250.7216.8"): se
                    # separan por el patron de un decimal.
                    vals = re.findall(r"\d+\.\d|-", m.group(2))
                    if len(vals) >= 12:
                        v = [_v(x) for x in vals[:12]]
                        anual[m.group(1)] = {"llegadas": v[1], "salidas": v[7],
                                             "ofertadas": v[0] + v[6]}
        if "Table 6.01" in t:
            for l in lineas:
                m = re.match(r"^(20\d\d)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)$", l)
                if m:
                    aeronaves[m.group(1)] = [int(m.group(2).replace(",", "")),
                                             int(m.group(3).replace(",", ""))]
        if "Table 7.01" in t:
            for l in lineas:
                m = re.match(r"^(20\d\d)\s+(\d+)\s+(?:-|-?\d+\.\d)\s+(\d+)\b", l)
                if m:
                    carga[m.group(1)] = int(m.group(2)) + int(m.group(3))   # miles de kg
    return mensual, anual, aeronaves, carga


def recoger(anio_actual):
    anio_inf, b, url = descargar(anio_actual)
    mensual, anual, aeronaves, carga = interpretar(b)
    if not mensual or not anual:
        raise RuntimeError("el informe no trae las tablas esperadas")

    # Serie mensual: suma de todas las tablas (UK regular + Espana + Tanger + charter).
    ocup, ofer = {}, {}
    for (tabla, per), (u, o) in mensual.items():
        if int(per[:4]) < PRIMER_ANIO_MENSUAL:
            continue
        ocup[per] = ocup.get(per, 0) + u
        ofer[per] = ofer.get(per, 0) + o
    x = sorted(ocup)
    anios = sorted(anual)
    res = {
        "informe": anio_inf, "url": url,
        "x": x,
        "pax": [int(round(ocup[p] * 1000)) for p in x],
        "ofertadas": [int(round(ofer[p] * 1000)) for p in x],
        "anual": {
            "x": anios,
            "pax": [int(round((anual[a]["llegadas"] + anual[a]["salidas"]) * 1000)) for a in anios],
            "ofertadas": [int(round(anual[a]["ofertadas"] * 1000)) for a in anios],
        },
        "aeronaves": {"x": sorted(aeronaves),
                      "regulares": [aeronaves[a][0] for a in sorted(aeronaves)],
                      "no_regulares": [aeronaves[a][1] for a in sorted(aeronaves)]},
        "carga_t": {"x": sorted(carga), "v": [carga[a] for a in sorted(carga)]},
    }
    # Control de cuadre: la suma mensual del ultimo ano frente a la tabla anual.
    ult = anios[-1]
    suma = sum(v for p, v in zip(x, res["pax"]) if p.startswith(ult))
    oficial = res["anual"]["pax"][-1]
    if oficial and abs(suma - oficial) / oficial > 0.02:
        aviso(f"Gibraltar {ult}: la suma mensual ({suma:,}) no cuadra con la anual ({oficial:,})")
    ok(f"Gibraltar: informe {anio_inf}, {len(x)} meses ({x[0]} a {x[-1]}), {ult}: {oficial:,} pasajeros")
    return res
