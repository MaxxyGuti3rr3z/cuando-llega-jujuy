"""Validación de los datos fase 0. Uso: python pruebas/test_datos.py"""
import json
import sys
from pathlib import Path

DATOS = Path(__file__).resolve().parent.parent / "datos"


def cargar(n):
    return json.loads((DATOS / n).read_text(encoding="utf-8"))


def main():
    fallos = []

    def check(cond, msg):
        if not cond:
            fallos.append(msg)

    lineas = cargar("lineas.json")
    paradas = cargar("paradas.json")
    estado = cargar("estado.json")
    gj = cargar("recorridos.geojson")

    check(len(lineas) >= 20, f"esperaba >=20 líneas, hay {len(lineas)}")
    check(len(paradas) >= 300, f"esperaba >=300 paradas, hay {len(paradas)}")
    check(estado["lineas"] == len(lineas), "estado.lineas no coincide con lineas.json")
    check(estado["paradas"] == len(paradas), "estado.paradas no coincide")
    check(gj["type"] == "FeatureCollection", "geojson sin type correcto")

    refs_geo = set()
    for ref, l in lineas.items():
        check(l["sentidos"], f"línea {ref} sin sentidos")
        for s in l["sentidos"]:
            check(len(s["geo"]) >= 10, f"línea {ref} sentido {s['relation_id']}: geometría muy corta ({len(s['geo'])} pts)")
            check(all(-24.5 < lat < -23.9 and -65.6 < lon < -65.0 for lat, lon in s["geo"]),
                  f"línea {ref}: coordenadas fuera de Jujuy")
            for pid in s["paradas"]:
                check(pid in paradas, f"línea {ref}: parada {pid} no existe en paradas.json")
            refs_geo.add(ref)

    for pid, p in paradas.items():
        check(-24.5 < p["lat"] < -23.9 and -65.6 < p["lon"] < -65.0,
              f"parada {pid}: coordenadas fuera de Jujuy")

    for f in gj["features"]:
        check(f["geometry"]["type"] == "LineString", "feature sin LineString")
        check(f["properties"]["ref"] in lineas, "feature con ref inexistente")
        check(len(f["geometry"]["coordinates"]) >= 10, "feature con pocos puntos")

    ops = {l["operador"] for l in lineas.values()}
    check("Santa Ana" in ops and "El Urbano" in ops, f"operadores esperados ausentes: {ops}")

    if fallos:
        print(f"FALLOS ({len(fallos)}):")
        for f in fallos[:20]:
            print(" -", f)
        sys.exit(1)
    print(f"OK: {len(lineas)} líneas, {len(paradas)} paradas, "
          f"{len(gj['features'])} recorridos, operadores {sorted(ops)}")


if __name__ == "__main__":
    main()
