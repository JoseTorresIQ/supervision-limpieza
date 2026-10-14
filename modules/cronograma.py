"""
Módulo de Cronograma y Planificador de Supervisiones:
Programación anticipada de visitas técnicas, asignación de cuadrillas/supervisores,
control de frecuencias contractuales y semáforo de auditorías vencidas.
"""
import io
import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta

from database import (
    obtener_cronograma, agregar_item_cronograma, actualizar_estado_cronograma, eliminar_item_cronograma,
    obtener_lista_edificios, obtener_lista_supervisores, obtener_tipos_inspeccion, obtener_turnos_trabajo,
    obtener_ultima_supervision_edificio
)


def render_modulo_cronograma():
    """Renderiza el planificador operativo y calendario de supervisiones."""
    st.markdown("""
        <div class="header-hero">
            <h1>📅 Cronograma & Planificador de Supervisiones</h1>
            <p>Planificación de auditorías técnicas, asignación de supervisores por edificio y alertas de control de frecuencia.</p>
            <div class="header-badges">
                <span class="badge-tag">🗓️ Calendario Operativo</span>
                <span class="badge-tag">🚨 Alerta >7 Días Sin Auditoría</span>
                <span class="badge-tag">👷 Asignación de Inspectores</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    edificios = obtener_lista_edificios(solo_activos=True)
    supervisores = obtener_lista_supervisores(solo_activos=True)
    tipos_insp = obtener_tipos_inspeccion(solo_activos=True)
    turnos = obtener_turnos_trabajo(solo_activos=True)

    # 1. ALERTA DE EDIFICIOS SIN AUDITAR EN > 7 DÍAS
    edificios_desatendidos = []
    hoy = date.today()
    for e in edificios:
        ult = obtener_ultima_supervision_edificio(e["nombre"])
        if ult:
            fec_ult = datetime.strptime(ult["fecha_inspeccion"], "%Y-%m-%d").date()
            dias_sin_auditoria = (hoy - fec_ult).days
            if dias_sin_auditoria > 7:
                edificios_desatendidos.append((e["nombre"], dias_sin_auditoria, ult["fecha_inspeccion"]))
        else:
            edificios_desatendidos.append((e["nombre"], "Nunca", "Sin registro"))

    if edificios_desatendidos:
        with st.expander(f"⚠️ Alerta Operativa: {len(edificios_desatendidos)} Edificios sin supervisión reciente (> 7 días)", expanded=True):
            st.warning("Los siguientes inmuebles superan el periodo de tolerancia contractual sin inspección técnica registrada:")
            for nom, dias, fec in edificios_desatendidos:
                st.markdown(f"- 🏢 **{nom}**: Última visita hace **{dias} días** (`{fec}`).")

    # 2. FILTROS Y KPI
    with st.expander("🔍 Filtros del Cronograma", expanded=False):
        c_f1, c_f2, c_f3 = st.columns(3)
        with c_f1:
            nombres_e = ["Todos"] + [e["nombre"] for e in edificios]
            f_edif = st.selectbox("Filtrar Edificio:", nombres_e, key="crono_f_edif")
        with c_f2:
            f_est = st.selectbox("Filtrar Estado:", ["Todos", "Programada", "Realizada", "Atrasada", "Cancelada"], key="crono_f_est")
        with c_f3:
            nombres_s = ["Todos"] + [s["nombre_completo"] for s in supervisores]
            f_sup = st.selectbox("Filtrar Supervisor:", nombres_s, key="crono_f_sup")

    tareas = obtener_cronograma(filtro_edificio=f_edif, filtro_estado=f_est, filtro_supervisor=f_sup)

    # Métricas
    hoy_str = hoy.strftime("%Y-%m-%d")
    total_prog = len(tareas)
    para_hoy = sum(1 for t in tareas if t.get("fecha_programada") == hoy_str and t.get("estado") == "Programada")
    realizadas = sum(1 for t in tareas if t.get("estado") == "Realizada")
    atrasadas = sum(1 for t in tareas if t.get("fecha_programada") < hoy_str and t.get("estado") == "Programada")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Programadas", total_prog)
    k2.metric("Programadas Hoy", para_hoy)
    k3.metric("Atrasadas / Vencidas", atrasadas, delta=f"-{atrasadas}" if atrasadas > 0 else "0", delta_color="inverse")
    k4.metric("Realizadas", realizadas)

    st.markdown("---")

    # Pestañas: Ver Programación vs Nueva Programación
    tab_list, tab_nueva = st.tabs(["📋 Inspecciones Programadas", "➕ Programar Nueva Visita"])

    with tab_nueva:
        st.markdown("### ➕ Registrar Nueva Supervisión en el Cronograma")
        with st.form("form_nueva_programacion", clear_on_submit=True):
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                edif_sel = st.selectbox("Edificio / Inmueble *:", [e["nombre"] for e in edificios], key="cr_edif")
                sup_sel = st.selectbox("Supervisor Asignado *:", [s["nombre_completo"] for s in supervisores], key="cr_sup")
                fecha_prog = st.date_input("Fecha Programada *:", value=date.today() + timedelta(days=1), key="cr_fecha")
            with col_p2:
                tipo_sel = st.selectbox("Tipo de Inspección *:", tipos_insp, key="cr_tipo")
                turno_sel = st.selectbox("Turno de Trabajo *:", turnos, key="cr_turno")
                obs = st.text_area("Objetivo / Enfoque Especial de la Visita:", placeholder="Ej: Revisión profunda de sótanos y cuarto de bombas.", key="cr_obs")

            if st.form_submit_button("📅 Guardar en el Cronograma", type="primary"):
                edif_obj = next((e for e in edificios if e["nombre"] == edif_sel), None)
                sup_obj = next((s for s in supervisores if s["nombre_completo"] == sup_sel), None)
                if edif_obj and sup_obj:
                    agregar_item_cronograma(
                        edificio_id=edif_obj["id"],
                        edificio_nombre=edif_sel,
                        supervisor_id=sup_obj["id"],
                        supervisor_nombre=sup_sel,
                        fecha_programada=str(fecha_prog),
                        tipo_inspeccion=tipo_sel,
                        turno=turno_sel,
                        observaciones=obs.strip()
                    )
                    st.success(f"✅ Inspección programada exitosamente para '{edif_sel}' el {fecha_prog}.")
                    st.rerun()

    with tab_list:
        if not tareas:
            st.info("No hay tareas programadas en el cronograma con los filtros seleccionados.")
            return

        # Exportar cronograma
        df_crono = pd.DataFrame(tareas)[[
            "id", "fecha_programada", "edificio_nombre", "tipo_inspeccion",
            "turno", "supervisor_nombre", "estado", "observaciones"
        ]]
        df_crono.columns = ["ID", "Fecha Programada", "Edificio", "Tipo Inspección", "Turno", "Supervisor", "Estado", "Observaciones"]

        excel_buf = io.BytesIO()
        with pd.ExcelWriter(excel_buf, engine='openpyxl') as writer:
            df_crono.to_excel(writer, index=False, sheet_name="Cronograma_Supervisiones")
        excel_buf.seek(0)

        col_d1, col_d2 = st.columns([3, 1])
        with col_d2:
            st.download_button(
                label="📊 Exportar Cronograma (.xlsx)",
                data=excel_buf,
                file_name=f"Cronograma_Supervisiones_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        for t in tareas:
            fec = t["fecha_programada"]
            est = t["estado"]
            es_vencida = (fec < hoy_str and est == "Programada")

            if est == "Realizada":
                badge_t = "🟢 REALIZADA"
            elif es_vencida:
                badge_t = "🔴 ATRASADA"
            elif est == "Cancelada":
                badge_t = "⚪ CANCELADA"
            else:
                badge_t = "🔵 PROGRAMADA"

            with st.container():
                c1, c2, c3, c4 = st.columns([1.5, 2.5, 2, 1.5])
                with c1:
                    st.markdown(f"**{badge_t}**\n\n📅 `{fec}`")
                with c2:
                    st.markdown(f"🏢 **{t['edificio_nombre']}**\n\n📋 *{t['tipo_inspeccion']}*")
                with c3:
                    st.markdown(f"👷 **{t['supervisor_nombre']}**\n\n⏰ *{t.get('turno', '')}*")
                with c4:
                    if est == "Programada":
                        if st.button("Marcar Realizada", key=f"btn_rea_{t['id']}", use_container_width=True):
                            actualizar_estado_cronograma(t["id"], "Realizada")
                            st.rerun()
                        if st.button("Eliminar", key=f"btn_del_cr_{t['id']}", use_container_width=True):
                            eliminar_item_cronograma(t["id"])
                            st.rerun()
                    else:
                        st.caption(f"Estado: {est}")
                st.markdown("---")
