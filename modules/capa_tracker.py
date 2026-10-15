"""
Módulo de Seguimiento de Incidencias y Plan de Acción (CAPA Tracker):
Ciclo de vida completo de no conformidades, levantamiento de observaciones con foto "Después",
control de plazos (SLA) y emisión de Acta de Subsanación de Hallazgos.
"""
import os
import io
import streamlit as st
import pandas as pd
from datetime import datetime, date
from PIL import Image

from config import UPLOADS_DIR
from database import (
    obtener_todas_incidencias, actualizar_estado_incidencia,
    obtener_lista_edificios, obtener_lista_supervisores
)


def render_modulo_capa():
    """Renderiza la vista principal del CAPA Tracker para gestión de no conformidades."""
    st.markdown("""
        <div class="header-hero">
            <h1>🚨 Seguimiento de Incidencias & Plan de Acción (CAPA)</h1>
            <p>Control de hallazgos, registro de subsanaciones con evidencia fotográfica 'Después' y cumplimiento de plazos SLA.</p>
            <div class="header-badges">
                <span class="badge-tag">🛡️ Corrective Actions</span>
                <span class="badge-tag">⏱️ Control de SLA</span>
                <span class="badge-tag">📸 Evidencia 'Después'</span>
                <span class="badge-tag">✅ Certificación de Calidad</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    edificios = obtener_lista_edificios(solo_activos=False)
    nombres_edif = ["Todos"] + [e["nombre"] for e in edificios]

    # Filtros de búsqueda
    with st.expander("🔍 Filtros de Búsqueda de Incidencias", expanded=True):
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            filtro_edif = st.selectbox("Filtrar por Edificio:", nombres_edif, key="capa_f_edif")
        with col_f2:
            filtro_est = st.selectbox("Filtrar por Estado:", ["Todos", "Pendiente", "En Proceso", "Subsanada"], key="capa_f_est")
        with col_f3:
            filtro_sev = st.selectbox("Filtrar por Severidad:", ["Todos", "Crítica", "Alta", "Media", "Baja"], key="capa_f_sev")

    # Consultar datos
    incidencias = obtener_todas_incidencias(
        filtro_edificio=filtro_edif,
        filtro_estado=filtro_est,
        filtro_severidad=filtro_sev
    )

    # Tarjetas Métricas KPI
    total_inc = len(incidencias)
    pendientes = sum(1 for i in incidencias if i.get("estado_subsanacion") == "Pendiente")
    en_proceso = sum(1 for i in incidencias if i.get("estado_subsanacion") == "En Proceso")
    subsanadas = sum(1 for i in incidencias if i.get("estado_subsanacion") == "Subsanada")
    tasa_cierre = (subsanadas / total_inc * 100.0) if total_inc > 0 else 100.0

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.metric("Total Incidencias", total_inc)
    with kpi2:
        st.metric("Pendientes", pendientes, delta=f"-{pendientes}" if pendientes > 0 else "0", delta_color="inverse")
    with kpi3:
        st.metric("En Proceso", en_proceso)
    with kpi4:
        st.metric("Tasa de Cierre (SLA)", f"{tasa_cierre:.1f}%")

    st.markdown("---")

    if not incidencias:
        st.info("🎉 ¡Excelente! No hay incidencias registradas con los filtros seleccionados.")
        return

    # Descarga rápida en Excel del reporte CAPA
    df_capa = pd.DataFrame(incidencias)
    cols_excel = [
        "codigo_informe", "fecha_inspeccion", "edificio_nombre", "area_nombre",
        "descripcion_hallazgo", "severidad", "accion_correctiva", "plazo_subsanacion",
        "responsable", "estado_subsanacion", "fecha_subsanacion", "cerrado_por", "comentario_cierre"
    ]
    df_excel_capa = df_capa[[c for c in cols_excel if c in df_capa.columns]]

    buf_excel = io.BytesIO()
    with pd.ExcelWriter(buf_excel, engine='openpyxl') as writer:
        df_excel_capa.to_excel(writer, index=False, sheet_name="Matriz_CAPA_Incidencias")
    buf_excel.seek(0)

    col_btn1, col_btn2 = st.columns([3, 1])
    with col_btn2:
        st.download_button(
            label="📊 Descargar Matriz CAPA (.xlsx)",
            data=buf_excel,
            file_name=f"Matriz_CAPA_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    # Listado interactivo de incidencias
    st.markdown("### 📋 Listado Detallado de No Conformidades")

    for idx, inc in enumerate(incidencias):
        estado = inc.get("estado_subsanacion", "Pendiente")
        sev = inc.get("severidad", "Media")
        
        # Color del badge
        if estado == "Subsanada":
            badge_estado = "🟢 SUBSANADA"
        elif estado == "En Proceso":
            badge_estado = "🟡 EN PROCESO"
        else:
            badge_estado = "🔴 PENDIENTE"

        sev_badge = f"⚠️ {sev.upper()}" if sev in ["Alta", "Crítica"] else f"ℹ️ {sev}"

        with st.expander(f"{badge_estado} | {inc['edificio_nombre']} — {inc['area_nombre']} ({inc['codigo_informe']}) - {sev_badge}", expanded=(estado != "Subsanada")):
            c_info1, c_info2 = st.columns([2, 1])
            with c_info1:
                st.markdown(f"**Hallazgo / Observación:** {inc['descripcion_hallazgo']}")
                st.markdown(f"**Acción Correctiva Planteada:** {inc['accion_correctiva']}")
                st.markdown(f"**Plazo Estipulado:** `{inc.get('plazo_subsanacion', '24 horas')}` | **Responsable:** `{inc.get('responsable', 'Supervisor')}`")
                st.caption(f"📅 Fecha de Inspección: {inc.get('fecha_inspeccion')} | Supervisor: {inc.get('supervisor_nombre')}")

                if estado == "Subsanada":
                    st.success(f"✅ **Subsanada el:** {inc.get('fecha_subsanacion', 'N/D')} | **Validado por:** {inc.get('cerrado_por', 'Supervisor')}")
                    if inc.get("comentario_cierre"):
                        st.info(f"💬 **Comentario de Cierre:** {inc['comentario_cierre']}")

            with c_info2:
                foto_hallazgo = inc.get("foto_hallazgo_ruta")
                foto_despues = inc.get("foto_subsanacion_ruta")
                if foto_hallazgo and os.path.exists(foto_hallazgo):
                    st.image(foto_hallazgo, caption="📸 Hallazgo Inicial (Antes)", use_container_width=True)
                if foto_despues and os.path.exists(foto_despues):
                    st.image(foto_despues, caption="📸 Evidencia de Subsanación (Después)", use_container_width=True)
                elif not foto_hallazgo:
                    st.caption("📸 Sin fotografías adjuntas.")

            # Formulario para actualizar o levantar observación
            st.markdown("---")
            st.markdown("#### ✍️ Actualizar Estado / Subsanar Observación")

            with st.form(f"form_subsanar_{inc['id']}"):
                col_sub1, col_sub2 = st.columns(2)
                with col_sub1:
                    nuevo_est = st.selectbox(
                        "Cambiar Estado a:",
                        ["Pendiente", "En Proceso", "Subsanada"],
                        index=["Pendiente", "En Proceso", "Subsanada"].index(estado) if estado in ["Pendiente", "En Proceso", "Subsanada"] else 0,
                        key=f"sel_est_{inc['id']}"
                    )
                    fecha_sub = st.date_input("Fecha de Subsanación:", value=date.today(), key=f"fec_sub_{inc['id']}")
                    validador = st.text_input("Validado / Subsanado Por:", value=inc.get("responsable", "Líder de Cuadrilla"), key=f"val_{inc['id']}")

                with col_sub2:
                    comentario = st.text_area("Comentario / Detalle de la Solución:", value=inc.get("comentario_cierre", ""), placeholder="Ej: Se realizó lavado con amonio cuaternario y abrillantado de griferías.", key=f"com_{inc['id']}")
                    foto_sub_file = st.file_uploader("📸 Adjuntar Foto de Evidencia 'Después':", type=["jpg", "jpeg", "png"], key=f"foto_sub_{inc['id']}")

                if st.form_submit_button("💾 Guardar Actualización de Incidencia", type="primary"):
                    ruta_guardada = inc.get("foto_subsanacion_ruta", "")
                    if foto_sub_file:
                        nom_archivo = f"subsanacion_{inc['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                        ruta_dest = UPLOADS_DIR / nom_archivo
                        with open(ruta_dest, "wb") as f_out:
                            f_out.write(foto_sub_file.getbuffer())
                        ruta_guardada = str(ruta_dest)

                    actualizar_estado_incidencia(
                        incidencia_id=inc["id"],
                        nuevo_estado=nuevo_est,
                        fecha_subsanacion=str(fecha_sub) if nuevo_est == "Subsanada" else "",
                        foto_subsanacion_ruta=ruta_guardada,
                        comentario_cierre=comentario.strip(),
                        cerrado_por=validador.strip()
                    )
                    st.success("✅ Incidencia actualizada correctamente.")
                    st.rerun()
