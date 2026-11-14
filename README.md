# Los Bailarines del SAR 🛰️💃

**NASA Space Apps Challenge 2026** — reto *"The Earth's surface dance"* con datos de radar **NISAR** (NASA-ISRO).

> 🇬🇧 English version below.

## ¿Qué es?

Una aplicación web interactiva que muestra **cómo cambia la superficie de la Tierra** entre dos fechas, a partir de imágenes de radar de apertura sintética (SAR) de la misión NISAR. El radar ve de día y de noche, a través de nubes y humo, y es sensible a la rugosidad y a la humedad de la superficie.

**Demo en vivo:** https://fredyxander.github.io/bailarines-del-sar/

- **Zonas de estudio:** _por definir (2 zonas)_
- **Pregunta:** _por definir (una frase)_

## Estructura

| Carpeta | Contenido |
|---|---|
| `pipeline/` | Script en Python: lee 2 escenas, calcula el cambio y exporta capas para la web |
| `web/` | Frontend del observatorio (comparador antes/después) |
| `tutorial/` | Tutorial SAR en Python de la Agencia Espacial Canadiense, punto de partida |
| `docs/` | Datos usados, metodología y notas del equipo |
| `data/` | Escenas descargadas (no se suben al repo) |

## Uso rápido

```bash
pip install -r requirements.txt
python pipeline/change_detection.py data/fecha1.tif data/fecha2.tif --out web/layers
```

Luego abre `web/index.html` con un servidor local (`python -m http.server -d web`).

## Datos usados

Ver [`docs/DATOS.md`](docs/DATOS.md). Colección **NISAR PROVISIONAL** (17 jun – 23 oct 2026) desde [ASF Vertex](https://search.asf.alaska.edu). Hay un hueco del instrumento entre el 27 jul y el 10 ago 2026.

## Equipo

Tinjacá · Fredy · Santiago · Daira · Moneeb

## Use of AI tools

Parts of this repository were written with the assistance of AI coding tools. All method choices, polarization selections, thresholds and scientific interpretations were specified, reviewed and approved by the human team members named in this submission. AI-assisted components are limited to code drafting, documentation and workflow automation. No radar scene, measurement, result or figure in this project was generated, synthesised or altered by an AI tool.

## Créditos y licencia

- Código: [MIT](LICENSE). Avisos de terceros en [`NOTICE`](NOTICE).
- `tutorial/`: © Agencia Espacial Canadiense, licencia MIT propia ([`tutorial/LICENSE-CSA`](tutorial/LICENSE-CSA)). El uso de este material no implica respaldo de la CSA.
- Datos NISAR: NASA/JPL-Caltech e ISRO, distribuidos por ASF DAAC. NASA no respalda este proyecto.

---

## 🇬🇧 English

**Los Bailarines del SAR** ("The SAR Dancers") is an interactive web app for NASA Space Apps Challenge 2026. It shows **how Earth's surface changes** between two dates using NISAR synthetic aperture radar data. Live demo: https://fredyxander.github.io/bailarines-del-sar/

- `pipeline/change_detection.py` reads two co-registered scenes (any GDAL-readable raster: GeoTIFF or an HDF5 subdataset), computes the backscatter change in dB and exports PNG layers plus bounds for the web viewer.
- `web/` is a before/after swipe viewer.
- Data provenance (collection, CRID, date of each scene) lives in [`docs/DATOS.md`](docs/DATOS.md).

Quick start: see the commands above. Code is MIT licensed; `tutorial/` keeps the Canadian Space Agency's own MIT license.
