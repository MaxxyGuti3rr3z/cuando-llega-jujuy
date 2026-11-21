"""API: fase 0 (datos OSM) + fase 1 (reportes colaborativos).

Uso:  python -m uvicorn src.api:app --host 127.0.0.1 --port 8100
(o:   python src/api.py)
"""
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

try:
    from . import reportes as rep
except ImportError:  # ejecución directa: python src/api.py
    import reportes as rep

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"


def cargar(nombre: str):
    p = DATOS / nombre
    if not p.exists():
        raise RuntimeError(f"Falta {p}. Ejecutá antes: python src/descargar_osm.py")
    return json.loads(p.read_text(encoding="utf-8"))


app = FastAPI(title="Cuándo Llega Jujuy", version="0.2.0")
LINEAS = cargar("lineas.json")
PARADAS = cargar("paradas.json")
ESTADO = cargar("estado.json")
PARADAS_LINEAS = {pid: set(p["lineas"]) for pid, p in PARADAS.items()}


class ReporteIn(BaseModel):
    parada_id: str
    linea_ref: str
    tipo: str
    minutos: int | None = None


@app.get("/api/estado")
def estado():
    con = rep.conectar()
    try:
        return {**ESTADO, "reportes_total": rep.total(con)}
    finally:
        con.close()


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


@app.post("/api/reportes")
def crear_reporte(r: ReporteIn, request: Request):
    ip = request.client.host if request.client else ""
    con = rep.conectar()
    try:
        rid = rep.insertar(con, parada_id=r.parada_id, linea_ref=r.linea_ref,
                           tipo=r.tipo, minutos=r.minutos, ip=ip,
                           paradas_lineas=PARADAS_LINEAS)
        return {"ok": True, "id": rid}
    except ValueError as e:
        raise HTTPException(422, str(e))
    finally:
        con.close()


@app.get("/api/reportes")
def listar_reportes(parada_id: str | None = None, linea_ref: str | None = None,
                    ventana: int = 120):
    con = rep.conectar()
    try:
        return rep.recientes(con, parada_id, linea_ref, ventana_min=ventana)
    finally:
        con.close()


@app.get("/api/frecuencia/{ref}")
def frecuencia_linea(ref: str, parada_id: str, ventana: int = 180):
    if ref not in LINEAS:
        raise HTTPException(404, "línea no encontrada")
    if parada_id not in PARADAS_LINEAS or ref not in PARADAS_LINEAS[parada_id]:
        raise HTTPException(422, "esa línea no pasa por esa parada")
    con = rep.conectar()
    try:
        return rep.frecuencia(con, parada_id, ref, ventana_min=ventana)
    finally:
        con.close()


app.mount("/", StaticFiles(directory=RAIZ / "web", html=True), name="web")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8100)
