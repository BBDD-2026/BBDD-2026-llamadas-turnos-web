"""
core.py — parseo de .rsl y capa de datos SQLite para Llamadas_Turnos.

Lo usan tanto la app de escritorio (panel_llamadas.py) como el ETL (etl.py).
La base acumula todas las jornadas; la clave primaria (fecha, archivo, record_id)
evita duplicar si se reimporta el mismo archivo.
"""
from __future__ import annotations

import csv
import sqlite3
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB_PATH = HERE / "data" / "llamadas.db"

# --- Campos crudos del .rsl que conservamos -> nombre final ---------------
RENOMBRES = {
    "record_id": "record_id",
    "contact_info": "telefono",
    "record_type": "record_type",
    "record_status": "record_status",
    "call_result": "resultado",
    "attempt": "intento",
    "call_time": "call_time_raw",
    "campaign_id": "campania_id",
    "group_id": "grupo_id",
    "switch_id": "switch_id",
    "chain_id": "chain_id",
    "agent_id": "agente_id",
    "CORTEBASE": "lista_origen",
    "CAMPANIA": "campania",
    "REGION": "region",
    "DISPOSITIONCODE": "tipificacion",
    "CLIENTE_NOMBRE": "cliente_nombre",
    "CUST_DATA_12": "servicio_destino",
    "CUST_DATA_13": "codigo_base",
    "CUST_DATA_14": "localidad",
    "CUST_DATA_15": "base",
}

# Orden de columnas de la tabla `llamadas`
COLUMNS = [
    "fecha", "archivo", "record_id",
    "origen", "turno", "hora", "call_time",
    "telefono", "resultado", "resultado_familia", "intento",
    "contactado", "contestador", "gestion_agente", "tipificado", "tipificacion",
    "campania", "region", "servicio_destino", "localidad", "base",
    "lista_origen", "codigo_base",
    "agente_id", "switch_id", "campania_id", "grupo_id",
    "record_type", "record_status", "chain_id",
    "cliente_con_datos", "importado_en",
]

FAMILIA = {
    "Answer": "Contacto humano",
    "Answering Machine Detected": "Contestador",
    "Fax Detected": "Contestador",
    "No Answer": "No atiende",
    "Busy": "Ocupado",
    "General Error": "Error / técnico",
    "SIT Invalid Number": "Número inválido",
    "Silence": "Error / técnico",
    "Dropped": "Abandonada por sistema",
    "Abandoned": "Abandonada por sistema",
    "Remote Release": "Cortó el llamado",
    "Stale": "Otros",
    "Cancel Record": "Otros",
    "Do Not Call": "No llamar",
    "Agent CallBack Error": "Otros",
}

FAMILIA_COLORES = {
    "Contacto humano": "#36B37E",
    "Contestador": "#FFAB00",
    "No atiende": "#6554C0",
    "Ocupado": "#00B8D9",
    "Cortó el llamado": "#FF7452",
    "Abandonada por sistema": "#FF5630",
    "Error / técnico": "#8993A4",
    "Número inválido": "#DE350B",
    "No llamar": "#BF2600",
    "Otros": "#505F79",
}


# ----------------------------- Parseo -----------------------------------
def clasificar_archivo(nombre: str) -> tuple[str, str]:
    n = nombre.upper()
    if "IVR" in n:
        return "IVR BAF", "Mixto"
    if "(TM)" in n or " TM" in n or "_TM" in n:
        return "Contact Center", "Mañana"
    if "(TT)" in n or " TT" in n or "_TT" in n:
        return "Contact Center", "Tarde"
    return "Contact Center", "Sin clasificar"


def parse_line(line: str) -> dict:
    out = {}
    for part in line.rstrip("\r\n").split("|"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k] = v
    return out


def parse_call_time(s: str):
    if not s or not s.strip():
        return None
    t = (s.strip()
         .replace("a. m.", "AM").replace("p. m.", "PM")
         .replace("a.m.", "AM").replace("p.m.", "PM")
         .replace("a. m", "AM").replace("p. m", "PM"))
    for fmt in ("%d/%m/%Y %I:%M:%S %p", "%d/%m/%Y %H:%M:%S"):
        try:
            return datetime.strptime(t, fmt)
        except ValueError:
            continue
    return None


def _int(v):
    try:
        return int(str(v).strip())
    except (ValueError, TypeError):
        return None


def normalizar(d: dict, archivo: str, origen: str, turno: str, importado_en: str) -> tuple:
    r = {dest: d.get(src, "") for src, dest in RENOMBRES.items()}
    dt = parse_call_time(r["call_time_raw"])
    resultado = r["resultado"].strip()
    tip = r["tipificacion"].strip() or None
    agente = r["agente_id"].strip()
    switch = _int(r["switch_id"])
    nombre_cli = r["cliente_nombre"].strip()

    fila = {
        "fecha": dt.strftime("%Y-%m-%d") if dt else None,
        "archivo": archivo,
        "record_id": r["record_id"].strip(),
        "origen": origen,
        "turno": turno,
        "hora": dt.hour if dt else None,
        "call_time": dt.strftime("%Y-%m-%d %H:%M:%S") if dt else None,
        "telefono": r["telefono"].strip(),
        "resultado": resultado,
        "resultado_familia": FAMILIA.get(resultado, "Otros"),
        "intento": _int(r["intento"]),
        "contactado": 1 if resultado == "Answer" else 0,
        "contestador": 1 if resultado == "Answering Machine Detected" else 0,
        "gestion_agente": 1 if (agente != "" or switch == 102) else 0,
        "tipificado": 1 if tip else 0,
        "tipificacion": tip,
        "campania": r["campania"].strip(),
        "region": r["region"].strip(),
        "servicio_destino": r["servicio_destino"].strip(),
        "localidad": r["localidad"].strip(),
        "base": r["base"].strip(),
        "lista_origen": r["lista_origen"].strip(),
        "codigo_base": r["codigo_base"].strip(),
        "agente_id": agente,
        "switch_id": switch,
        "campania_id": _int(r["campania_id"]),
        "grupo_id": _int(r["grupo_id"]),
        "record_type": r["record_type"].strip(),
        "record_status": r["record_status"].strip(),
        "chain_id": r["chain_id"].strip(),
        "cliente_con_datos": 0 if nombre_cli in ("", "Sin Datos") else 1,
        "importado_en": importado_en,
    }
    return tuple(fila[c] for c in COLUMNS)


def leer_archivo(path: str | Path, progress=None) -> tuple[list[tuple], str, str]:
    """Devuelve (filas, origen, turno). progress(frac: float, n: int) opcional."""
    path = Path(path)
    origen, turno = clasificar_archivo(path.name)
    importado_en = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total = max(path.stat().st_size, 1)
    filas = []
    with path.open("r", encoding="latin-1") as fh:
        for i, line in enumerate(fh):
            if line.strip():
                filas.append(normalizar(parse_line(line), path.name, origen, turno, importado_en))
            if progress and i % 5000 == 0:
                progress(fh.tell() / total, len(filas))
    if progress:
        progress(1.0, len(filas))
    return filas, origen, turno


def rsl_bytes_a_filas(data: bytes, nombre: str) -> list[tuple]:
    """Bytes de un .rsl -> filas en orden COLUMNS (para pd.DataFrame(columns=COLUMNS))."""
    origen, turno = clasificar_archivo(nombre)
    importado_en = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    filas = []
    for line in data.decode("latin-1").splitlines():
        if line.strip():
            filas.append(normalizar(parse_line(line), nombre, origen, turno, importado_en))
    return filas


# ------------------------- Sanitización (versión online) ---------------
# Subconjunto de columnas que viaja a la nube. Sin teléfono real, sin nombres
# ni flags de cliente. `archivo` + `record_id` se conservan sólo para deduplicar.
PUBLICAS = [
    "fecha", "archivo", "record_id", "hora", "telefono",
    "origen", "turno", "campania", "resultado", "resultado_familia", "intento",
    "contactado", "contestador", "gestion_agente", "tipificado", "tipificacion",
    "region", "servicio_destino", "localidad", "base", "lista_origen", "agente_id",
]


def hash_telefono(valor: str, salt: str) -> str:
    import hashlib
    v = ("" if valor is None else str(valor)).strip()
    if not v:
        return ""
    return hashlib.sha256((salt + v).encode()).hexdigest()[:16]


def sanitizar(df, salt: str):
    """DataFrame con columnas de `llamadas` -> subconjunto PUBLICAS con tel. hasheado."""
    d = df.copy()
    d["telefono"] = d["telefono"].map(lambda x: hash_telefono(x, salt))
    for c in ("contactado", "contestador", "gestion_agente", "tipificado"):
        d[c] = d[c].fillna(0).astype("int8")
    d["agente_id"] = d["agente_id"].fillna("").astype(str).str.strip()
    for c in PUBLICAS:
        if c not in d.columns:
            d[c] = None
    return d[PUBLICAS].copy()


# ----------------------------- Base de datos ----------------------------
SCHEMA = f"""
CREATE TABLE IF NOT EXISTS llamadas (
    {", ".join(c + (" INTEGER" if c in
        ("hora","intento","contactado","contestador","gestion_agente","tipificado",
         "switch_id","campania_id","grupo_id","cliente_con_datos")
        else " TEXT") for c in COLUMNS)},
    PRIMARY KEY (fecha, archivo, record_id)
);
CREATE INDEX IF NOT EXISTS ix_fecha    ON llamadas(fecha);
CREATE INDEX IF NOT EXISTS ix_origen   ON llamadas(origen);
CREATE INDEX IF NOT EXISTS ix_campania ON llamadas(campania);
CREATE INDEX IF NOT EXISTS ix_region   ON llamadas(region);

CREATE TABLE IF NOT EXISTS importaciones (
    archivo TEXT, fecha_jornada TEXT, registros INTEGER, importado_en TEXT,
    PRIMARY KEY (archivo, fecha_jornada)
);

CREATE TABLE IF NOT EXISTS fuentes (
    ruta TEXT PRIMARY KEY, tam INTEGER, mtime REAL, importado_en TEXT
);
"""


class DB:
    def __init__(self, path: str | Path = DB_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self):
        self.conn.close()

    # -- ingesta --
    def ingest(self, path: str | Path, progress=None, saltar_si_visto=False) -> dict:
        path = Path(path)
        archivo = path.name
        ruta = str(path.resolve())
        stat = path.stat()

        if saltar_si_visto:
            row = self.conn.execute(
                "SELECT tam, mtime FROM fuentes WHERE ruta=?", (ruta,)
            ).fetchone()
            if row and row[0] == stat.st_size and abs(row[1] - stat.st_mtime) < 1:
                return {"archivo": archivo, "ruta": ruta, "omitido": True,
                        "lineas": 0, "insertados": 0, "duplicados": 0, "fechas": []}

        filas, origen, turno = leer_archivo(path, progress)
        antes = self.conn.total_changes
        self.conn.executemany(
            f"INSERT OR IGNORE INTO llamadas ({','.join(COLUMNS)}) "
            f"VALUES ({','.join('?' * len(COLUMNS))})",
            filas,
        )
        insertados = self.conn.total_changes - antes
        # actualizar catálogo de importaciones por jornada
        fechas = sorted({f[0] for f in filas if f[0]})
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for fe in fechas:
            n = self.conn.execute(
                "SELECT COUNT(*) FROM llamadas WHERE archivo=? AND fecha=?", (archivo, fe)
            ).fetchone()[0]
            self.conn.execute(
                "INSERT OR REPLACE INTO importaciones VALUES (?,?,?,?)",
                (archivo, fe, n, ahora),
            )
        self.conn.execute(
            "INSERT OR REPLACE INTO fuentes VALUES (?,?,?,?)",
            (ruta, stat.st_size, stat.st_mtime, ahora),
        )
        self.conn.commit()
        return {
            "archivo": archivo, "ruta": ruta, "origen": origen, "turno": turno,
            "omitido": False, "lineas": len(filas), "insertados": insertados,
            "duplicados": len(filas) - insertados, "fechas": fechas,
        }

    def borrar_jornada(self, archivo: str, fecha: str) -> int:
        cur = self.conn.execute(
            "DELETE FROM llamadas WHERE archivo=? AND fecha=?", (archivo, fecha)
        )
        self.conn.execute(
            "DELETE FROM importaciones WHERE archivo=? AND fecha_jornada=?", (archivo, fecha)
        )
        self.conn.commit()
        return cur.rowcount

    # -- consultas --
    def _where(self, f: dict, extra: list[str] | None = None):
        cl, p = [], []
        if f.get("desde"):
            cl.append("fecha >= ?"); p.append(f["desde"])
        if f.get("hasta"):
            cl.append("fecha <= ?"); p.append(f["hasta"])
        for col, key, todos in (("origen", "origen", "Todos"),
                                ("turno", "turno", "Todos"),
                                ("campania", "campania", "Todas"),
                                ("region", "region", "Todas"),
                                ("agente_id", "agente", "Todos")):
            v = f.get(key)
            if v and v != todos:
                cl.append(f"{col} = ?"); p.append(v)
        if f.get("solo_agente"):
            cl.append("gestion_agente = 1")
        if extra:
            cl.extend(extra)
        return (("WHERE " + " AND ".join(cl)) if cl else ""), p

    def serie(self, select, groupby, f, extra=None, order=None, limit=None):
        import pandas as pd
        w, p = self._where(f, extra)
        sql = f"SELECT {select} FROM llamadas {w} GROUP BY {groupby}"
        if order:
            sql += f" ORDER BY {order}"
        if limit:
            sql += f" LIMIT {int(limit)}"
        return pd.read_sql_query(sql, self.conn, params=p)

    def kpis(self, f: dict) -> dict:
        w, p = self._where(f)
        row = self.conn.execute(
            f"""SELECT COUNT(*), COUNT(DISTINCT telefono),
                       COALESCE(SUM(contactado),0), COALESCE(SUM(contestador),0),
                       COALESCE(SUM(gestion_agente),0), COALESCE(SUM(tipificado),0)
                FROM llamadas {w}""", p
        ).fetchone()
        k = dict(zip(
            ("llamadas", "telefonos", "contacto", "contestador", "agente", "tipificadas"), row))
        return k

    def por_agente(self, f: dict):
        """Ranking de TMK (agente_id) según las llamadas que gestionó."""
        import pandas as pd
        w, p = self._where(f, extra=["agente_id <> ''"])
        return pd.read_sql_query(
            f"""SELECT agente_id AS tmk, COUNT(*) AS gestiones,
                       COALESCE(SUM(contactado),0) AS contacto,
                       COALESCE(SUM(tipificado),0) AS tipificadas,
                       COUNT(DISTINCT fecha) AS dias
                FROM llamadas {w}
                GROUP BY agente_id ORDER BY gestiones DESC""",
            self.conn, params=p)

    def tip_por_agente(self, f: dict):
        import pandas as pd
        w, p = self._where(f, extra=["agente_id <> ''", "tipificado = 1"])
        return pd.read_sql_query(
            f"""SELECT agente_id AS tmk, tipificacion, COUNT(*) AS n
                FROM llamadas {w} GROUP BY agente_id, tipificacion""",
            self.conn, params=p)

    def detalle(self, f: dict, limit=5000):
        import pandas as pd
        w, p = self._where(f)
        return pd.read_sql_query(
            f"""SELECT fecha, hora, telefono, origen, turno, campania,
                       resultado, resultado_familia, intento, region,
                       servicio_destino, localidad, base, lista_origen,
                       gestion_agente, tipificacion, agente_id
                FROM llamadas {w} ORDER BY call_time LIMIT {int(limit)}""",
            self.conn, params=p)

    def exportar_csv(self, f: dict, destino: str | Path) -> int:
        w, p = self._where(f)
        cur = self.conn.execute(f"SELECT * FROM llamadas {w} ORDER BY call_time", p)
        n = 0
        with open(destino, "w", newline="", encoding="utf-8-sig") as fh:
            wr = csv.writer(fh, delimiter=";")
            wr.writerow([d[0] for d in cur.description])
            for row in cur:
                wr.writerow(row); n += 1
        return n

    def valores(self, col: str) -> list[str]:
        rows = self.conn.execute(
            f"SELECT DISTINCT {col} FROM llamadas WHERE {col} IS NOT NULL AND {col} <> '' "
            f"ORDER BY {col}"
        ).fetchall()
        return [r[0] for r in rows]

    def rango_fechas(self):
        return self.conn.execute("SELECT MIN(fecha), MAX(fecha) FROM llamadas").fetchone()

    def importaciones(self):
        import pandas as pd
        return pd.read_sql_query(
            "SELECT archivo, fecha_jornada, registros, importado_en "
            "FROM importaciones ORDER BY fecha_jornada DESC, archivo", self.conn)

    def total(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM llamadas").fetchone()[0]
