"""
Panel Llamadas_Turnos — versión ONLINE (Streamlit Community Cloud)
-----------------------------------------------------------------
NO guarda datos en ningún lado. Subís los `.rsl` del día (o un `.zip` con
varios) desde la barra lateral: se parsean y anonimizan EN MEMORIA (el teléfono
se reemplaza por un hash de sesión) y se muestra el panel. Al cerrar la pestaña
o reiniciarse la app, los datos se van; hay que volver a subir los `.rsl`.

Acceso protegido por usuario/contraseña (Secrets de la app, sección "Acceso").
Este es el entrypoint que usa Streamlit Community Cloud.
"""
from __future__ import annotations

import hmac
import io
import secrets
import zipfile
from pathlib import Path

import pandas as pd
import streamlit as st

import core
import paneles

BUILD = "2026-09-09b · incluye Ventas (preventa)"

st.set_page_config(page_title="Panel Llamadas_Turnos", page_icon="📞", layout="wide")

st.markdown(
    """
    <style>
      .block-container {padding-top: 2.2rem; padding-bottom: 2rem;}
      [data-testid="stMetricValue"] {font-size: 1.7rem;}
      [data-testid="stMetric"] {background:#161B26; border:1px solid #262C38;
        border-radius:10px; padding:12px 14px;}
      h1,h2,h3 {letter-spacing:.2px;}
    </style>
    """,
    unsafe_allow_html=True,
)

CAT_FILTROS = [
    ("fecha", "Fecha"), ("origen", "Origen"), ("turno", "Turno"),
    ("campania", "Campaña"), ("region", "Región"), ("servicio_destino", "Servicio destino"),
]


# --------------------------------- Acceso --------------------------------
# Credenciales en los Secrets de la app (Streamlit Cloud → Settings → Secrets):
#
#   # opción A — varios usuarios:
#   [passwords]
#   enzo       = "clave-de-enzo"
#   supervisor = "clave-del-super"
#
#   # opción B — una sola clave:
#   password = "clave-unica"
def _cred_ok(usuario: str, clave: str) -> bool:
    if not clave:
        return False
    tabla = st.secrets.get("passwords", None)
    if tabla is not None:
        real = tabla.get(usuario)
        return real is not None and hmac.compare_digest(str(real), clave)
    unica = st.secrets.get("password", None)
    return bool(unica) and hmac.compare_digest(str(unica), clave)


def pedir_login() -> None:
    multi = st.secrets.get("passwords", None)
    if multi is None and not st.secrets.get("password"):
        st.error("Faltan credenciales en los Secrets de la app "
                 "(`[passwords]` con usuarios, o `password` con una clave única).")
        st.stop()
    if st.session_state.get("_auth_user"):
        return

    st.title("📞 Panel Llamadas_Turnos")
    with st.form("login"):
        usuario = st.text_input("Usuario") if multi is not None else "equipo"
        clave = st.text_input("Contraseña", type="password")
        entrar = st.form_submit_button("Entrar")
    if entrar:
        if _cred_ok(usuario.strip(), clave):
            st.session_state["_auth_user"] = usuario.strip() or "equipo"
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos.")
    st.stop()


pedir_login()

# sal de sesión: sólo para no tener el número crudo en memoria; se descarta al salir
SALT = st.session_state.setdefault("_salt", secrets.token_hex(16))


# --------------------------------- Datos (en sesión) --------------------
def _pares_rsl(subidos) -> list[tuple[str, bytes]]:
    """Expande .zip; devuelve [(nombre, bytes), ...] solo de los .rsl."""
    pares: list[tuple[str, bytes]] = []
    for uf in subidos:
        nombre, datos = uf.name, uf.getvalue()
        if nombre.lower().endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(datos)) as z:
                for zi in z.infolist():
                    if not zi.is_dir() and zi.filename.lower().endswith(".rsl"):
                        pares.append((Path(zi.filename).name, z.read(zi)))
        elif nombre.lower().endswith(".rsl"):
            pares.append((nombre, datos))
    return pares


def _procesar_rsl(subidos, acumular: bool) -> None:
    pares = _pares_rsl(subidos)
    if not pares:
        st.warning("No se encontraron `.rsl` en lo subido.")
        return

    bar = st.progress(0.0, text=f"0 / {len(pares)}")
    partes = []
    for i, (nombre, datos) in enumerate(pares, 1):
        filas = core.rsl_bytes_a_filas(datos, nombre)
        partes.append(core.sanitizar(pd.DataFrame(filas, columns=core.COLUMNS), SALT))
        bar.progress(i / len(pares), text=f"{i} / {len(pares)} · {nombre[:34]}")
    bar.empty()
    pub = pd.concat(partes, ignore_index=True)

    if acumular and isinstance(st.session_state.get("datos"), pd.DataFrame):
        pub = pd.concat([st.session_state["datos"], pub], ignore_index=True)
    pub = (pub[core.PUBLICAS]
           .drop_duplicates(["fecha", "archivo", "record_id"], keep="last")
           .sort_values(["fecha", "archivo"])
           .reset_index(drop=True))

    st.session_state["datos"] = pub
    fechas = ", ".join(sorted(pub["fecha"].dropna().astype(str).unique()))
    st.success(f"{len(pares)} `.rsl` procesados · {len(pub):,} filas · {fechas}")
    st.rerun()


def _para_panel(pub: pd.DataFrame) -> pd.DataFrame:
    df = pub.copy()
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce").dt.date
    for c in ("contactado", "contestador", "gestion_agente", "tipificado", "venta"):
        if c not in df.columns:
            df[c] = 0
        df[c] = df[c].fillna(0).astype(bool)
    df["agente_id"] = df["agente_id"].fillna("").astype(str).str.strip()
    return df


# ---- barra lateral ----
with st.sidebar:
    lc, bc = st.columns([2, 1])
    lc.caption(f"👤 {st.session_state.get('_auth_user', '')}")
    if bc.button("Salir", help="Cerrar sesión"):
        st.session_state.clear()
        st.rerun()

st.sidebar.header("Datos de la sesión")
_datos = st.session_state.get("datos")
_hay = isinstance(_datos, pd.DataFrame) and not _datos.empty
if _hay:
    _f = sorted(_datos["fecha"].dropna().astype(str).unique())
    _rango = _f[0] if len(_f) == 1 else f"{_f[0]} → {_f[-1]}"
    st.sidebar.caption(f"📅 {_rango}  ·  {len(_f)} jornada" + ("s" if len(_f) != 1 else "")
                       + f"  ·  {len(_datos):,} filas")

with st.sidebar.expander("Cargar .rsl", expanded=not _hay):
    st.caption("Se procesan en el momento para mostrar el panel. **No se guardan** "
               "en ningún lado: al recargar o cerrar hay que volver a subirlos.")
    rsls = st.file_uploader("Archivos .rsl / .zip", type=["rsl", "zip"],
                            accept_multiple_files=True, key="up_rsl")
    acumular = st.checkbox("Sumar a lo ya cargado en esta sesión", value=True,
                           disabled=not _hay)
    if rsls and st.button("Procesar", type="primary", width='stretch'):
        _procesar_rsl(rsls, acumular and _hay)
    if _hay and st.button("Vaciar datos", width='stretch'):
        st.session_state.pop("datos", None)
        st.rerun()

if not _hay:
    st.info("Subí los `.rsl` del día desde la barra lateral para ver el panel. "
            "Los datos se procesan en memoria y no se guardan.")
    st.stop()

df = _para_panel(_datos)

# --------------------------------- Filtros -------------------------------
st.sidebar.divider()
st.sidebar.header("Filtros")


def msel(col: str, label: str):
    if col not in df.columns:
        return None
    todos = sorted(x for x in df[col].dropna().unique().tolist() if x != "")
    sel = st.sidebar.multiselect(label, todos, default=todos, key=f"f_{col}")
    return None if len(sel) == len(todos) else set(sel)


mask = pd.Series(True, index=df.index)
for col, label in CAT_FILTROS:
    picked = msel(col, label)
    if picked is not None:
        mask &= df[col].isin(picked)
if st.sidebar.checkbox("Solo llamadas gestionadas por agente", value=False):
    mask &= df["gestion_agente"]

d = df[mask]
st.sidebar.caption(f"{len(d):,} de {len(df):,} registros")
if d.empty:
    st.warning("Los filtros no devuelven registros.")
    st.stop()

# --------------------------------- Tableros -----------------------------
fechas = ", ".join(sorted(str(x) for x in d["fecha"].dropna().unique()))
st.title("📞 Panel Llamadas_Turnos")
st.caption(f"Discador · campañas de retención Claro · jornada(s): {fechas}  ·  "
           f"datos anonimizados en memoria  ·  build {BUILD}")

paneles.kpi_row(d)
st.divider()

tab_gen, tab_tmk = st.tabs(["📊  Panorama general", "🎧  TMK / Agentes"])
with tab_gen:
    paneles.tab_general(d)
with tab_tmk:
    paneles.tab_tmk(d)

st.divider()
with st.expander("Ver detalle de registros (máx. 3000)"):
    cols = [c for c in ["fecha", "hora", "origen", "turno", "campania", "resultado",
                        "resultado_familia", "intento", "region", "servicio_destino",
                        "localidad", "base", "lista_origen", "gestion_agente",
                        "tipificacion", "venta", "agente_id"] if c in d.columns]
    st.dataframe(d[cols].head(3000), width='stretch', hide_index=True)

st.download_button(
    "Descargar selección (CSV)",
    d.drop(columns=[c for c in ["telefono"] if c in d.columns])
     .to_csv(index=False, encoding="utf-8-sig"),
    file_name="llamadas_turnos_seleccion.csv",
    mime="text/csv",
)
