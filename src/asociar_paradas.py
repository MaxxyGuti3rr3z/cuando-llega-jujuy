"""Fase 0.5: asociación espacial paradas ↔ recorridos.

Muchas relaciones OSM tienen pocos miembros 'stop' aunque las paradas existen
como nodos sueltos (ej. línea 48: 6 miembros). Este script matchea cada parada
contra la geometría de cada sentido: si está a <= UMBRAL_M metros del trazado,
la sirve esa línea. Las paradas asociadas se ORDENAN por su proyección sobre el
recorrido (distancia acumulada), lo que da la secuencia real de paradas —
insumo directo para estimar frecuencias/ETA en fase 1.

Uso:  python src/asociar_paradas.py [--umbral 25]
Lee:  datos/lineas.json, datos/paradas.json
Escribe: los mismos archivos actualizados + metadatos en datos/estado.json
"""
import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"
M_POR_GRADO_LAT = 110540.0
M_POR_GRADO_LON = 111320.0


def dist_pt_seg(px, py, ax, ay, bx, by):
    """Distancia punto-segmento en metros + posición proyectada (0..1)."""
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    if l2 == 0:
        return math.hypot(px - ax, py - ay), 0.0
    t = ((px - ax) * dx + (py - ay) * dy) / l2
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy)), t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--umbral", type=float, default=25.0, help="metros máximos al trazado")
    args = ap.parse_args()
    umbral = args.umbral

    lineas = json.loads((DATOS / "lineas.json").read_text(encoding="utf-8"))
    paradas = json.loads((DATOS / "paradas.json").read_text(encoding="utf-8"))
    estado = json.loads((DATOS / "estado.json").read_text(encoding="utf-8"))

    lat0 = sum(p["lat"] for p in paradas.values()) / len(paradas)
    cos_lat = math.cos(math.radians(lat0))

    def a_metros(lat, lon):
        return lon * M_POR_GRADO_LON * cos_lat, lat * M_POR_GRADO_LAT

    # Pre-procesar cada sentido: segmentos en metros + bbox + distancia acumulada
    sentidos = []  # (ref, idx_sentido, segs, bbox, paradas_miembro)
    for ref, l in lineas.items():
        for i, s in enumerate(l["sentidos"]):
            pts = [a_metros(lat, lon) for lat, lon in s["geo"]]
            segs = []
            cum = 0.0
            for a, b in zip(pts, pts[1:]):
                largo = math.hypot(b[0] - a[0], b[1] - a[1])
                segs.append((a[0], a[1], b[0], b[1], cum, largo))
                cum += largo
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            margen = umbral + 5
            bbox = (min(xs) - margen, min(ys) - margen, max(xs) + margen, max(ys) + margen)
            sentidos.append((ref, i, segs, bbox, set(s["paradas"])))

    paradas_m = {pid: a_metros(p["lat"], p["lon"]) for pid, p in paradas.items()}

    total_antes = sum(len(s["paradas"]) for l in lineas.values() for s in l["sentidos"])
    nuevas = 0
    for ref, i, segs, (x0, y0, x1, y1), miembros in sentidos:
        candidatas = [(pid, xy) for pid, xy in paradas_m.items()
                      if x0 <= xy[0] <= x1 and y0 <= xy[1] <= y1]
        asociadas = []  # (posicion, pid)
        for pid, (px, py) in candidatas:
            mejor_d, mejor_pos = float("inf"), 0.0
            for ax, ay, bx, by, cum, largo in segs:
                d, t = dist_pt_seg(px, py, ax, ay, bx, by)
                if d < mejor_d:
                    mejor_d, mejor_pos = d, cum + t * largo
                    if d <= 1.0:
                        break  # suficientemente cerca: no hace falta seguir
            if mejor_d <= umbral:
                asociadas.append((mejor_pos, pid))
        asociadas.sort()
        orden = [pid for _, pid in asociadas]
        s = lineas[ref]["sentidos"][i]
        antes = len(s["paradas"])
        # unión: miembros OSM originales + espaciales, en orden del recorrido
        conjunto = set(orden) | miembros
        s["paradas"] = [pid for pid in orden if pid in conjunto] + \
                       [pid for pid in s["paradas"] if pid not in set(orden)]
        s["paradas_origen"] = {"miembros_osm": len(miembros), "espaciales": len(orden)}
        nuevas += max(0, len(s["paradas"]) - antes)
        for pid in s["paradas"]:
            if ref not in paradas[pid]["lineas"]:
                paradas[pid]["lineas"].append(ref)

    for p in paradas.values():
        p["lineas"].sort()

    con_linea = sum(1 for p in paradas.values() if p["lineas"])
    sin_paradas = sum(1 for l in lineas.values() for s in l["sentidos"] if not s["paradas"])
    total_despues = sum(len(s["paradas"]) for l in lineas.values() for s in l["sentidos"])
    estado["asociacion_paradas"] = {
        "fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "umbral_m": umbral,
        "asociaciones_antes": total_antes,
        "asociaciones_despues": total_despues,
        "paradas_con_al_menos_una_linea": con_linea,
        "sentidos_sin_paradas": sin_paradas,
    }

    (DATOS / "lineas.json").write_text(json.dumps(lineas, ensure_ascii=False), encoding="utf-8")
    (DATOS / "paradas.json").write_text(json.dumps(paradas, ensure_ascii=False), encoding="utf-8")
    (DATOS / "estado.json").write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(estado["asociacion_paradas"], ensure_ascii=False, indent=1))
    print(f"paradas con línea: {con_linea}/{len(paradas)}")


if __name__ == "__main__":
    main()
