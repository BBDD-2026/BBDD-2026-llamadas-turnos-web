"""
Panel Llamadas_Turnos — versión ONLINE (Streamlit Community Cloud)
-----------------------------------------------------------------
Lee un consolidado YA SANITIZADO (`data/publico.parquet`): el teléfono viene
hasheado, no hay nombres ni datos de clientes. Ese archivo lo genera
`publicar.py` en la máquina donde están los .rsl.

Acceso protegido por contraseña (`.streamlit/secrets.toml` →  password = "…").

Este es el entrypoint que usa Streamlit Community Cloud.
"""
from __future__ import annotations

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
def pedir_password() -> None:
    esperada = st.secrets.get("password", None)
    if not esperada:
        st.error("Falta configurar `password` en los secrets de la app.")
        st.stop()
    if st.session_state.get("_auth_ok"):
        return
    st.title("📞 Panel Llamadas_Turnos")
    pw = st.text_input("Contraseña", type="password")
    if pw and pw == esperada:
        st.session_state["_auth_ok"] = True
        st.rerun()
    elif pw:
        st.error("Contraseña incorrecta.")
    st.stop()


pedir_password()


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


# ---- barra lateral: reemplazar el consolidado (solo instancia actual) ----
st.sidebar.header("Datos")
with st.sidebar.expander("Actualizar consolidado"):
    st.caption(
        "Subí el `publico.parquet` que genera `publicar.py`. Actualiza esta "
        "instancia hasta el próximo reinicio; para que quede fijo, corré "
        "`python publicar.py --push` en la máquina de los .rsl."
    )
    up = st.file_uploader("publico.parquet", type=["parquet"])
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
