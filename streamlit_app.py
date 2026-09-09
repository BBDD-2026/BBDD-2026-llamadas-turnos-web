"""
Panel Llamadas_Turnos — versión ONLINE (Streamlit Community Cloud)
-----------------------------------------------------------------
Lee un consolidado YA SANITIZADO (`data/publico.parquet`): el teléfono viene
hasheado, no hay nombres ni datos de clientes. Ese archivo lo genera
`publicar.py` en la máquina donde están los .rsl.

Acceso protegido por usuario/contraseña definidos en los Secrets de la app
(ver bloque de comentario más abajo, sección "Acceso").

Este es el entrypoint que usa Streamlit Community Cloud.
"""
from __future__ import annotations

import hmac
from pathlib import Path

import pandas as pd
import streamlit as st

import paneles

st.set_page_config(page_title="Panel Llamadas_Turnos", page_icon="📞", layout="wide")

HERE = Path(__file__).resolve().parent
CANDIDATOS = [HERE / "data" / "publico.parquet", HERE / "web" / "data" / "publico.parquet"]
PARQUET = next((p for p in CANDIDATOS if p.exists()), CANDIDATOS[0])

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
#   tmk        = "clave-compartida"
#
#   # opción B — una sola clave para todo el equipo:
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


# --------------------------------- Datos ---------------------------------
@st.cache_data(show_spinner="Cargando consolidado…")
def cargar(_mtime: float) -> pd.DataFrame:
    df = pd.read_parquet(PARQUET)
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce").dt.date
    for c in ("contactado", "contestador", "gestion_agente", "tipificado"):
        if c in df.columns:
            df[c] = df[c].fillna(0).astype(bool)
    if "agente_id" in df.columns:
        df["agente_id"] = df["agente_id"].fillna("").astype(str).str.strip()
    return df


@st.cache_data(show_spinner=False)
def fechas_cargadas(_mtime: float) -> list[str]:
    if not PARQUET.exists():
        return []
    s = pd.read_parquet(PARQUET, columns=["fecha"])["fecha"].dropna().astype(str)
    return sorted(s.unique().tolist())


# ---- barra lateral ----
with st.sidebar:
    lc, bc = st.columns([2, 1])
    lc.caption(f"👤 {st.session_state.get('_auth_user', '')}")
    if bc.button("Salir", help="Cerrar sesión"):
        st.session_state.clear()
        st.rerun()

st.sidebar.header("Datos")
_fc = fechas_cargadas(PARQUET.stat().st_mtime if PARQUET.exists() else 0.0)
if _fc:
    _rango = _fc[0] if len(_fc) == 1 else f"{_fc[0]} → {_fc[-1]}"
    st.sidebar.caption(
        f"📅 Cargadas: {_rango}  ·  {len(_fc)} jornada" + ("s" if len(_fc) != 1 else ""))
with st.sidebar.expander("Actualizar consolidado"):
    if _fc:
        st.caption("Fechas en el consolidado:")
        st.code("\n".join(_fc), language=None)
    st.caption(
        "⚠️ Acá **no** se suben `.rsl` ni carpetas. Este panel lee un único "
        "archivo ya anonimizado: **`publico.parquet`**, que se genera con "
        "`publicar.py` en la máquina donde están los `.rsl`.\n\n"
        "Lo normal es actualizar con `python publicar.py --push` (redeploy "
        "automático). Subirlo acá a mano sólo cambia esta instancia hasta el "
        "próximo reinicio."
    )
    up = st.file_uploader("Subir publico.parquet (un solo archivo)", type=["parquet"])
    if up is not None and st.button("Reemplazar", width='stretch'):
        PARQUET.parent.mkdir(parents=True, exist_ok=True)
        PARQUET.write_bytes(up.getbuffer())
        st.cache_data.clear()
        st.success("Consolidado actualizado.")
        st.rerun()

if not PARQUET.exists():
    st.info("Todavía no hay datos. Subí un `publico.parquet` desde la barra lateral.")
    st.stop()

MT = PARQUET.stat().st_mtime
df = cargar(MT)
if df.empty:
    st.warning("El consolidado está vacío.")
    st.stop()

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
st.caption(f"Discador · campañas de retención Claro · jornada(s): {fechas}  ·  datos anonimizados")

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
                        "tipificacion", "agente_id"] if c in d.columns]
    st.dataframe(d[cols].head(3000), width='stretch', hide_index=True)

st.download_button(
    "Descargar selección (CSV)",
    d.drop(columns=[c for c in ["telefono"] if c in d.columns])
     .to_csv(index=False, encoding="utf-8-sig"),
    file_name="llamadas_turnos_seleccion.csv",
    mime="text/csv",
)
