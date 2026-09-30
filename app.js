/* ============================================================================
   app.js — Observatorio de Aeropuertos del Sur (Andalucía + Gibraltar) con
   Madrid y Barcelona como referencia.
   Datos: data/data.js, que escribe pipeline/build_data.py. assets/ no se toca.
   ========================================================================== */
(function () {
  'use strict';

  var D = window.DATOS || {};
  var F = Obs.fmt;
  var AE = D.aena || { x: [], pax: {}, ops: {}, carga_t: {} };
  var GIB = D.gib || { x: [], pax: [], anual: { x: [], pax: [], ofertadas: [] }, aeronaves: { x: [] }, carga_t: { x: [], v: [] } };
  var EU = D.euro || { x: [], ap: {} };
  var C = D.comun || { anual: { x: [], pax: {} }, verano: {}, ocupacion: { v: {} }, carga_t: {} };

  /* ------------------------------------------------------------ Aeropuertos */

  var AP = {
    AGP: { n: 'Málaga-Costa del Sol', c: 'Málaga' },
    SVQ: { n: 'Sevilla', c: 'Sevilla' },
    GRX: { n: 'F. G. L. Granada-Jaén', c: 'Granada-Jaén' },
    LEI: { n: 'Almería', c: 'Almería' },
    XRY: { n: 'Jerez de la Frontera', c: 'Jerez' },
    ODB: { n: 'Córdoba', c: 'Córdoba' },
    GIB: { n: 'Gibraltar', c: 'Gibraltar' },
    MAD: { n: 'Adolfo Suárez Madrid-Barajas', c: 'Madrid' },
    BCN: { n: 'Josep Tarradellas Barcelona-El Prat', c: 'Barcelona' }
  };
  var SUR = ['AGP', 'SVQ', 'GRX', 'LEI', 'XRY', 'GIB', 'ODB'];
  var TODOS = ['MAD', 'BCN', 'AGP', 'SVQ', 'GRX', 'LEI', 'XRY', 'GIB', 'ODB'];
  var AENA = ['AGP', 'SVQ', 'GRX', 'LEI', 'XRY', 'ODB', 'MAD', 'BCN'];
  var EURO = ['AGP', 'SVQ', 'GRX', 'LEI', 'XRY', 'MAD', 'BCN'];
  var nom = function (a) { return AP[a] ? AP[a].c : a; };

  /* ------------------------------------------------------------- Fuentes */

  var F_AENA = { txt: 'Aena · Informes mensuales de tráfico', url: 'https://www.aena.es/es/estadisticas/informes-mensuales.html' };
  var F_GIB = { txt: 'HM Government of Gibraltar · Air Traffic Survey ' + (GIB.informe || ''), url: GIB.url || 'https://www.gibraltar.gov.gi/statistics' };
  var F_EU = { txt: 'Eurostat · avia_par_es (tráfico por ruta)', url: EU.url || 'https://ec.europa.eu/eurostat/databrowser/view/avia_par_es/default/table' };
  var F_MIX = { txt: 'Aena · Gobierno de Gibraltar', url: 'https://www.aena.es/es/estadisticas/informes-mensuales.html' };
  var F_MIX_EU = { txt: 'Eurostat · Gobierno de Gibraltar', url: 'https://ec.europa.eu/eurostat/databrowser/view/avia_par_es/default/table' };

  var CH_MES = { txt: 'Mensual', tipo: 'live' };
  var CH_ANUAL = { txt: 'Anual' };
  var CH_COMUN = { txt: 'Los 9 aeropuertos' };

  /* ------------------------------------------------------------ Utilidades */

  var MES_CORTO = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
  var ult = function (a) { return a && a.length ? a[a.length - 1] : null; };
  var idxDe = function (x, p) { return (x || []).indexOf(p); };
  var mesAnterior = function (p, n) {          /* 'AAAA-MM' menos n meses */
    var y = +p.slice(0, 4), m = +p.slice(5) - n;
    while (m < 1) { m += 12; y -= 1; }
    return y + '-' + (m < 10 ? '0' : '') + m;
  };
  var ultimoMes = ult(AE.x);
  var anioAct = ultimoMes ? ultimoMes.slice(0, 4) : '';
  var mesesAct = ultimoMes ? +ultimoMes.slice(5) : 0;

  var valMes = function (serie, p) { var i = idxDe(AE.x, p); return i < 0 ? null : serie[i]; };
  var varInt = function (serie, p) {
    var c = valMes(serie, p), a = valMes(serie, mesAnterior(p, 12));
    return (c == null || !a) ? null : (c - a) / a * 100;
  };
  var sumaAnio = function (serie, y, hastaMes) {
    var s = 0, n = 0;
    AE.x.forEach(function (p, i) {
      if (p.slice(0, 4) === y && +p.slice(5) <= hastaMes && serie[i] != null) { s += serie[i]; n++; }
    });
    return n ? s : null;
  };
  /* Gibraltar alineado al eje mensual de Aena (termina donde termine su informe). */
  var gibEnEjeAena = AE.x.map(function (p) { var i = idxDe(GIB.x, p); return i < 0 ? null : GIB.pax[i]; });
  var anualDe = function (a, y) { var i = idxDe(C.anual.x, y); return i < 0 || !C.anual.pax[a] ? null : C.anual.pax[a][i]; };
  var ref = C.anio_ref;
  var ordenar = function (pares) { return pares.filter(function (p) { return p[1] != null; }).sort(function (a, b) { return b[1] - a[1]; }); };
  var barh = function (pares, nombre, yFormat) {
    var o = ordenar(pares);
    return { type: 'barh', x: o.map(function (p) { return p[0]; }), yFormat: yFormat || 'num',
             series: [{ name: nombre, data: o.map(function (p) { return p[1]; }) }] };
  };
  var opcionesAp = function (lista) { return lista.map(function (a) { return { v: a, txt: AP[a].n }; }); };
  var pctF = function (v) { return F.pct(v, 1); };

  /* ------------------------------------------------------------- Secciones */

  var SECCIONES = [

    /* ================================================= 1. Comparativa ==== */
    {
      id: 'comparativa', nombre: 'Comparativa',
      titulo: 'Indicadores comunes a los nueve aeropuertos',
      desc: 'Lo que se puede medir igual en todos: pasajeros, crecimiento, estacionalidad, ocupación de los aviones y carga. ' +
        'Aena publica cada mes; Gibraltar, una vez al año. Por eso las comparaciones anuales usan el último año cerrado para todos (' + (ref || '—') + ').',
      render: function () {
        var surTotal = SUR.reduce(function (s, a) { return s + (anualDe(a, ref) || 0); }, 0);
        var kpiMes = function (a) {
          return { label: nom(a) + ' · ' + Obs.periodo(ultimoMes, 'mes'), valor: valMes(AE.pax[a], ultimoMes),
                   delta: varInt(AE.pax[a], ultimoMes), deltaRef: 'interanual', serie: (AE.pax[a] || []).slice(-24) };
        };
        var gIdx = GIB.anual.x.length - 1;
        return {
          hero: {
            valor: surTotal, label: 'Pasajeros en los aeropuertos del sur en ' + ref + ' (Andalucía y Gibraltar)',
            extra: [
              { label: 'Cuota de Málaga en el sur', valor: surTotal ? anualDe('AGP', ref) / surTotal * 100 : null, formato: pctF },
              { label: 'Madrid-Barajas en ' + ref, valor: anualDe('MAD', ref) },
              { label: 'Barcelona-El Prat en ' + ref, valor: anualDe('BCN', ref) }
            ]
          },
          kpis: [
            kpiMes('AGP'), kpiMes('SVQ'), kpiMes('GRX'), kpiMes('LEI'), kpiMes('XRY'),
            { label: 'Gibraltar · año ' + (GIB.anual.x[gIdx] || ''), valor: GIB.anual.pax[gIdx],
              delta: gIdx > 0 ? (GIB.anual.pax[gIdx] - GIB.anual.pax[gIdx - 1]) / GIB.anual.pax[gIdx - 1] * 100 : null,
              deltaRef: 'sobre ' + (GIB.anual.x[gIdx - 1] || ''), serie: GIB.anual.pax.slice(-10) },
            kpiMes('MAD'), kpiMes('BCN')
          ],
          cards: [
            {
              titulo: 'Pasajeros en ' + ref, sub: 'Llegadas más salidas, año completo',
              chips: [CH_ANUAL, CH_COMUN], fuente: F_MIX, alto: 'tall',
              spec: barh(TODOS.map(function (a) { return [nom(a), anualDe(a, ref)]; }), 'Pasajeros')
            },
            {
              titulo: 'Recuperación frente a 2019', sub: 'Variación de pasajeros de ' + ref + ' sobre 2019, último año prepandemia',
              chips: [CH_ANUAL], fuente: F_MIX, alto: 'tall',
              nota: 'Córdoba se omite: parte de una base mínima (' + F.num(anualDe('ODB', '2019')) + ' pasajeros en 2019) y su ' +
                'variación (' + F.signo(anualDe('ODB', '2019') ? (anualDe('ODB', ref) - anualDe('ODB', '2019')) / anualDe('ODB', '2019') * 100 : null) + ' %) aplastaría al resto.',
              spec: barh(TODOS.filter(function (a) { return a !== 'ODB'; }).map(function (a) {
                var b = anualDe(a, '2019'), c = anualDe(a, ref);
                return [nom(a), b && c != null ? +((c - b) / b * 100).toFixed(1) : null];
              }), '% sobre 2019', pctF)
            },
            {
              titulo: 'Evolución anual de pasajeros', sub: 'Índice 2019 = 100',
              chips: [CH_ANUAL], fuente: F_MIX, ancho: 'full',
              nota: 'Base 100 en 2019 para comparar la trayectoria de aeropuertos de tamaños muy distintos. Córdoba se omite por su base mínima.',
              spec: {
                type: 'line', xType: 'anual', x: C.anual.x, yFormat: 'num', ref: 100, refLabel: '2019 = 100',
                series: ['MAD', 'BCN', 'AGP', 'SVQ', 'GRX', 'LEI', 'XRY', 'GIB'].map(function (a) {
                  var b = anualDe(a, '2019');
                  return { name: nom(a), data: C.anual.x.map(function (y) { var v = anualDe(a, y); return v != null && b ? +(v / b * 100).toFixed(1) : null; }) };
                })
              }
            },
            {
              titulo: 'Estacionalidad', sub: 'Peso de junio a septiembre sobre los pasajeros de ' + ref,
              chips: [CH_ANUAL, CH_COMUN], fuente: F_MIX, alto: 'tall',
              nota: 'Si el tráfico fuera plano todo el año, esos cuatro meses pesarían un 33,3 %. Cuanto más alto, más dependiente del verano.',
              spec: (function () { var s = barh(TODOS.map(function (a) { return [nom(a), C.verano[a]]; }), '% en verano', pctF); return s; })()
            },
            {
              titulo: 'Ocupación de los aviones', sub: 'Pasajeros a bordo sobre plazas ofertadas, año ' + ((C.ocupacion || {}).anio || '—'),
              chips: [CH_ANUAL], fuente: F_MIX_EU, alto: 'tall',
              nota: 'Último año con dato de Eurostat y del informe de Gibraltar a la vez. Aena no publica plazas; Córdoba no figura en Eurostat.',
              spec: barh(Object.keys((C.ocupacion || {}).v || {}).map(function (a) { return [nom(a), C.ocupacion.v[a]]; }), 'Ocupación', pctF)
            },
            {
              titulo: 'Reparto de pasajeros en el sur', sub: 'Andalucía y Gibraltar, ' + ref,
              chips: [CH_ANUAL], fuente: F_MIX,
              spec: (function () {
                var o = ordenar(SUR.map(function (a) { return [nom(a), anualDe(a, ref)]; }));
                return { type: 'donut', x: o.map(function (p) { return p[0]; }), yFormat: 'num',
                         series: [{ name: 'Pasajeros', data: o.map(function (p) { return p[1]; }) }] };
              })()
            },
            {
              titulo: 'Carga aérea en ' + ref, sub: 'Toneladas de mercancía (llegadas y salidas)',
              chips: [CH_ANUAL, CH_COMUN], fuente: F_MIX, alto: 'tall',
              nota: 'Granada, Almería, Jerez y Córdoba no mueven carga comercial significativa. Gibraltar: ' + F.num(C.carga_t.GIB) + ' t en ' + ref + '.',
              spec: barh(TODOS.map(function (a) { return [nom(a), C.carga_t[a]]; }), 'Toneladas')
            },
            {
              titulo: 'Pasajeros mensuales · grandes aeropuertos', sub: 'Madrid, Barcelona, Málaga y Sevilla',
              chips: [CH_MES], fuente: F_AENA, ancho: 'full',
              spec: {
                type: 'line', xType: 'mes', x: AE.x, yFormat: 'num', zoom: true, zoomDesde: '2023-01',
                series: ['MAD', 'BCN', 'AGP', 'SVQ'].map(function (a) { return { name: nom(a), data: AE.pax[a] }; })
              }
            },
            {
              titulo: 'Pasajeros mensuales · aeropuertos medianos y Gibraltar', sub: 'Granada-Jaén, Almería, Jerez y Gibraltar',
              chips: [CH_MES], fuente: F_MIX, ancho: 'full',
              nota: 'Gibraltar publica su serie mensual una vez al año: llega hasta ' + Obs.periodo(ult(GIB.x), 'mes') + '. Córdoba (entre 200 y 5.000 pasajeros al mes) no se ve a esta escala: está en la tabla de la pestaña Aena.',
              spec: {
                type: 'line', xType: 'mes', x: AE.x, yFormat: 'num', zoom: true, zoomDesde: '2023-01',
                series: [
                  { name: nom('GRX'), data: AE.pax.GRX },
                  { name: nom('LEI'), data: AE.pax.LEI },
                  { name: nom('XRY'), data: AE.pax.XRY },
                  { name: nom('GIB'), data: gibEnEjeAena }
                ]
              }
            }
          ]
        };
      }
    },

    /* ======================================================= 2. Aena ===== */
    {
      id: 'aena', nombre: 'Aena al mes',
      titulo: 'El pulso mensual de los aeropuertos de Aena',
      desc: 'Pasajeros, operaciones y carga de cada mes según el informe que Aena publica hacia mediados del mes siguiente. ' +
        'Los datos del año en curso son provisionales. Gibraltar no forma parte de la red de Aena.',
      render: function () {
        var ytd = function (a) {
          var c = sumaAnio(AE.pax[a], anioAct, mesesAct), p = sumaAnio(AE.pax[a], String(+anioAct - 1), mesesAct);
          return c != null && p ? +((c - p) / p * 100).toFixed(1) : null;
        };
        var comparaAnios = function (serieDe, nombre) {
          return function (a) {
            var s = serieDe(a) || [];
            var anios = ['2019', String(+anioAct - 1), anioAct];
            return {
              type: 'line', xType: 'cat', x: MES_CORTO, yFormat: 'num', xTodas: true,
              series: anios.map(function (y) {
                return { name: y, data: MES_CORTO.map(function (_, m) { return valMes(s, y + '-' + (m < 9 ? '0' : '') + (m + 1)); }) };
              })
            };
          };
        };
        var paxAnios = comparaAnios(function (a) { return AE.pax[a]; });
        var opsAnios = comparaAnios(function (a) { return AE.ops[a]; });
        var paxPorOp = function (a) {
          return {
            type: 'line', xType: 'mes', x: AE.x, yFormat: 'num', zoom: true, zoomDesde: '2022-01',
            series: [{ name: 'Pasajeros por operación', data: AE.x.map(function (_, i) {
              var p = AE.pax[a][i], o = AE.ops[a][i]; return p != null && o ? Math.round(p / o) : null; }) }]
          };
        };
        var carga = function (a) {
          return { type: 'area', xType: 'mes', x: AE.x, yFormat: 'num', unidad: 't',
                   series: [{ name: 'Toneladas', data: AE.carga_t[a] }] };
        };
        return {
          kpis: AENA.map(function (a) {
            return { label: nom(a) + ' · acumulado ' + anioAct, valor: sumaAnio(AE.pax[a], anioAct, mesesAct),
                     delta: ytd(a), deltaRef: 'sobre ene-' + MES_CORTO[mesesAct - 1] + ' ' + (+anioAct - 1),
                     serie: (AE.pax[a] || []).slice(-24) };
          }),
          cards: [
            {
              titulo: 'Pasajeros mes a mes', sub: anioAct + ' frente a ' + (+anioAct - 1) + ' y 2019',
              chips: [CH_MES], fuente: F_AENA, ancho: 'full',
              control: { label: 'Aeropuerto', valor: 'AGP', opciones: opcionesAp(AENA), spec: paxAnios },
              spec: paxAnios('AGP')
            },
            {
              titulo: 'Crecimiento en lo que va de año', sub: 'Pasajeros de enero a ' + MES_CORTO[mesesAct - 1] + ' ' + anioAct + ' sobre el mismo periodo de ' + (+anioAct - 1),
              chips: [CH_MES], fuente: F_AENA, alto: 'tall',
              nota: 'Córdoba se omite por su base mínima: ' + F.signo(ytd('ODB')) + ' % con ' + F.num(sumaAnio(AE.pax.ODB, anioAct, mesesAct)) + ' pasajeros.',
              spec: barh(AENA.filter(function (a) { return a !== 'ODB'; }).map(function (a) { return [nom(a), ytd(a)]; }), 'Variación', pctF)
            },
            {
              titulo: 'Operaciones mes a mes', sub: 'Aterrizajes y despegues · ' + anioAct + ' frente a ' + (+anioAct - 1) + ' y 2019',
              chips: [CH_MES], fuente: F_AENA,
              control: { label: 'Aeropuerto', valor: 'AGP', opciones: opcionesAp(AENA), spec: opsAnios },
              spec: opsAnios('AGP')
            },
            {
              titulo: 'Pasajeros por operación', sub: 'Tamaño medio y llenado de los vuelos',
              chips: [CH_MES], fuente: F_AENA,
              nota: 'Pasajeros entre aterrizajes y despegues. Incluye aviación general, así que en Córdoba y Jerez (escuelas de vuelo) sale muy bajo.',
              control: { label: 'Aeropuerto', valor: 'AGP', opciones: opcionesAp(AENA), spec: paxPorOp },
              spec: paxPorOp('AGP')
            },
            {
              titulo: 'Carga aérea mensual', sub: 'Toneladas de mercancía',
              chips: [CH_MES], fuente: F_AENA,
              control: { label: 'Aeropuerto', valor: 'SVQ', opciones: opcionesAp(['SVQ', 'AGP', 'MAD', 'BCN']), spec: carga },
              spec: carga('SVQ')
            },
            {
              titulo: 'Operaciones mensuales · aeropuertos andaluces', sub: 'Aterrizajes y despegues',
              chips: [CH_MES], fuente: F_AENA,
              spec: {
                type: 'line', xType: 'mes', x: AE.x, yFormat: 'num', zoom: true, zoomDesde: '2023-01',
                series: ['AGP', 'SVQ', 'XRY', 'GRX', 'LEI', 'ODB'].map(function (a) { return { name: nom(a), data: AE.ops[a] }; })
              }
            }
          ]
        };
      }
    },

    /* ============================================== 3. Mercados y rutas == */
    {
      id: 'mercados', nombre: 'Mercados y rutas',
      titulo: 'De dónde vienen y adónde van los vuelos',
      desc: 'Desglose por país y por ruta que solo publica Eurostat para los aeropuertos de la UE. ' +
        'El país es el del aeropuerto del otro extremo del vuelo, no la nacionalidad del pasajero.',
      render: function () {
        var anioEU = function (a) { return ult(((EU.ap[a] || {}).anios) || []); };
        var paises = function (a) {
          var e = EU.ap[a] || {}, y = anioEU(a), lista = (e.paises || {})[y] || [];
          var top = lista.slice(0, 7), resto = lista.slice(7).reduce(function (s, p) { return s + p[1]; }, 0);
          if (resto) top = top.concat([['Resto', resto]]);
          return { type: 'donut', x: top.map(function (p) { return p[0]; }), yFormat: 'num',
                   series: [{ name: 'Pasajeros ' + y, data: top.map(function (p) { return p[1]; }) }] };
        };
        var mercadosMes = function (a) {
          var e = EU.ap[a] || {}, m = e.mercados || {};
          var ss = [{ name: 'España (nacional)', data: e.nac }];
          Object.keys(m).forEach(function (k) { ss.push({ name: k, data: m[k] }); });
          ss.push({ name: 'Resto internacional', data: e.resto_intl });
          return { type: 'stack', xType: 'mes', x: EU.x, yFormat: 'num', series: ss };
        };
        var rutas = function (a) {
          var e = EU.ap[a] || {}, y = anioEU(a), r = ((e.rutas || {})[y] || []).slice(0, 12);
          return { type: 'barh', x: r.map(function (p) { return p[0] + ' (' + p[1] + ')'; }), yFormat: 'num',
                   series: [{ name: 'Pasajeros ' + y, data: r.map(function (p) { return p[2]; }) }] };
        };
        var ocup = function (a) {
          return { type: 'line', xType: 'mes', x: EU.x, yFormat: 'pct', yMin: 40, yMax: 100,
                   series: [{ name: 'Ocupación', data: (EU.ap[a] || {}).lf }] };
        };
        var yRef = anioEU('AGP');
        var cuota = function (a, pais) {
          var l = ((EU.ap[a] || {}).paises || {})[yRef] || [];
          var tot = l.reduce(function (s, p) { return s + p[1]; }, 0);
          var v = l.filter(function (p) { return p[0] === pais; })[0];
          return tot ? +((v ? v[1] : 0) / tot * 100).toFixed(1) : null;
        };
        var intl = function (a) { var c = cuota(a, 'España'); return c == null ? null : +(100 - c).toFixed(1); };
        var e = EU.ap.AGP || {}, lAGP = (e.paises || {})[yRef] || [];
        var totAGP = lAGP.reduce(function (s, p) { return s + p[1]; }, 0);
        return {
          nota: '<b>Retraso de la fuente:</b> España envía estos datos a Eurostat con más de un año de retraso; ahora llegan hasta ' +
            Obs.periodo(EU.ultimo, 'mes') + '. El colector los incorpora solos cuando Eurostat los publica. ' +
            'Gibraltar no figura en Eurostat, pero su informe confirma que todos sus vuelos regulares son con el Reino Unido.',
          notaTipo: 'warn',
          hero: {
            valor: cuota('AGP', 'Reino Unido'), formato: pctF,
            label: 'Peso del Reino Unido en los pasajeros de Málaga (' + yRef + ')',
            extra: [
              { label: 'Tráfico internacional de Málaga', valor: intl('AGP'), formato: pctF },
              { label: 'Países con vuelo directo a Málaga', valor: lAGP.length, formato: F.num },
              { label: 'Pasajeros de Málaga según Eurostat', valor: totAGP, formato: F.num }
            ]
          },
          cards: [
            {
              titulo: 'Peso del tráfico internacional', sub: 'Pasajeros en vuelos con el extranjero, ' + yRef,
              chips: [CH_ANUAL], fuente: F_MIX_EU, alto: 'tall',
              nota: 'Gibraltar: 100 %, porque todos sus vuelos regulares son con el Reino Unido.',
              spec: barh(EURO.map(function (a) { return [nom(a), intl(a)]; }).concat([[nom('GIB'), 100]]), '% internacional', pctF)
            },
            {
              titulo: 'Dependencia del mercado británico', sub: 'Pasajeros en vuelos con el Reino Unido, ' + yRef,
              chips: [CH_ANUAL], fuente: F_MIX_EU, alto: 'tall',
              spec: barh(EURO.map(function (a) { return [nom(a), cuota(a, 'Reino Unido')]; }).concat([[nom('GIB'), 100]]), '% Reino Unido', pctF)
            },
            {
              titulo: 'Pasajeros por país', sub: 'País del aeropuerto de origen o destino, último año completo',
              chips: [CH_ANUAL], fuente: F_EU,
              control: { label: 'Aeropuerto', valor: 'AGP', opciones: opcionesAp(EURO), spec: paises },
              spec: paises('AGP')
            },
            {
              titulo: 'Rutas con más pasajeros', sub: 'Aeropuerto del otro extremo, último año completo',
              chips: [CH_ANUAL], fuente: F_EU, alto: 'tall',
              control: { label: 'Aeropuerto', valor: 'AGP', opciones: opcionesAp(EURO), spec: rutas },
              spec: rutas('AGP')
            },
            {
              titulo: 'Mercados mes a mes', sub: 'Nacional y los seis principales países',
              chips: [CH_MES], fuente: F_EU, ancho: 'full', alto: 'tall',
              control: { label: 'Aeropuerto', valor: 'AGP', opciones: opcionesAp(EURO), spec: mercadosMes },
              spec: mercadosMes('AGP')
            },
            {
              titulo: 'Ocupación de los aviones', sub: 'Pasajeros a bordo sobre plazas ofertadas, mensual',
              chips: [CH_MES], fuente: F_EU,
              control: { label: 'Aeropuerto', valor: 'AGP', opciones: opcionesAp(EURO), spec: ocup },
              spec: ocup('AGP')
            }
          ]
        };
      }
    },

    /* ================================================== 4. Gibraltar ===== */
    {
      id: 'gibraltar', nombre: 'Gibraltar',
      titulo: 'Aeropuerto de Gibraltar',
      desc: 'La única fuente oficial es el informe anual de la oficina de estadística de Gibraltar, que recoge los pasajeros de pago en vuelos regulares y charter. ' +
        'Base militar británica con uso civil; no pertenece a la red de Aena.',
      render: function () {
        var A = GIB.anual, n = A.x.length - 1;
        var lfAnual = A.x.map(function (_, i) { return A.ofertadas[i] ? +(A.pax[i] / A.ofertadas[i] * 100).toFixed(1) : null; });
        var i19 = idxDe(A.x, '2019');
        var lfMes = GIB.x.map(function (_, i) { return GIB.ofertadas[i] ? +(GIB.pax[i] / GIB.ofertadas[i] * 100).toFixed(1) : null; });
        var ae = GIB.aeronaves || { x: [], regulares: [], no_regulares: [] };
        return {
          nota: '<b>Qué cambia con el tratado UE–Reino Unido (en aplicación provisional desde el 15 de julio de 2026).</b> ' +
            'Desaparecen los controles en la Verja y el control Schengen pasa al aeropuerto, a cargo de agentes españoles. ' +
            'El aeropuerto sigue siendo británico y no se integra en Aena, así que su dato seguirá llegando por esta vía. ' +
            'Su área de influencia pasa de 38.000 habitantes a unos 4 millones, y hay rutas europeas en negociación a partir de 2027: ' +
            'esta pestaña es donde se verá si el tratado mueve la aguja.',
          hero: {
            valor: A.pax[n], label: 'Pasajeros en ' + A.x[n],
            extra: [
              { label: 'Sobre ' + A.x[n - 1], valor: n > 0 ? (A.pax[n] - A.pax[n - 1]) / A.pax[n - 1] * 100 : null, formato: function (v) { return F.signo(v) + ' %'; } },
              { label: 'Sobre 2019', valor: i19 >= 0 ? (A.pax[n] - A.pax[i19]) / A.pax[i19] * 100 : null, formato: function (v) { return F.signo(v) + ' %'; } },
              { label: 'Ocupación de los aviones', valor: lfAnual[n], formato: pctF },
              { label: 'Aviones llegados en ' + ult(ae.x), valor: (ult(ae.regulares) || 0) + (ult(ae.no_regulares) || 0) }
            ]
          },
          cards: [
            {
              titulo: 'Pasajeros al mes', sub: 'Llegadas más salidas, vuelos regulares y charter',
              chips: [CH_ANUAL], fuente: F_GIB, ancho: 'full',
              nota: 'El informe da miles con un decimal: la resolución es de 100 pasajeros.',
              spec: { type: 'line', xType: 'mes', x: GIB.x, yFormat: 'num', zoom: true, zoomDesde: '2019-01',
                      series: [{ name: 'Pasajeros', data: GIB.pax }] }
            },
            {
              titulo: 'Pasajeros al año', sub: 'Serie oficial desde 2001',
              chips: [CH_ANUAL], fuente: F_GIB,
              spec: { type: 'bar', xType: 'anual', x: A.x, yFormat: 'num', series: [{ name: 'Pasajeros', data: A.pax }] }
            },
            {
              titulo: 'Ocupación de los aviones', sub: 'Plazas ocupadas sobre plazas ofertadas',
              chips: [CH_ANUAL], fuente: F_GIB,
              spec: { type: 'line', xType: 'anual', x: A.x, yFormat: 'pct', series: [{ name: 'Ocupación', data: lfAnual }] }
            },
            {
              titulo: 'Plazas ofertadas y ocupadas', sub: 'Capacidad de las aerolíneas frente a demanda',
              chips: [CH_ANUAL], fuente: F_GIB,
              spec: { type: 'line', xType: 'anual', x: A.x, yFormat: 'num', desdeCero: true,
                      series: [{ name: 'Plazas ofertadas', data: A.ofertadas }, { name: 'Pasajeros', data: A.pax }] }
            },
            {
              titulo: 'Aviones llegados', sub: 'Vuelos regulares y no regulares (charter, jets privados y avionetas)',
              chips: [CH_ANUAL], fuente: F_GIB,
              spec: { type: 'stack', xType: 'anual', x: ae.x, yFormat: 'num',
                      series: [{ name: 'Regulares', data: ae.regulares }, { name: 'No regulares', data: ae.no_regulares }] }
            },
            {
              titulo: 'Ocupación mensual', sub: 'Plazas ocupadas sobre ofertadas, cada mes',
              chips: [CH_ANUAL], fuente: F_GIB,
              spec: { type: 'line', xType: 'mes', x: GIB.x, yFormat: 'pct', zoom: true, zoomDesde: '2019-01',
                      series: [{ name: 'Ocupación', data: lfMes }] }
            },
            {
              titulo: 'Carga aérea', sub: 'Toneladas descargadas y cargadas',
              chips: [CH_ANUAL], fuente: F_GIB,
              nota: 'La carga comercial por avión es residual desde 2017.',
              spec: { type: 'bar', xType: 'anual', x: GIB.carga_t.x, yFormat: 'num', unidad: 't', series: [{ name: 'Toneladas', data: GIB.carga_t.v }] }
            }
          ]
        };
      }
    }
  ];

  /* ------------------------------------------------------------- Arranque */

  var AVION = '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.2c.4-.3.6-.7.5-1.2z"/></svg>';

  Obs.init({
    titulo: 'Observatorio de Aeropuertos del Sur',
    subtitulo: 'Andalucía y Gibraltar, con Madrid y Barcelona como referencia · fuentes oficiales, actualización automática',
    icono: AVION,
    secciones: SECCIONES,
    actualizado: (D.meta || {}).actualizado,
    fuentes: [F_AENA, F_EU, F_GIB],
    metodologia: 'Un proceso automático (<code>pipeline/build_data.py</code>) lee cada semana el Excel mensual de Aena, el conjunto ' +
      '<code>avia_par_es</code> de Eurostat y el informe anual de Gibraltar, y vuelca <code>data/data.js</code>. ' +
      'Los indicadores comunes usan el último año cerrado para todos, porque Gibraltar solo publica una vez al año. ' +
      'Cada tarjeta enlaza a su fuente y permite ver los datos en tabla y descargarlos en CSV.',
    pie: 'Los datos son de Aena, Eurostat y el Gobierno de Gibraltar; su tratamiento y presentación, de este observatorio. ' +
      'Los meses del año en curso de Aena son provisionales. Aena incluye aviación general; Eurostat, solo vuelos comerciales de pasajeros, ' +
      'por eso sus totales no coinciden exactamente.'
  });

  var m = D.meta || {};
  Obs.estado('Aena hasta ' + Obs.periodo(m.ultimo_periodo, 'mes') + ' · Eurostat hasta ' + Obs.periodo(m.ultimo_eurostat, 'mes') +
    ' · Gibraltar hasta ' + Obs.periodo(m.ultimo_gib, 'mes'), 'live');

})();
