"""
Módulo de Dashboard Ejecutivo y Analítica de Calidad en Limpieza:
Métricas de rendimiento (SLA), gráficos de evolución por edificio, zonas críticas y dotación de personal.
"""
import streamlit as st
import pandas as pd
import altair as alt
from database import obtener_supervisiones, obtener_lista_edificios


def render_dashboard_analitica():
    """Renderiza el panel de control ejecutivo e indicadores clave de desempeño (KPIs)."""
    st.markdown("""
        <div class="header-hero">
            <h1>📊 Dashboard Ejecutivo & Indicadores de Calidad (KPI)</h1>
            <p>Monitoreo en tiempo real del desempeño de limpieza, ranking de edificios, análisis de zonas críticas y SLA.</p>
        </div>
    """, unsafe_allow_html=True)

    supervisiones = obtener_supervisiones()

    if not supervisiones:
        st.info("ℹ️ Aún no hay datos suficientes de supervisiones para generar estadísticas. Registre al menos una supervisión.")
        return

    df = pd.DataFrame(supervisiones)

    # 1. TARJETAS KPI GLOBALES
    total_auditorias = len(df)
    promedio_score = df["score_global"].mean()
    total_nc = df["total_no_conformes"].sum()
    
    # Cálculo de cumplimiento de personal
    total_prog = df["personal_programado"].sum()
    total_pres = df["personal_presente"].sum()
    tasa_dotacion = (total_pres / total_prog * 100.0) if total_prog > 0 else 100.0

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">Auditorías Realizadas</div>
                <div class="kpi-val">{total_auditorias}</div>
                <div class="kpi-sub">Total inspecciones</div>
            </div>
        """, unsafe_allow_html=True)

    with kpi2:
        score_color = "#10B981" if promedio_score >= 85 else ("#0284C7" if promedio_score >= 75 else "#EF4444")
        st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">Índice Calidad Global</div>
                <div class="kpi-val" style="color:{score_color};">{promedio_score:.1f}%</div>
                <div class="kpi-sub">Promedio acumulado</div>
            </div>
        """, unsafe_allow_html=True)

    with kpi3:
        st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">Cumplimiento Dotación</div>
                <div class="kpi-val">{tasa_dotacion:.1f}%</div>
                <div class="kpi-sub">{total_pres} de {total_prog} operarios</div>
            </div>
        """, unsafe_allow_html=True)

    with kpi4:
        st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">No Conformidades</div>
                <div class="kpi-val" style="color:#EF4444;">{int(total_nc)}</div>
                <div class="kpi-sub">Hallazgos observados</div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # 2. GRÁFICOS ANALÍTICOS (ALTAIR)
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.markdown("### 🏢 Ranking de Calidad por Edificio")
        df_ranking = df.groupby("edificio_nombre")["score_global"].mean().reset_index()
        df_ranking.columns = ["Edificio", "Score Promedio"]
        df_ranking = df_ranking.sort_values(by="Score Promedio", ascending=False)

        chart_ranking = alt.Chart(df_ranking).mark_bar(cornerRadiusTopRight=6, cornerRadiusBottomRight=6).encode(
            x=alt.X("Score Promedio:Q", title="Calificación Promedio (%)", scale=alt.Scale(domain=[0, 100])),
            y=alt.Y("Edificio:N", sort="-x", title=""),
            color=alt.Color(
                "Score Promedio:Q",
                scale=alt.Scale(domain=[70, 85, 100], range=["#EF4444", "#0284C7", "#10B981"]),
                legend=None
            ),
            tooltip=["Edificio", alt.Tooltip("Score Promedio:Q", format=".1f")]
        ).properties(height=280)

        st.altair_chart(chart_ranking, use_container_width=True)

    with col_g2:
        st.markdown("### 📈 Evolución Temporal de Calidad")
        df_evol = df.sort_values(by="fecha_inspeccion")
        
        chart_evol = alt.Chart(df_evol).mark_line(point=True, strokeWidth=3).encode(
            x=alt.X("fecha_inspeccion:T", title="Fecha de Supervisión"),
            y=alt.Y("score_global:Q", title="Score Obtenido (%)", scale=alt.Scale(domain=[50, 100])),
            color=alt.Color("edificio_nombre:N", title="Edificio"),
            tooltip=["fecha_inspeccion", "edificio_nombre", alt.Tooltip("score_global:Q", format=".1f")]
        ).properties(height=280)

        st.altair_chart(chart_evol, use_container_width=True)

    # 3. DISTRIBUCIÓN DE CALIFICACIONES Y DOTACIÓN
    col_d1, col_d2 = st.columns(2)

    with col_d1:
        st.markdown("### 🎯 Desglose de Evaluaciones (C / R / NC / NA)")
        total_c = df["total_conformes"].sum()
        total_r = df["total_regulares"].sum()
        total_nc = df["total_no_conformes"].sum()
        total_na = df["total_no_aplica"].sum()

        df_pie = pd.DataFrame({
            "Estado": ["Conformes (C)", "Regulares (R)", "No Conformes (NC)", "No Aplica (NA)"],
            "Cantidad": [total_c, total_r, total_nc, total_na],
            "Color": ["#10B981", "#F59E0B", "#EF4444", "#94A3B8"]
        })

        chart_pie = alt.Chart(df_pie).mark_arc(innerRadius=50).encode(
            theta=alt.Theta("Cantidad:Q"),
            color=alt.Color("Estado:N", scale=alt.Scale(
                domain=df_pie["Estado"].tolist(),
                range=df_pie["Color"].tolist()
            ), legend=alt.Legend(title="Dictamen")),
            tooltip=["Estado", "Cantidad"]
        ).properties(height=260)

        st.altair_chart(chart_pie, use_container_width=True)

    with col_d2:
        st.markdown("### 👥 Asistencia de Operarios por Turno")
        df_turno = df.groupby("turno").agg({
            "personal_programado": "sum",
            "personal_presente": "sum",
            "personal_faltante": "sum"
        }).reset_index()

        df_melt = pd.melt(df_turno, id_vars=["turno"], value_vars=["personal_presente", "personal_faltante"],
                          var_name="Tipo", value_name="Operarios")
        df_melt["Tipo"] = df_melt["Tipo"].replace({"personal_presente": "Presentes", "personal_faltante": "Faltantes"})

        chart_turno = alt.Chart(df_melt).mark_bar().encode(
            x=alt.X("turno:N", title="Turno Operativo"),
            y=alt.Y("Operarios:Q", title="Total Personal"),
            color=alt.Color("Tipo:N", scale=alt.Scale(domain=["Presentes", "Faltantes"], range=["#0284C7", "#EF4444"])),
            tooltip=["turno", "Tipo", "Operarios"]
        ).properties(height=260)

        st.altair_chart(chart_turno, use_container_width=True)

    # 4. ANÁLISIS DE CAUSA RAÍZ (DIAGRAMA DE PARETO 80/20)
    st.markdown("---")
    st.markdown("### 🔍 Análisis de Causa Raíz (Diagrama de Pareto — Criterios con Mayor Frecuencia de Falla)")
    st.caption("Identificación de los puntos críticos de control donde se concentra el mayor número de observaciones y no conformidades (Regla 80/20).")

    from database import obtener_estadisticas_causa_raiz
    datos_pareto = obtener_estadisticas_causa_raiz()

    if datos_pareto:
        df_p = pd.DataFrame(datos_pareto)
        col_p1, col_p2 = st.columns([2, 1])

        with col_p1:
            # Gráfico de barras de fallas
            chart_bar = alt.Chart(df_p).mark_bar(color="#EF4444").encode(
                x=alt.X("item_criterio:N", sort="-y", title="Criterio Técnico Observado", axis=alt.Axis(labelAngle=-45, labelLimit=180)),
                y=alt.Y("total_fallas:Q", title="Total Observaciones (NC + R)"),
                tooltip=["item_criterio", "nombre_area", "total_fallas", alt.Tooltip("pct_acumulado:Q", format=".1f", title="% Acumulado")]
            )

            # Línea de porcentaje acumulado (Pareto)
            chart_line = alt.Chart(df_p).mark_line(color="#0284C7", point=True, strokeWidth=2.5).encode(
                x=alt.X("item_criterio:N", sort="-y"),
                y=alt.Y("pct_acumulado:Q", title="% Acumulado", scale=alt.Scale(domain=[0, 100]), axis=alt.Axis(orient="right")),
                tooltip=["item_criterio", alt.Tooltip("pct_acumulado:Q", format=".1f", title="% Acumulado")]
            )

            pareto_combined = alt.layer(chart_bar, chart_line).resolve_scale(
                y="independent"
            ).properties(height=320)

            st.altair_chart(pareto_combined, use_container_width=True)

        with col_p2:
            st.markdown("##### 📌 Top Hallazgos Recurrentes")
            for idx, r in enumerate(datos_pareto[:5]):
                st.markdown(f"**{idx+1}. {r['item_criterio']}**")
                st.caption(f"Área: *{r['nombre_area']}* | Fallas: `{r['total_fallas']}` ({r['pct_acumulado']:.1f}% acum.)")
    else:
        st.info("ℹ️ No hay registros suficientes de observaciones para calcular el Diagrama de Pareto.")

