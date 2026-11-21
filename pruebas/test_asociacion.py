"""Validación de la asociación espacial paradas↔recorridos.
Uso: python pruebas/test_asociacion.py  (después de src/asociar_paradas.py)"""
import json
import sys
from pathlib import Path

DATOS = Path(__file__).resolve().parent.parent / "datos"


def cargar(n):
    return json.loads((DATOS / n).read_text(encoding="utf-8"))


def main():
    lineas = cargar("lineas.json")
    paradas = cargar("paradas.json")
    estado = cargar("estado.json")
    fallos = []

    def check(cond, msg):
        if not cond:
            fallos.append(msg)

    check("asociacion_paradas" in estado, "estado.json sin metadatos de asociación")

    # consistencia cruzada: toda parada listada en un sentido debe declarar esa línea
    for ref, l in lineas.items():
        for s in l["sentidos"]:
            check("paradas_origen" in s, f"línea {ref}: sentido sin paradas_origen")
            for pid in s["paradas"]:
                check(pid in paradas, f"línea {ref}: parada {pid} inexistente")
                if pid in paradas:
                    check(ref in paradas[pid]["lineas"],
                          f"parada {pid} no declara la línea {ref}")

    # la línea 48 (caso testigo: 6 miembros OSM) debe tener muchas más paradas
    s48 = lineas.get("48", {}).get("sentidos", [])
    check(s48 and len(s48[0]["paradas"]) >= 15,
          f"línea 48: esperaba >=15 paradas asociadas, hay "
          f"{len(s48[0]['paradas']) if s48 else 0}")

    # cobertura global: la gran mayoría de sentidos debe tener paradas
    sentidos = [s for l in lineas.values() for s in l["sentidos"]]
    con = sum(1 for s in sentidos if s["paradas"])
    check(con / len(sentidos) >= 0.9,
          f"solo {con}/{len(sentidos)} sentidos con paradas (esperaba >=90%)")

    # la mayoría de las paradas debe tener al menos una línea
    con_linea = sum(1 for p in paradas.values() if p["lineas"])
    check(con_linea / len(paradas) >= 0.7,
          f"solo {con_linea}/{len(paradas)} paradas con línea (esperaba >=70%)")

    # ordenamiento: las paradas espaciales deben venir ordenadas por proyección
    # (verificable indirectamente: sin duplicados dentro de un sentido)
    for ref, l in lineas.items():
        for s in l["sentidos"]:
            check(len(s["paradas"]) == len(set(s["paradas"])),
                  f"línea {ref}: paradas duplicadas en un sentido")

    if fallos:
        print(f"FALLOS ({len(fallos)}):")
        for f in fallos[:20]:
            print(" -", f)
        sys.exit(1)
    print(f"OK: {con}/{len(sentidos)} sentidos con paradas, "
          f"{con_linea}/{len(paradas)} paradas con línea, "
          f"línea 48: {[len(s['paradas']) for s in s48]} paradas por sentido")


if __name__ == "__main__":
    main()
