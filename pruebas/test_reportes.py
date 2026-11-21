"""Tests de fase 1 (reportes). Uso: python pruebas/test_reportes.py
Usa una DB temporal: no toca datos/reportes.db.
"""
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import reportes as rep  # noqa: E402

PARADAS_LINEAS = {"p1": {"48", "40"}, "p2": {"40"}}


def main():
    fallos = []

    def check(cond, msg):
        if not cond:
            fallos.append(msg)

    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "test.db"
        con = rep.conectar(db)
        t0 = rep.ahora()

        # inserción válida
        rid = rep.insertar(con, parada_id="p1", linea_ref="48", tipo="paso",
                           ip="1.2.3.4", paradas_lineas=PARADAS_LINEAS, ts=t0)
        check(rid > 0, "inserción válida falló")

        # validaciones
        for kwargs, esperado in [
            (dict(tipo="cualquiera"), "tipo inválido"),
            (dict(parada_id="nope"), "parada inexistente"),
            (dict(linea_ref="99"), "no pasa por esa parada"),
        ]:
            base = dict(parada_id="p1", linea_ref="48", tipo="paso",
                        ip="9.9.9.9", paradas_lineas=PARADAS_LINEAS, ts=t0)
            base.update(kwargs)
            try:
                rep.insertar(con, **base)
                fallos.append(f"debía rechazar {kwargs}")
            except ValueError as e:
                check(esperado in str(e), f"mensaje inesperado: {e}")

        # demora requiere minutos
        try:
            rep.insertar(con, parada_id="p1", linea_ref="48", tipo="demora",
                         ip="9.9.9.9", paradas_lineas=PARADAS_LINEAS, ts=t0)
            fallos.append("demora sin minutos debía rechazarse")
        except ValueError as e:
            check("minutos" in str(e), f"mensaje inesperado: {e}")
        rid = rep.insertar(con, parada_id="p1", linea_ref="48", tipo="demora",
                           minutos=30, ip="9.9.9.9", paradas_lineas=PARADAS_LINEAS, ts=t0)
        check(rid > 0, "demora válida falló")

        # rate limit: misma IP dentro de 20 s
        try:
            rep.insertar(con, parada_id="p1", linea_ref="48", tipo="paso",
                         ip="1.2.3.4", paradas_lineas=PARADAS_LINEAS,
                         ts=t0 + timedelta(seconds=5))
            fallos.append("rate limit no actuó")
        except ValueError as e:
            check("esperá" in str(e), f"mensaje inesperado: {e}")
        # otra IP sí puede
        rid = rep.insertar(con, parada_id="p1", linea_ref="48", tipo="paso",
                           ip="5.6.7.8", paradas_lineas=PARADAS_LINEAS,
                           ts=t0 + timedelta(seconds=5))
        check(rid > 0, "otra IP debía poder reportar")

        # frecuencia: 4 pasos → intervalos 10, 12, 11 min → mediana 11
        for i, mins in enumerate([0, 10, 22, 33]):
            rep.insertar(con, parada_id="p2", linea_ref="40", tipo="paso",
                         ip=f"10.0.0.{i}", paradas_lineas=PARADAS_LINEAS,
                         ts=t0 - timedelta(minutes=40 - mins))
        f = rep.frecuencia(con, "p2", "40")
        check(f["reportes_paso"] == 4, f"esperaba 4 pasos, hay {f['reportes_paso']}")
        check(f["intervalo_mediano_min"] == 11.0,
              f"mediana esperada 11, dio {f['intervalo_mediano_min']}")
        check(f["confianza"] == "ok", "confianza debía ser ok")

        # sin datos suficientes → estimación None, honesto
        f2 = rep.frecuencia(con, "p1", "40")
        check(f2["intervalo_mediano_min"] is None, "sin pasos debía dar None")
        check("insuficiente" in f2["confianza"], "confianza debía ser insuficiente")

        # recientes no expone ip_hash
        rs = rep.recientes(con, parada_id="p1")
        check(rs and all("ip_hash" not in r for r in rs), "recientes expone ip_hash")
        check(rep.total(con) >= 6, "total inconsistente")
        con.close()

    if fallos:
        print(f"FALLOS ({len(fallos)}):")
        for f in fallos:
            print(" -", f)
        sys.exit(1)
    print("OK: validaciones, rate-limit, frecuencia (mediana 11 min), privacidad")


if __name__ == "__main__":
    main()
