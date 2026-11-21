"""Fase 0: descarga datos de transporte de OpenStreetMap (Overpass API) y genera
JSON reutilizable + GeoJSON de recorridos.

Fuente: colaboradores de OpenStreetMap, licencia ODbL (atribución obligatoria).
No depende de ninguna empresa de transporte: son datos abiertos mapeados por la
comunidad (wiki.openstreetmap.org/wiki/Jujuy/transporte_publico).

Uso:  python src/descargar_osm.py
Salida: datos/lineas.json, datos/paradas.json, datos/recorridos.geojson,
        datos/estado.json y copia cruda en datos/fuente/.
"""
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"
FUENTE = DATOS / "fuente"
# S.S. de Jujuy + Alto Comedero + Yala + Valles cercanos
BBOX = (-24.32, -65.45, -24.08, -65.18)  # (sur, oeste, norte, este)
OVERPASS = "https://overpass-api.de/api/interpreter"
UA = "cuando-llega-jujuy/0.1 (proyecto civico de datos abiertos)"


def overpass(query: str) -> dict:
    data = urllib.parse.urlencode({"data": query}).encode()
    req = urllib.request.Request(OVERPASS, data=data, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=240) as r:
        return json.load(r)


def normalizar_operador(op: str) -> str:
    op = (op or "desconocido").strip()
    if op.lower().startswith("santa ana"):
        return "Santa Ana"
    if op.lower().startswith("el urbano"):
        return "El Urbano"
    if "xibi" in op.lower():
        return "Xibi-Xibi (histórico)"
    return op


def main() -> None:
    DATOS.mkdir(exist_ok=True)
    FUENTE.mkdir(exist_ok=True)
    s, w, n, e = BBOX
    bbox = f"({s},{w},{n},{e})"

    print("1/3 Descargando relaciones route=bus (con geometria)...")
    raw_rel = overpass(f'[out:json][timeout:240];relation["route"="bus"]{bbox};out geom;')
    (FUENTE / "osm_relaciones.json").write_text(
        json.dumps(raw_rel, ensure_ascii=False), encoding="utf-8")

    print("2/3 Descargando paradas highway=bus_stop...")
    raw_par = overpass(f'[out:json][timeout:240];node["highway"="bus_stop"]{bbox};out body;')
    (FUENTE / "osm_paradas.json").write_text(
        json.dumps(raw_par, ensure_ascii=False), encoding="utf-8")

    print("3/3 Procesando...")
    paradas: dict = {}
    for el in raw_par.get("elements", []):
        if el.get("type") != "node":
            continue
        t = el.get("tags", {})
        paradas[str(el["id"])] = {
            "id": str(el["id"]),
            "lat": el["lat"],
            "lon": el["lon"],
            "nombre": t.get("name", "Parada sin nombre"),
            "lineas": [],
        }

    lineas: dict = {}
    features = []
    sentidos_ok = 0
    for el in raw_rel.get("elements", []):
        if el.get("type") != "relation":
            continue
        t = el.get("tags", {})
        ref = t.get("ref", "?").strip()
        operador = normalizar_operador(t.get("operator", ""))
        geo = []
        paradas_sentido = []
        for m in el.get("members", []):
            if m.get("type") == "way" and m.get("geometry"):
                geo.extend([[p["lat"], p["lon"]] for p in m["geometry"]])
            elif m.get("type") == "node" and str(m.get("role", "")).startswith("stop"):
                pid = str(m["ref"])
                if pid not in paradas and "lat" in m and "lon" in m:
                    paradas[pid] = {"id": pid, "lat": m["lat"], "lon": m["lon"],
                                    "nombre": "Parada (miembro de relación)", "lineas": []}
                if pid in paradas:
                    paradas_sentido.append(pid)
                    if ref not in paradas[pid]["lineas"]:
                        paradas[pid]["lineas"].append(ref)
        if not geo:
            continue  # relación sin geometría mapeada: se omite y se cuenta en estado
        sentidos_ok += 1
        sentido = {
            "relation_id": el["id"],
            "from": t.get("from", ""),
            "to": t.get("to", ""),
            "paradas": paradas_sentido,
            "geo": geo,
        }
        if ref not in lineas:
            lineas[ref] = {"ref": ref, "nombre": t.get("name", f"Línea {ref}"),
                           "operador": operador, "sentidos": []}
        lineas[ref]["sentidos"].append(sentido)
        features.append({
            "type": "Feature",
            "properties": {"ref": ref, "operador": operador,
                           "from": t.get("from", ""), "to": t.get("to", ""),
                           "relation_id": el["id"]},
            "geometry": {"type": "LineString",
                         "coordinates": [[lon, lat] for lat, lon in geo]},
        })

    for p in paradas.values():
        p["lineas"].sort()

    estado = {
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fuente": "OpenStreetMap contributors (Overpass API)",
        "licencia": "ODbL 1.0 — atribución obligatoria",
        "wiki": "https://wiki.openstreetmap.org/wiki/Jujuy/transporte_publico",
        "bbox": list(BBOX),
        "lineas": len(lineas),
        "sentidos_con_geometria": sentidos_ok,
        "relaciones_sin_geometria": len(raw_rel.get("elements", [])) - sentidos_ok,
        "paradas": len(paradas),
        "operadores": sorted({v["operador"] for v in lineas.values()}),
        "fase": 0,
        "nota": "Datos estáticos de recorridos y paradas. Sin tiempo real todavía.",
    }

    (DATOS / "lineas.json").write_text(json.dumps(lineas, ensure_ascii=False), encoding="utf-8")
    (DATOS / "paradas.json").write_text(json.dumps(paradas, ensure_ascii=False), encoding="utf-8")
    (DATOS / "recorridos.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False),
        encoding="utf-8")
    (DATOS / "estado.json").write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(estado, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
