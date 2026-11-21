"""Fase 1: reportes colaborativos de usuarios (SQLite, stdlib).

Tipos:
- paso:    "pasó el cole ahora" → base para estimar frecuencia real
- colmado: "va lleno"
- demora:  "no viene hace X minutos" (minutos obligatorio, 1..180)

Privacidad: se guarda un hash truncado de la IP solo para rate-limit;
nunca la IP cruda ni datos personales. Sin cuentas ni login.
"""
import hashlib
import sqlite3
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DB_DEFAULT = RAIZ / "datos" / "reportes.db"
TIPOS = {"paso", "colmado", "demora"}
LIMITE_SEGUNDOS = 20     # 1 reporte cada 20 s por IP
LIMITE_HORA = 40         # máx 40 reportes/hora por IP


def ahora() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def conectar(db_path=None) -> sqlite3.Connection:
    p = Path(db_path) if db_path else DB_DEFAULT
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p)
    con.row_factory = sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS reportes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        parada_id TEXT NOT NULL,
        linea_ref TEXT NOT NULL,
        tipo TEXT NOT NULL,
        minutos INTEGER,
        ip_hash TEXT NOT NULL)""")
    con.execute("CREATE INDEX IF NOT EXISTS idx_parada_ts ON reportes(parada_id, ts)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_linea_ts ON reportes(linea_ref, ts)")
    con.commit()
    return con


def hash_ip(ip: str) -> str:
    return hashlib.sha256((ip or "?").encode()).hexdigest()[:16]


def insertar(con, *, parada_id: str, linea_ref: str, tipo: str,
             minutos=None, ip: str = "", paradas_lineas: dict,
             ts: datetime | None = None) -> int:
    """Valida + rate-limit + inserta. ValueError con mensaje en español si falla."""
    if tipo not in TIPOS:
        raise ValueError(f"tipo inválido: {tipo} (usar: paso, colmado, demora)")
    if parada_id not in paradas_lineas:
        raise ValueError("parada inexistente")
    if linea_ref not in paradas_lineas[parada_id]:
        raise ValueError(f"la línea {linea_ref} no pasa por esa parada")
    if tipo == "demora":
        if minutos is None or not (1 <= int(minutos) <= 180):
            raise ValueError("demora requiere minutos entre 1 y 180")
        minutos = int(minutos)
    else:
        minutos = None

    t = ts or ahora()
    ih = hash_ip(ip)
    desde_20s = iso(t - timedelta(seconds=LIMITE_SEGUNDOS))
    desde_1h = iso(t - timedelta(hours=1))
    n20 = con.execute("SELECT COUNT(*) c FROM reportes WHERE ip_hash=? AND ts>=?",
                      (ih, desde_20s)).fetchone()["c"]
    if n20:
        raise ValueError(f"esperá {LIMITE_SEGUNDOS} segundos entre reportes")
    n1h = con.execute("SELECT COUNT(*) c FROM reportes WHERE ip_hash=? AND ts>=?",
                      (ih, desde_1h)).fetchone()["c"]
    if n1h >= LIMITE_HORA:
        raise ValueError("límite de reportes por hora alcanzado, gracias por colaborar")
    cur = con.execute(
        "INSERT INTO reportes(ts, parada_id, linea_ref, tipo, minutos, ip_hash) "
        "VALUES(?,?,?,?,?,?)", (iso(t), parada_id, linea_ref, tipo, minutos, ih))
    con.commit()
    return cur.lastrowid


def recientes(con, parada_id: str | None = None, linea_ref: str | None = None,
              ventana_min: int = 120, limite: int = 50) -> list[dict]:
    desde = iso(ahora() - timedelta(minutes=ventana_min))
    q = "SELECT ts, parada_id, linea_ref, tipo, minutos FROM reportes WHERE ts>=?"
    args: list = [desde]
    if parada_id:
        q += " AND parada_id=?"
        args.append(parada_id)
    if linea_ref:
        q += " AND linea_ref=?"
        args.append(linea_ref)
    q += " ORDER BY ts DESC LIMIT ?"
    args.append(limite)
    return [dict(r) for r in con.execute(q, args)]


def frecuencia(con, parada_id: str, linea_ref: str, ventana_min: int = 180) -> dict:
    """Frecuencia real estimada a partir de reportes 'paso' consecutivos.

    Honesto con la confianza: con <3 pasos no hay estimación (intervalo_min=None).
    """
    desde = iso(ahora() - timedelta(minutes=ventana_min))
    rows = con.execute(
        "SELECT ts, tipo FROM reportes WHERE parada_id=? AND linea_ref=? AND ts>=? "
        "ORDER BY ts", (parada_id, linea_ref, desde)).fetchall()
    pasos = [datetime.fromisoformat(r["ts"]) for r in rows if r["tipo"] == "paso"]
    demoras = [r for r in rows if r["tipo"] == "demora"]
    intervalos = [(b - a).total_seconds() / 60 for a, b in zip(pasos, pasos[1:])]
    estimacion = round(statistics.median(intervalos), 1) if len(intervalos) >= 2 else None
    ultimo = pasos[-1] if pasos else None
    return {
        "parada_id": parada_id,
        "linea_ref": linea_ref,
        "ventana_min": ventana_min,
        "reportes_paso": len(pasos),
        "reportes_demora": len(demoras),
        "intervalo_mediano_min": estimacion,
        "confianza": "ok" if estimacion is not None else "insuficiente (faltan reportes 'paso')",
        "ultimo_paso": iso(ultimo) if ultimo else None,
        "minutos_desde_ultimo_paso": round((ahora() - ultimo).total_seconds() / 60, 1) if ultimo else None,
    }


def total(con) -> int:
    return con.execute("SELECT COUNT(*) c FROM reportes").fetchone()["c"]
