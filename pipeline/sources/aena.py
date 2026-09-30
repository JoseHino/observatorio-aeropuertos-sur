# -*- coding: utf-8 -*-
"""Aena - informes mensuales de trafico (pasajeros, operaciones y mercancia).

Aena no tiene API publica: cada mes cuelga un Excel en
    https://www.aena.es/es/estadisticas/informes-mensuales.html?anio=AAAA
enlazado por un identificador de blob. El colector lee la pagina de cada ano,
localiza el Excel de cada mes por la etiqueta del enlace (no por la posicion:
Aena alterna el orden PDF/XLS) y lo interpreta.

Trampas ya vistas:
  - 2018-2021 son .xls antiguos (BIFF) y 2022 en adelante .xlsx; se detecta por
    la firma del fichero, no por la extension (la URL no la trae).
  - La columna del total no esta siempre pegada a la del nombre (en 2018-2020
    hay columnas combinadas en medio), asi que se localiza por su cabecera.
  - Los nombres cambian con los anos (FGL GRANADA-JAEN, BARCELONA-EL PRAT J.T.):
    se casan por un fragmento estable del nombre.
  - Aena corta si se le piden varios ficheros en paralelo: descarga secuencial.

Cache: pipeline/cache/aena.json guarda cada mes ya interpretado junto al id del
blob. En cada ejecucion solo se descargan los meses nuevos o aquellos cuyo blob
ha cambiado (Aena sustituye el provisional por el definitivo).
"""

import io
import json
import os
import re
import time
import unicodedata

from .comun import get, ok, aviso

AEROPUERTOS = {   # codigo IATA -> fragmento estable del nombre Aena (normalizado)
    "AGP": "MALAGA",
    "SVQ": "SEVILLA",
    "GRX": "GRANADA",
    "LEI": "ALMERIA",
    "XRY": "JEREZ",
    "ODB": "CORDOBA",
    "MAD": "MADRID-BARAJAS",
    "BCN": "BARCELONA",
}

URL_ANIO = "https://www.aena.es/es/estadisticas/informes-mensuales.html?anio={}"
URL_BLOB = ("https://www.aena.es/sites/Satellite?blobcol=urldata&blobkey=id"
            "&blobtable=MungoBlobs&blobwhere={}&ssbinary=true")
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
PRIMER_ANIO = 2018
UA_NAV = {"User-Agent": "Mozilla/5.0 (observatorio-aeropuertos; solo lectura)"}


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return " ".join(s.upper().split())


# ------------------------------------------------------------------ Listado

def listar_anio(anio):
    """{'AAAA-MM': id_blob_excel} publicado en la pagina de ese ano."""
    html = get(URL_ANIO.format(anio), headers=UA_NAV).decode("utf-8", "ignore")
    res = {}
    patron = r"Informe ([a-zA-Z]+) (\d{4})(.*?)(?=Informe [a-zA-Z]+ \d{4}|$)"
    for m in re.finditer(patron, html, re.S):
        mes, a, bloque = m.group(1).lower(), m.group(2), m.group(3)
        if mes not in MESES or int(a) != anio:
            continue
        for bid, etiqueta in re.findall(
                r'href="/sites/Satellite\?[^"]*blobwhere=(\d+)[^"]*"[^>]*>(.*?)</a>', bloque, re.S):
            if "XLS" in re.sub(r"<[^>]+>", " ", etiqueta).upper():
                res[f"{a}-{MESES.index(mes) + 1:02d}"] = bid
    return res


# --------------------------------------------------------------- Interprete

def _filas(b):
    if b[:2] == b"PK":
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(b), data_only=True, read_only=True)
        hojas = [(ws.title, [list(r) for r in ws.iter_rows(values_only=True)]) for ws in wb.worksheets]
    else:
        import xlrd
        wb = xlrd.open_workbook(file_contents=b)
        hojas = [(s.name, [s.row_values(i) for i in range(s.nrows)]) for s in wb.sheets()]
    for nombre, filas in hojas:
        n = _norm(nombre)
        if "ACUM" in n or "MOZART" in n:      # acumulado del ano y metadatos
            continue
        return filas
    raise ValueError("el Excel no trae hoja mensual")


def interpretar(b):
    """{'pax': {IATA: n}, 'ops': {...}, 'carga': {...}} de un Excel mensual."""
    bloques = None
    out = {"pax": {}, "ops": {}, "carga": {}}
    for fila in _filas(b):
        celdas = [_norm(c) if isinstance(c, str) else c for c in fila]
        if bloques is None:
            nombres = [i for i, c in enumerate(celdas) if c == "AEROPUERTOS"]
            totales = [i for i, c in enumerate(celdas) if c == "TOTAL"]
            if len(nombres) == 3 and len(totales) == 3:
                bloques = list(zip(nombres, totales))
            continue
        for clave, (cn, cv) in zip(("pax", "ops", "carga"), bloques):
            if cv >= len(celdas):
                continue
            nombre, valor = celdas[cn], celdas[cv]
            if not isinstance(nombre, str) or not isinstance(valor, (int, float)):
                continue
            for iata, frag in AEROPUERTOS.items():
                if frag in nombre and iata not in out[clave]:
                    out[clave][iata] = int(round(valor))
    if bloques is None:
        raise ValueError("no se encuentra la cabecera de la tabla")
    return out


# ------------------------------------------------------------------ Colector

def recoger(ruta_cache, anio_actual):
    cache = {}
    if os.path.exists(ruta_cache):
        cache = json.load(open(ruta_cache, encoding="utf-8"))
    cambios = 0
    fallos = []
    for anio in range(PRIMER_ANIO, anio_actual + 1):
        # Los anos cerrados y completos en cache no se vuelven a consultar.
        completos = all(f"{anio}-{m:02d}" in cache for m in range(1, 13))
        if completos and anio < anio_actual - 1:
            continue
        try:
            publicados = listar_anio(anio)
        except Exception as e:                                    # noqa: BLE001
            fallos.append(f"Aena listado {anio}: {e}")
            aviso(f"listado {anio}: {e}")
            continue
        for mes, bid in sorted(publicados.items()):
            if mes in cache and cache[mes].get("blob") == bid:
                continue
            try:
                datos = interpretar(get(URL_BLOB.format(bid), headers=UA_NAV))
                faltan = [a for a in AEROPUERTOS if a not in datos["pax"]]
                if faltan:
                    raise ValueError("faltan " + ", ".join(faltan))
                datos["blob"] = bid
                cache[mes] = datos
                cambios += 1
                ok(f"Aena {mes}: Malaga {datos['pax']['AGP']:,} pasajeros")
            except Exception as e:                                # noqa: BLE001
                fallos.append(f"Aena {mes}: {e}")
                aviso(f"{mes}: {e}")
            time.sleep(0.6)
    if cambios:
        os.makedirs(os.path.dirname(ruta_cache), exist_ok=True)
        with open(ruta_cache, "w", encoding="utf-8") as f:
            json.dump(dict(sorted(cache.items())), f, ensure_ascii=False, indent=0)
    ok(f"Aena: {len(cache)} meses en cache ({cambios} nuevos o revisados)")
    return cache, fallos
