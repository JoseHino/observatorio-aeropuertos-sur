# -*- coding: utf-8 -*-
"""Eurostat - trafico aereo por ruta de los aeropuertos espanoles (avia_par_es).

Es la unica fuente abierta con el desglose por pais y por aeropuerto de
origen/destino del vuelo. Cada fila es una ruta aeropuerto-aeropuerto
(p. ej. ES_LEMG_UK_EGKK = Malaga - Londres Gatwick) con pasajeros
transportados (PAS_CRD), pasajeros a bordo (PAS_BRD), plazas ofertadas (ST_PAS)
y vuelos (CAF_PAS), mensual.

Lo que hay que decir siempre al usarla:
  - El pais es el del AEROPUERTO del otro extremo del vuelo, no la nacionalidad
    ni la residencia del pasajero. Un aleman que vuela desde Londres cuenta como
    Reino Unido.
  - Solo cuenta vuelos comerciales de pasajeros: sale algo por debajo de Aena,
    que incluye aviacion general y otros conceptos.
  - Espana reporta con retraso (a septiembre de 2026 llega a diciembre de 2024).
    El colector coge lo que haya; en cuanto Eurostat publique, entra solo.
  - Cordoba no figura: por debajo del umbral de reporte de la normativa.
"""

import collections
import gzip
import io

from .comun import get, ok

URL_DATOS = ("https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/"
             "avia_par_es?format=TSV&compressed=true")
URL_RUTAS = ("https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/codelist/"
             "ESTAT/AIRP_PR?format=TSV&lang=en")
URL_WEB = "https://ec.europa.eu/eurostat/databrowser/view/avia_par_es/default/table"

ICAO = {"LEMG": "AGP", "LEZL": "SVQ", "LEGR": "GRX", "LEAM": "LEI",
        "LEJR": "XRY", "LEMD": "MAD", "LEBL": "BCN"}
MEDIDAS = ("PAS_CRD", "PAS_BRD", "ST_PAS", "CAF_PAS")
DESDE = "2019-01"

PAISES = {
    "ES": "España", "UK": "Reino Unido", "DE": "Alemania", "FR": "Francia", "IT": "Italia",
    "NL": "Países Bajos", "BE": "Bélgica", "IE": "Irlanda", "CH": "Suiza", "PT": "Portugal",
    "DK": "Dinamarca", "SE": "Suecia", "NO": "Noruega", "FI": "Finlandia", "AT": "Austria",
    "PL": "Polonia", "US": "Estados Unidos", "MA": "Marruecos", "LU": "Luxemburgo",
    "CZ": "Chequia", "HU": "Hungría", "RO": "Rumanía", "BG": "Bulgaria", "EL": "Grecia",
    "TR": "Turquía", "IL": "Israel", "AE": "Emiratos Árabes", "QA": "Catar", "SA": "Arabia Saudí",
    "MX": "México", "CO": "Colombia", "AR": "Argentina", "BR": "Brasil", "CL": "Chile",
    "PE": "Perú", "VE": "Venezuela", "CU": "Cuba", "DO": "Rep. Dominicana", "CA": "Canadá",
    "CN": "China", "JP": "Japón", "KR": "Corea del Sur", "IS": "Islandia", "LT": "Lituania",
    "LV": "Letonia", "EE": "Estonia", "SK": "Eslovaquia", "SI": "Eslovenia", "HR": "Croacia",
    "MT": "Malta", "CY": "Chipre", "DZ": "Argelia", "TN": "Túnez", "EG": "Egipto",
    "SN": "Senegal", "RS": "Serbia", "UA": "Ucrania", "RU": "Rusia", "GE": "Georgia",
    "AM": "Armenia", "GI": "Gibraltar", "EC": "Ecuador", "UY": "Uruguay", "PA": "Panamá",
    "GT": "Guatemala", "SV": "El Salvador", "CR": "Costa Rica", "BO": "Bolivia",
    "PY": "Paraguay", "HN": "Honduras", "NG": "Nigeria", "ET": "Etiopía", "KZ": "Kazajistán",
    "IN": "India", "SG": "Singapur", "TH": "Tailandia", "JO": "Jordania", "LB": "Líbano",
    "KW": "Kuwait", "BH": "Baréin", "OM": "Omán", "AZ": "Azerbaiyán", "AL": "Albania",
    "MK": "Macedonia del Norte", "BA": "Bosnia", "ME": "Montenegro", "MD": "Moldavia",
    "CV": "Cabo Verde", "MR": "Mauritania", "GQ": "Guinea Ecuatorial",
}


def pais(c):
    return PAISES.get(c, c)


def _etiquetas_rutas():
    """{'UK_EGKK': 'London Gatwick'} a partir del codelist de rutas."""
    try:
        txt = get(URL_RUTAS, timeout=180).decode("utf-8")
    except Exception:                                             # noqa: BLE001
        return {}
    res = {}
    for linea in txt.splitlines():
        cod, _, lab = linea.partition("\t")
        if cod[3:7] not in ICAO or " - " not in lab:
            continue
        otro = lab.split(" - ", 1)[1].replace(" airport", "").strip()
        res.setdefault(cod[8:], otro.title().replace("/", " / "))
    return res


def recoger():
    b = get(URL_DATOS, timeout=300)
    f = io.TextIOWrapper(gzip.GzipFile(fileobj=io.BytesIO(b)), encoding="utf-8")
    cab = [c.strip() for c in f.readline().split("\t")]
    periodos = cab[1:]
    cols = [i for i, p in enumerate(periodos) if len(p) == 7 and p[4] == "-" and p >= DESDE]

    agg = collections.defaultdict(float)          # (iata, medida, pais, mes)
    rutas = collections.defaultdict(float)        # (iata, anio, ruta)
    for linea in f:
        partes = linea.rstrip("\n").split("\t")
        frec, _unit, medida, par = partes[0].split(",")
        if frec != "M" or medida not in MEDIDAS:
            continue
        iata = ICAO.get(par[3:7])
        if not iata:
            continue
        pc, ruta = par[8:10], par[8:]
        vals = partes[1:]
        for i in cols:
            v = vals[i].strip().split(" ")[0]           # quita banderas ("123 p")
            if not v or v == ":":
                continue
            v = float(v)
            agg[(iata, medida, pc, periodos[i])] += v
            if medida == "PAS_CRD":
                rutas[(iata, periodos[i][:4], ruta)] += v

    meses = sorted({k[3] for k in agg if k[1] == "PAS_CRD"})
    if not meses:
        raise RuntimeError("Eurostat no devuelve meses para los aeropuertos configurados")
    x = [m for m in _rango(meses[0], meses[-1])]
    etiquetas = _etiquetas_rutas()

    total_m = collections.defaultdict(float)
    pais_anio = collections.defaultdict(float)    # (iata, anio, pais) pasajeros
    for (a, med, pc, m), v in agg.items():
        total_m[(a, med, m, pc == "ES")] += v
        if med == "PAS_CRD":
            pais_anio[(a, m[:4], pc)] += v

    res = {"x": x, "ap": {}, "url": URL_WEB}
    for a in sorted(set(ICAO.values())):
        nac = [total_m.get((a, "PAS_CRD", m, True)) for m in x]
        intl = [total_m.get((a, "PAS_CRD", m, False)) for m in x]
        brd = [(total_m.get((a, "PAS_BRD", m, True), 0) + total_m.get((a, "PAS_BRD", m, False), 0)) for m in x]
        st = [(total_m.get((a, "ST_PAS", m, True), 0) + total_m.get((a, "ST_PAS", m, False), 0)) for m in x]
        vuelos = [(total_m.get((a, "CAF_PAS", m, True), 0) + total_m.get((a, "CAF_PAS", m, False), 0)) for m in x]
        lf = [round(b_ / s_ * 100, 1) if s_ else None for b_, s_ in zip(brd, st)]

        # Anos completos disponibles para ese aeropuerto.
        por_anio = collections.defaultdict(int)
        for m, n_, i_ in zip(x, nac, intl):
            if (n_ or 0) + (i_ or 0) > 0:
                por_anio[m[:4]] += 1
        anios = sorted(y for y, n in por_anio.items() if n == 12)
        if not anios:
            continue

        paises_anual, rutas_anual, lf_anual = {}, {}, {}
        for y in anios:
            pa = {pc: v for (aa, yy, pc), v in pais_anio.items() if aa == a and yy == y}
            paises_anual[y] = [[pais(c), int(v)] for c, v in sorted(pa.items(), key=lambda t: -t[1])]
            top = sorted(((v, r) for (aa, yy, r), v in rutas.items() if aa == a and yy == y), reverse=True)[:15]
            rutas_anual[y] = [[etiquetas.get(r, r[3:]), pais(r[:2]), int(v)] for v, r in top]
            sb = sum(b_ for m, b_ in zip(x, brd) if m.startswith(y))
            ss = sum(s_ for m, s_ in zip(x, st) if m.startswith(y))
            lf_anual[y] = round(sb / ss * 100, 1) if ss else None

        # Serie mensual de los 6 mercados internacionales principales del ultimo ano.
        ult = anios[-1]
        top6 = [pc for pc, _ in sorted(
            ((pc, v) for (aa, yy, pc), v in pais_anio.items() if aa == a and yy == ult and pc != "ES"),
            key=lambda t: -t[1])[:6]]
        mercados = {pais(c): [int(agg.get((a, "PAS_CRD", c, m), 0)) for m in x] for c in top6}
        resto = []
        for i, m in enumerate(x):
            t = intl[i] or 0
            resto.append(int(max(0, t - sum(v[i] for v in mercados.values()))))

        res["ap"][a] = {
            "nac": [int(v) if v else None for v in nac],
            "intl": [int(v) if v else None for v in intl],
            "vuelos": [int(v) if v else None for v in vuelos],
            "lf": lf,
            "anios": anios,
            "paises": paises_anual,
            "rutas": rutas_anual,
            "lf_anual": lf_anual,
            "mercados": mercados,
            "resto_intl": resto,
        }
        ok(f"Eurostat {a}: {anios[0]}-{ult}, ocupacion {ult} {lf_anual[ult]} %")
    res["ultimo"] = x[-1]
    return res


def _rango(a, b):
    y, m = int(a[:4]), int(a[5:])
    while f"{y}-{m:02d}" <= b:
        yield f"{y}-{m:02d}"
        m += 1
        if m == 13:
            y, m = y + 1, 1
