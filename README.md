# Observatorio de Aeropuertos del Sur

Pasajeros, operaciones, carga, mercados y rutas de los aeropuertos de Andalucía
(Málaga, Sevilla, Granada-Jaén, Almería, Jerez, Córdoba) y de Gibraltar, con
Madrid-Barajas y Barcelona-El Prat como referencia.

**Web:** https://josehino.github.io/observatorio-aeropuertos-sur/

## Fuentes

| Fuente | Qué da | Frecuencia |
|---|---|---|
| Aena · informes mensuales (Excel) | pasajeros, operaciones y carga por aeropuerto | mensual (hacia el día 10-15) |
| Eurostat · `avia_par_es` | rutas → país, nacional/internacional, plazas y ocupación | mensual, con más de un año de retraso para España |
| Gobierno de Gibraltar · *Air Traffic Survey* (PDF) | pasajeros mensuales, plazas, aeronaves y carga | anual |

## Actualización

`.github/workflows/actualizar-datos.yml` ejecuta `python pipeline/build_data.py`
cada lunes y hace commit solo si cambian las cifras. `pipeline/cache/aena.json`
guarda los meses ya leídos de Aena para no descargarlos otra vez.
