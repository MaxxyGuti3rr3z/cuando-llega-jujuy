"""API fase 0: sirve los datos OSM procesados y la web estática.

Uso:  python -m uvicorn src.api:app --host 127.0.0.1 --port 8100
(o:   python src/api.py)
"""
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"


def cargar(nombre: str):
    p = DATOS / nombre
    if not p.exists():
        raise RuntimeError(f"Falta {p}. Ejecutá antes: python src/descargar_osm.py")
    return json.loads(p.read_text(encoding="utf-8"))


app = FastAPI(title="Cuándo Llega Jujuy — fase 0", version="0.1.0")
LINEAS = cargar("lineas.json")
PARADAS = cargar("paradas.json")
ESTADO = cargar("estado.json")


@app.get("/api/estado")
def estado():
    return ESTADO


@app.get("/api/lineas")
def lineas():
    return [
        {"ref": r, "nombre": v["nombre"], "operador": v["operador"],
         "sentidos": len(v["sentidos"])}
        for r, v in sorted(LINEAS.items(), key=lambda kv: (kv[1]["operador"], kv[0]))
    ]


@app.get("/api/lineas/{ref}")
def linea(ref: str):
    if ref not in LINEAS:
        raise HTTPException(404, "línea no encontrada")
    return LINEAS[ref]


@app.get("/api/paradas")
def paradas():
    return list(PARADAS.values())


@app.get("/api/recorridos.geojson")
def geojson():
    return cargar("recorridos.geojson")


app.mount("/", StaticFiles(directory=RAIZ / "web", html=True), name="web")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8100)
