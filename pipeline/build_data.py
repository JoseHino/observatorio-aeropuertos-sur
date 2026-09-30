# -*- coding: utf-8 -*-
"""Colector del Observatorio de Aeropuertos: descarga las fuentes y escribe data/data.js.

    python pipeline/build_data.py

Fuentes:
  - Aena (Excel mensual): pasajeros, operaciones y carga de cada aeropuerto.
  - Eurostat avia_par_es: rutas -> pais, nacional/internacional, ocupacion.
  - Gobierno de Gibraltar (Air Traffic Survey, PDF anual): el unico dato oficial
    del aeropuerto de Gibraltar.

Reglas del kit que se respetan:
  1. Solo lectura (GET).
  2. Un fallo de una fuente no tumba el panel: esa parte se conserva del
     data.js vigente y el resto se publica.
  3. Nunca se publica un data.js peor: si hay menos del 90 % de los valores
     publicados, se aborta con codigo 1.
"""

import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sources import aena, eurostat, gibraltar          # noqa: E402
from sources.comun import escribir_js, paso, ok, aviso  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = os.path.join(RAIZ, "data", "data.js")
CACHE_AENA = os.path.join(RAIZ, "pipeline", "cache", "aena.json")

AENA_IATA = list(aena.AEROPUERTOS)          # AGP SVQ GRX LEI XRY ODB MAD BCN
VERANO = ("06", "07", "08", "09")


def _rango(a, b):
    y, m = int(a[:4]), int(a[5:])
    while f"{y}-{m:02d}" <= b:
        yield f"{y}-{m:02d}"
        m += 1
        if m == 13:
            y, m = y + 1, 1


def _vigente():
    if not os.path.exists(SALIDA):
        return None
    try:
        txt = open(SALIDA, encoding="utf-8").read()
        m = re.search(r"window\.\w+\s*=\s*(\{.*\});?\s*$", txt, re.S)
        return json.loads(m.group(1)) if m else None
    except Exception:                                             # noqa: BLE001
        return None


def _contar(obj):
    if isinstance(obj, dict):
        return sum(_contar(v) for v in obj.values())
    if isinstance(obj, list):
        return sum(1 if isinstance(v, (int, float)) and not isinstance(v, bool) else _contar(v)
                   for v in obj)
    return 0


# ------------------------------------------------------------------ Recoleccion

def recoger(previo):
    hoy = datetime.date.today()
    datos = {"meta": {"actualizado": datetime.datetime.now(datetime.timezone.utc)
                      .strftime("%Y-%m-%dT%H:%M:%SZ")}}
    fallos = []

    # --- Aena ---------------------------------------------------------------
    paso("Aena - informes mensuales")
    try:
        cache, f_aena = aena.recoger(CACHE_AENA, hoy.year)
        fallos += f_aena
        meses = sorted(cache)
        x = list(_rango(meses[0], meses[-1]))
        serie = lambda clave, a, div=1: [  # noqa: E731
            (round(cache[m][clave][a] / div) if m in cache and a in cache[m][clave] else None) for m in x]
        datos["aena"] = {
            "x": x,
            "pax": {a: serie("pax", a) for a in AENA_IATA},
            "ops": {a: serie("ops", a) for a in AENA_IATA},
            "carga_t": {a: serie("carga", a, 1000) for a in AENA_IATA},   # kg -> t
        }
        ok(f"Aena: {x[0]} a {x[-1]}")
    except Exception as e:                                        # noqa: BLE001
        fallos.append(f"Aena: {e}")
        aviso(f"Aena: {e}")
        if previo and "aena" in previo:
            datos["aena"] = previo["aena"]

    # --- Gibraltar ----------------------------------------------------------
    paso("Gibraltar - Air Traffic Survey")
    try:
        datos["gib"] = gibraltar.recoger(hoy.year)
    except Exception as e:                                        # noqa: BLE001
        fallos.append(f"Gibraltar: {e}")
        aviso(f"Gibraltar: {e}")
        if previo and "gib" in previo:
            datos["gib"] = previo["gib"]

    # --- Eurostat -----------------------------------------------------------
    paso("Eurostat - rutas de los aeropuertos espanoles (avia_par_es)")
    try:
        datos["euro"] = eurostat.recoger()
    except Exception as e:                                        # noqa: BLE001
        fallos.append(f"Eurostat: {e}")
        aviso(f"Eurostat: {e}")
        if previo and "euro" in previo:
            datos["euro"] = previo["euro"]

    datos["comun"] = comun(datos)
    datos["meta"]["ultimo_periodo"] = (datos.get("aena") or {}).get("x", [None])[-1]
    datos["meta"]["ultimo_eurostat"] = (datos.get("euro") or {}).get("ultimo")
    datos["meta"]["ultimo_gib"] = ((datos.get("gib") or {}).get("x") or [None])[-1]
    datos["meta"]["fallos"] = fallos
    return datos, fallos


# ---------------------------------------------------- Indicadores comunes

def comun(d):
    """Indicadores homogeneos para los nueve aeropuertos (Aena + Gibraltar)."""
    ae, gib, eu = d.get("aena") or {}, d.get("gib") or {}, d.get("euro") or {}
    res = {}

    # Pasajeros anuales: solo anos completos (12 meses) en Aena.
    anual = {}
    if ae:
        for a in AENA_IATA:
            por = {}
            for m, v in zip(ae["x"], ae["pax"][a]):
                if v is not None:
                    por.setdefault(m[:4], []).append(v)
            anual[a] = {y: sum(v) for y, v in por.items() if len(v) == 12}
    if gib:
        anual["GIB"] = dict(zip(gib["anual"]["x"], gib["anual"]["pax"]))
    anios = sorted({y for a in anual.values() for y in a if y >= "2018"})
    res["anual"] = {"x": anios, "pax": {a: [anual[a].get(y) for y in anios] for a in anual}}

    # Ano de referencia comun: el ultimo con dato completo para todos.
    comunes = [y for y in anios if all(anual[a].get(y) is not None for a in anual)]
    ref = comunes[-1] if comunes else None
    res["anio_ref"] = ref

    # Estacionalidad: peso de junio-septiembre sobre el ano de referencia.
    est = {}
    if ref:
        for a in AENA_IATA:
            tot = anual[a][ref]
            ver = sum(v for m, v in zip(ae["x"], ae["pax"][a]) if m.startswith(ref) and m[5:] in VERANO and v)
            est[a] = round(ver / tot * 100, 1) if tot else None
        if gib:
            tot = sum(v for m, v in zip(gib["x"], gib["pax"]) if m.startswith(ref))
            ver = sum(v for m, v in zip(gib["x"], gib["pax"]) if m.startswith(ref) and m[5:] in VERANO)
            est["GIB"] = round(ver / tot * 100, 1) if tot else None
    res["verano"] = est

    # Ocupacion de los aviones: Eurostat (a bordo / plazas) y Gibraltar (ocupadas / ofertadas).
    lf = {"anio": None, "v": {}}
    if eu and gib and eu.get("ap"):
        anios_eu = set.intersection(*[set(v["anios"]) for v in eu["ap"].values()])
        anios_gib = {y for y, o in zip(gib["anual"]["x"], gib["anual"]["ofertadas"]) if o}
        cand = sorted(anios_eu & anios_gib)
        if cand:
            y = cand[-1]
            lf["anio"] = y
            for a, v in eu["ap"].items():
                lf["v"][a] = v["lf_anual"].get(y)
            i = gib["anual"]["x"].index(y)
            lf["v"]["GIB"] = round(gib["anual"]["pax"][i] / gib["anual"]["ofertadas"][i] * 100, 1)
    res["ocupacion"] = lf

    # Carga anual en toneladas (Gibraltar publica miles de kg, es decir, toneladas).
    carga = {}
    if ref and ae:
        for a in AENA_IATA:
            carga[a] = sum(v or 0 for m, v in zip(ae["x"], ae["carga_t"][a]) if m.startswith(ref))
        if gib and ref in gib["carga_t"]["x"]:
            carga["GIB"] = gib["carga_t"]["v"][gib["carga_t"]["x"].index(ref)]
    res["carga_t"] = carga
    return res


# ------------------------------------------------------------------------ Main

def main():
    print("== Observatorio de Aeropuertos - recoleccion ==")
    previo = _vigente()
    datos, fallos = recoger(previo)

    nuevos = _contar(datos)
    if previo is not None:
        antes = _contar(previo)
        if antes and nuevos < antes * 0.9:
            aviso(f"ABORTADO: {nuevos} valores frente a {antes} publicados "
                  f"({nuevos / antes:.0%}). No se sobrescribe data.js.")
            return 1

    paso("Escritura")
    escribir_js(SALIDA, datos)
    if fallos:
        aviso(f"{len(fallos)} incidencia(s): " + "; ".join(fallos))
    m = datos["meta"]
    print(f"\nListo. {nuevos} valores. Aena hasta {m['ultimo_periodo']}, "
          f"Eurostat hasta {m['ultimo_eurostat']}, Gibraltar hasta {m['ultimo_gib']}. "
          f"Ano comun de referencia: {datos['comun'].get('anio_ref')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
