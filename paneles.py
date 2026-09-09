"""
paneles.py — render de los tableros (KPIs + pestañas) de Llamadas_Turnos.

Lo comparten la app local (`app.py`, lee de SQLite) y la app online
(`streamlit_app.py`, lee del parquet sanitizado). No tiene dependencias del
proyecto: solo streamlit / plotly / pandas.

`d` es un DataFrame ya filtrado con estas columnas:
    fecha, hora, telefono, origen, turno, campania, resultado, resultado_familia,
    intento, contactado(bool), contestador(bool), gestion_agente(bool),
    tipificado(bool), tipificacion, region, servicio_destino, localidad, base,
    lista_origen, agente_id
En la versión online `telefono` es un hash (se preserva el conteo de únicos).
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ACCENT = "#4C9AFF"
GRID = "#2A2F3A"
FAM_COLORS = {
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


def layout(fig, h=360, legend=True):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=h,
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0) if legend else None,
        showlegend=legend,
    )
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID)
    return fig


def kpi_row(d: pd.DataFrame) -> None:
    llamadas = len(d)
    contactos = int(d["contactado"].sum())
    con_agente = int(d["gestion_agente"].sum())
    tipificadas = int(d["tipificado"].sum())
    contestador = int(d["contestador"].sum())

    k = st.columns(6)
    k[0].metric("Llamadas", f"{llamadas:,}")
    k[1].metric("Teléfonos únicos", f"{d['telefono'].nunique():,}")
    k[2].metric("Contacto humano", f"{contactos:,}", f"{contactos / llamadas:.1%}")
    k[3].metric("Contestador", f"{contestador:,}", f"{contestador / llamadas:.1%}",
                delta_color="inverse")
    k[4].metric("Con agente", f"{con_agente:,}", f"{con_agente / llamadas:.1%}")
    k[5].metric("Tipificadas", f"{tipificadas:,}",
                f"{tipificadas / con_agente:.1%} de gestión" if con_agente else "—")


def tab_general(d: pd.DataFrame) -> None:
    llamadas = len(d)
    contactos = int(d["contactado"].sum())
    con_agente = int(d["gestion_agente"].sum())
    tipificadas = int(d["tipificado"].sum())

    # ----------------------------- Fila 1 ------------------------------
    c1, c2 = st.columns([1, 1.3])

    with c1:
        st.subheader("Embudo de la jornada")
        etapas = pd.DataFrame({
            "Etapa": ["Llamadas", "Contacto humano", "Gestión con agente", "Tipificadas"],
            "Valor": [llamadas, contactos, con_agente, tipificadas],
        })
        fig = go.Figure(go.Funnel(
            y=etapas["Etapa"], x=etapas["Valor"],
            textinfo="value+percent initial",
            marker=dict(color=[ACCENT, "#36B37E", "#6554C0", "#FFAB00"]),
        ))
        st.plotly_chart(layout(fig, h=320, legend=False), width='stretch')

    with c2:
        st.subheader("Resultado de la llamada")
        fam = (d["resultado_familia"].value_counts()
               .rename_axis("Familia").reset_index(name="Llamadas"))
        fam["%"] = fam["Llamadas"] / llamadas
        fig = px.bar(fam.sort_values("Llamadas"), x="Llamadas", y="Familia",
                     orientation="h", color="Familia", color_discrete_map=FAM_COLORS,
                     text=fam.sort_values("Llamadas")["%"].map(lambda v: f"{v:.1%}"))
        fig.update_traces(textposition="outside", cliponaxis=False)
        st.plotly_chart(layout(fig, h=320, legend=False), width='stretch')

    # ----------------------------- Fila 2 ----------------------------
    st.subheader("Llamadas por hora y contactabilidad")
    porhora = (d.groupby(["hora", "resultado_familia"]).size().reset_index(name="n"))
    tot_hora = d.groupby("hora").agg(llamadas=("telefono", "size"),
                                     contacto=("contactado", "sum")).reset_index()
    tot_hora["pct"] = tot_hora["contacto"] / tot_hora["llamadas"]

    fig = px.bar(porhora, x="hora", y="n", color="resultado_familia",
                 color_discrete_map=FAM_COLORS, barmode="stack")
    fig.add_trace(go.Scatter(
        x=tot_hora["hora"], y=tot_hora["pct"], name="% contacto",
        yaxis="y2", mode="lines+markers", line=dict(color="#FFFFFF", width=2)))
    fig.update_layout(
        yaxis2=dict(overlaying="y", side="right", tickformat=".0%",
                    showgrid=False, title="% contacto"),
        xaxis=dict(dtick=1, title="Hora"),
    )
    st.plotly_chart(layout(fig, h=380), width='stretch')

    # ----------------------------- Fila 3 ---------------------------
    c3, c4 = st.columns(2)

    with c3:
        st.subheader("Por región")
        reg = d.groupby("region").agg(llamadas=("telefono", "size"),
                                      contacto=("contactado", "sum")).reset_index()
        reg["% contacto"] = reg["contacto"] / reg["llamadas"]
        reg = reg.sort_values("llamadas")
        fig = px.bar(reg, x="llamadas", y="region", orientation="h",
                     text=reg["% contacto"].map(lambda v: f"{v:.1%}"))
        fig.update_traces(marker_color=ACCENT, textposition="outside", cliponaxis=False)
        st.plotly_chart(layout(fig, h=360, legend=False), width='stretch')

    with c4:
        st.subheader("Distribución de intentos")
        it = (d["intento"].dropna().astype(int).value_counts()
              .rename_axis("intento").reset_index(name="llamadas").sort_values("intento"))
        fig = px.bar(it, x="intento", y="llamadas")
        fig.update_traces(marker_color="#6554C0")
        fig.update_xaxes(dtick=1)
        st.plotly_chart(layout(fig, h=360, legend=False), width='stretch')

    # ----------------------------- Fila 4 --------------------------
    c5, c6 = st.columns(2)

    with c5:
        st.subheader("Tipificaciones (gestión con agente)")
        tip = (d.loc[d["tipificado"], "tipificacion"].value_counts()
               .rename_axis("Tipificación").reset_index(name="Llamadas").head(15)
               .sort_values("Llamadas"))
        if tip.empty:
            st.info("Sin tipificaciones en la selección.")
        else:
            fig = px.bar(tip, x="Llamadas", y="Tipificación", orientation="h")
            fig.update_traces(marker_color="#36B37E")
            st.plotly_chart(layout(fig, h=380, legend=False), width='stretch')

    with c6:
        st.subheader("Top listas de origen (CORTEBASE)")
        lo = (d.groupby("lista_origen").agg(llamadas=("telefono", "size"),
                                            contacto=("contactado", "sum")).reset_index())
        lo["% contacto"] = lo["contacto"] / lo["llamadas"]
        lo = lo.sort_values("llamadas", ascending=False).head(15).sort_values("llamadas")
        fig = px.bar(lo, x="llamadas", y="lista_origen", orientation="h",
                     text=lo["% contacto"].map(lambda v: f"{v:.1%}"))
        fig.update_traces(marker_color="#00B8D9", textposition="outside", cliponaxis=False)
        st.plotly_chart(layout(fig, h=380, legend=False), width='stretch')

    # ----------------------------- Fila 5 -------------------------
    c7, c8 = st.columns([1, 1.6])

    with c7:
        st.subheader("Servicio destino")
        sv = (d["servicio_destino"].replace("", "Sin dato").value_counts()
              .rename_axis("Servicio").reset_index(name="Llamadas"))
        fig = px.pie(sv, names="Servicio", values="Llamadas", hole=.55)
        fig.update_traces(textinfo="percent+label")
        st.plotly_chart(layout(fig, h=340, legend=False), width='stretch')

    with c8:
        st.subheader("Contactabilidad por origen / turno")
        piv = d.groupby(["origen", "turno"]).agg(
            llamadas=("telefono", "size"),
            contacto=("contactado", "sum"),
            contestador=("contestador", "sum"),
            con_agente=("gestion_agente", "sum"),
            tipificadas=("tipificado", "sum"),
        ).reset_index()
        piv["% contacto"] = (piv["contacto"] / piv["llamadas"] * 100).round(1)
        piv["% contestador"] = (piv["contestador"] / piv["llamadas"] * 100).round(1)
        st.dataframe(piv, width='stretch', hide_index=True)

    # ----------------------------- Evolución diaria -------------------
    if d["fecha"].nunique() > 1:
        st.subheader("Evolución diaria")
        ev = d.groupby("fecha").agg(
            llamadas=("telefono", "size"),
            contacto=("contactado", "sum"),
            con_agente=("gestion_agente", "sum"),
            tipificadas=("tipificado", "sum"),
        ).reset_index()
        ev["% contacto"] = ev["contacto"] / ev["llamadas"]
        fig = px.bar(ev, x="fecha", y="llamadas")
        fig.update_traces(marker_color=ACCENT, name="Llamadas")
        fig.add_trace(go.Scatter(
            x=ev["fecha"], y=ev["% contacto"], name="% contacto", yaxis="y2",
            mode="lines+markers", line=dict(color="#36B37E", width=2)))
        fig.update_layout(yaxis2=dict(overlaying="y", side="right", tickformat=".0%",
                                      showgrid=False, title="% contacto"))
        st.plotly_chart(layout(fig, h=340), width='stretch')


def tab_tmk(d: pd.DataFrame) -> None:
    ag = d[d["agente_id"].fillna("").astype(str).str.strip() != ""].copy()
    ag["agente_id"] = ag["agente_id"].astype(str).str.strip()

    if ag.empty:
        st.info(
            "No hay llamadas ruteadas a un TMK en la selección. El discador solo "
            "asigna `agente_id` a las llamadas que llegaron a un operador."
        )
        return

    n_tmk = ag["agente_id"].nunique()
    gest = len(ag)
    tipif = int(ag["tipificado"].sum())
    cont = int(ag["contactado"].sum())
    dias = ag["fecha"].nunique()

    kt = st.columns(5)
    kt[0].metric("TMK activos", f"{n_tmk:,}")
    kt[1].metric("Gestiones", f"{gest:,}")
    kt[2].metric("Tipificadas", f"{tipif:,}", f"{tipif / gest:.1%}")
    kt[3].metric("Contacto", f"{cont:,}", f"{cont / gest:.1%}")
    kt[4].metric("Gestiones / TMK", f"{gest / n_tmk:,.0f}",
                 f"{gest / n_tmk / dias:,.0f} por día" if dias else None)
    st.divider()

    tab = ag.groupby("agente_id").agg(
        gestiones=("telefono", "size"),
        contacto=("contactado", "sum"),
        tipificadas=("tipificado", "sum"),
        dias=("fecha", "nunique"),
    ).reset_index()
    tab["% contacto"] = (tab["contacto"] / tab["gestiones"] * 100).round(1)
    tab["% tipif"] = (tab["tipificadas"] / tab["gestiones"] * 100).round(1)
    tab["gest/día"] = (tab["gestiones"] / tab["dias"]).round(1)

    top_tip = (ag[ag["tipificado"]]
               .groupby(["agente_id", "tipificacion"]).size()
               .reset_index(name="n")
               .sort_values("n", ascending=False)
               .drop_duplicates("agente_id")
               .set_index("agente_id")["tipificacion"])
    tab["tipif. principal"] = tab["agente_id"].map(top_tip).fillna("—")
    tab = (tab.rename(columns={"agente_id": "TMK"})
           .sort_values("gestiones", ascending=False))

    c1, c2 = st.columns([1.4, 1])
    with c1:
        st.subheader("Top 20 TMK por gestiones")
        top = tab.head(20).sort_values("gestiones")
        fig = px.bar(top, x="gestiones", y="TMK", orientation="h",
                     text=top["% tipif"].map(lambda v: f"{v:.0f}% tipif"))
        fig.update_traces(marker_color=ACCENT, textposition="outside", cliponaxis=False)
        fig.update_yaxes(type="category")
        st.plotly_chart(layout(fig, h=560, legend=False), width='stretch')
    with c2:
        st.subheader("Gestiones vs % tipificación")
        fig = px.scatter(tab, x="gestiones", y="% tipif", hover_name="TMK",
                         size="gestiones", color="% contacto",
                         color_continuous_scale="Blues")
        st.plotly_chart(layout(fig, h=560, legend=False), width='stretch')

    st.subheader(f"Detalle por TMK · {len(tab)} agentes")
    st.caption("Clic en el encabezado de una columna para ordenar.")
    st.dataframe(
        tab[["TMK", "gestiones", "contacto", "% contacto", "tipificadas",
             "% tipif", "dias", "gest/día", "tipif. principal"]],
        width='stretch', hide_index=True, height=460,
    )
    st.download_button(
        "Descargar tabla TMK (CSV)",
        tab.to_csv(index=False, encoding="utf-8-sig"),
        file_name="tmk_llamadas_turnos.csv", mime="text/csv",
    )

    st.subheader("Tipificaciones de los 12 TMK con más gestión")
    top12 = tab.head(12)["TMK"].tolist()
    mix = (ag[ag["tipificado"] & ag["agente_id"].isin(top12)]
           .groupby(["agente_id", "tipificacion"]).size().reset_index(name="n"))
    if mix.empty:
        st.info("Sin tipificaciones para esos TMK en la selección.")
    else:
        comunes = mix.groupby("tipificacion")["n"].sum().nlargest(8).index
        mix["tipificacion"] = mix["tipificacion"].where(
            mix["tipificacion"].isin(comunes), "Otras")
        mix = mix.groupby(["agente_id", "tipificacion"], as_index=False)["n"].sum()
        fig = px.bar(mix, x="agente_id", y="n", color="tipificacion", barmode="stack")
        fig.update_xaxes(type="category", title="TMK")
        fig.update_yaxes(title="Tipificaciones")
        st.plotly_chart(layout(fig, h=420), width='stretch')

    st.divider()
    foco = st.selectbox("Enfocar un TMK", ["—"] + tab["TMK"].tolist())
    if foco != "—":
        fa = ag[ag["agente_id"] == foco]
        f1, f2 = st.columns([1, 1])
        with f1:
            st.caption(f"TMK {foco} · por día")
            ev = fa.groupby("fecha").agg(
                gestiones=("telefono", "size"),
                tipificadas=("tipificado", "sum"),
            ).reset_index()
            fig = px.bar(ev, x="fecha", y=["gestiones", "tipificadas"], barmode="group")
            st.plotly_chart(layout(fig, h=320), width='stretch')
        with f2:
            st.caption(f"TMK {foco} · tipificaciones")
            tp = (fa.loc[fa["tipificado"], "tipificacion"].value_counts()
                  .rename_axis("Tipificación").reset_index(name="n").head(12)
                  .sort_values("n"))
            if tp.empty:
                st.info("Sin tipificaciones.")
            else:
                fig = px.bar(tp, x="n", y="Tipificación", orientation="h")
                fig.update_traces(marker_color="#36B37E")
                st.plotly_chart(layout(fig, h=320, legend=False), width='stretch')
