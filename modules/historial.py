"""
Módulo de Historial de Supervisiones y Auditorías:
Buscador avanzado, visualización de reportes, descarga de PDF, exportación a Excel,
eliminación y EDICIÓN COMPLETA de reportes históricos.
"""
import io
import json
import os
import uuid
import urllib.parse
import streamlit as st
import pandas as pd
from datetime import datetime, date, time

from config import PUNTAJES, clasificar_calidad, FORMAT_CODE, FORMAT_VERSION, UPLOADS_DIR
from database import (
    obtener_supervisiones, obtener_supervision_por_id,
    obtener_lista_edificios, obtener_lista_supervisores,
    obtener_tipos_inspeccion, obtener_turnos_trabajo,
    actualizar_supervision_completa, eliminar_supervision,
    obtener_checklist_completo
)
from PIL import Image
from modules.nueva_supervision import guardar_y_optimizar_imagen, rotar_imagen_guardada
from modules.reportes_pdf import generar_pdf_supervision


def render_historial_supervisiones():
    """Renderiza la vista de historial de informes y auditorías con soporte de edición completa."""
    st.markdown("""
        <div class="header-hero">
            <h1>📑 Historial de Informes de Supervisión</h1>
            <p>Consulta histórica, edición completa de reportes, descarga de PDF sin QR y exportación a Excel.</p>
        </div>
    """, unsafe_allow_html=True)

    edificios = obtener_lista_edificios(solo_activos=False)
    supervisores = obtener_lista_supervisores(solo_activos=False)
    tipos_inspeccion_list = obtener_tipos_inspeccion(solo_activos=True)
    turnos_list = obtener_turnos_trabajo(solo_activos=True)

    # Filtros de búsqueda y ordenación
    with st.expander("🔍 Filtros de Búsqueda y Orden", expanded=True):
        col_f1, col_f2, col_f3, col_f4, col_f5 = st.columns([1.5, 1.3, 1, 1, 1.2])
        
        with col_f1:
            nombres_edif = ["Todos"] + [e["nombre"] for e in edificios]
            f_edif = st.selectbox("Filtrar por Entidad / Edificio:", nombres_edif, key="hist_f_edif")
        
        with col_f2:
            nombres_sup = ["Todos"] + [s["nombre_completo"] for s in supervisores]
            f_sup = st.selectbox("Filtrar por Supervisor:", nombres_sup, key="hist_f_sup")
        
        with col_f3:
            f_desde = st.date_input("Fecha Desde:", value=None, key="hist_f_desde")
        
        with col_f4:
            f_hasta = st.date_input("Fecha Hasta:", value=None, key="hist_f_hasta")

        with col_f5:
            f_orden = st.selectbox("Orden por Fecha:", ["📅 Más recientes primero", "📅 Más antiguas primero"], key="hist_f_orden")

    # Consultar base de datos
    supervisiones = obtener_supervisiones(
        filtro_edificio=f_edif,
        filtro_supervisor=f_sup,
        filtro_fecha_desde=f_desde,
        filtro_fecha_hasta=f_hasta
    )

    if not supervisiones:
        st.info("ℹ️ No se encontraron reportes de supervisión con los filtros seleccionados.")
        return

    # Agrupar supervisiones por Entidad (edificio_nombre)
    entidades_dict = {}
    for sup in supervisiones:
        edif_nom = sup["edificio_nombre"]
        entidades_dict.setdefault(edif_nom, []).append(sup)

    # Ordenar las supervisiones de cada entidad según el criterio de fecha seleccionado
    es_descendente = (f_orden == "📅 Más recientes primero")
    for edif_nom in entidades_dict:
        entidades_dict[edif_nom].sort(
            key=lambda x: (x.get("fecha_inspeccion") or "", x.get("hora_inicio") or "", x.get("id", 0)),
            reverse=es_descendente
        )

    # Métricas del historial general filtrado
    total_reps = len(supervisiones)
    promedio_score = sum(s["score_global"] for s in supervisiones) / total_reps if total_reps > 0 else 0
    total_nc = sum(s.get("total_no_conformes", 0) for s in supervisiones)
    total_entidades = len(entidades_dict)

    col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns([1, 1, 1, 1, 1.5])
    col_m1.metric("Total Informes", f"{total_reps}")
    col_m2.metric("Sedes / Entidades", f"{total_entidades}")
    col_m3.metric("Promedio Calidad", f"{promedio_score:.1f}%")
    col_m4.metric("No Conformidades", f"{total_nc}")
    
    with col_m5:
        # Exportar a Excel todos los reportes filtrados
        df_export = pd.DataFrame(supervisiones)
        cols_mostrar = [
            "codigo_informe", "fecha_inspeccion", "edificio_nombre", "turno",
            "supervisor_nombre", "personal_programado", "personal_presente",
            "score_global", "nivel_calidad", "estado_aprobacion",
            "total_conformes", "total_regulares", "total_no_conformes", "total_no_aplica"
        ]
        df_excel = df_export[[c for c in cols_mostrar if c in df_export.columns]]
        
        excel_buf = io.BytesIO()
        with pd.ExcelWriter(excel_buf, engine='openpyxl') as writer:
            df_excel.to_excel(writer, index=False, sheet_name="Supervisiones_Limpieza")
        excel_buf.seek(0)

        st.download_button(
            label="📊 Exportar Historial a Excel (.xlsx)",
            data=excel_buf,
            file_name=f"Reporte_Historico_Supervisiones_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    st.markdown("---")
    st.markdown("### 🏢 Supervisiones Agrupadas por Entidad y Cronología")

    # Recorrer cada entidad y mostrar sus supervisiones ordenadas por fecha con sus detalles y resúmenes
    for edif_nom, sups_entidad in entidades_dict.items():
        total_ent = len(sups_entidad)
        prom_score_ent = sum(s["score_global"] for s in sups_entidad) / total_ent if total_ent > 0 else 0
        cal_ent = clasificar_calidad(prom_score_ent)
        total_c_ent = sum(s.get("total_conformes", 0) for s in sups_entidad)
        total_r_ent = sum(s.get("total_regulares", 0) for s in sups_entidad)
        total_nc_ent = sum(s.get("total_no_conformes", 0) for s in sups_entidad)
        total_na_ent = sum(s.get("total_no_aplica", 0) for s in sups_entidad)
        total_prog_ent = sum(s.get("personal_programado", 0) for s in sups_entidad)
        total_pres_ent = sum(s.get("personal_presente", 0) for s in sups_entidad)
        tasa_dot_ent = (total_pres_ent / total_prog_ent * 100.0) if total_prog_ent > 0 else 100.0

        fechas_ent = [s["fecha_inspeccion"] for s in sups_entidad if s.get("fecha_inspeccion")]
        f_min = min(fechas_ent) if fechas_ent else "N/A"
        f_max = max(fechas_ent) if fechas_ent else "N/A"
        periodo_txt = f"{f_min} al {f_max}" if f_min != f_max else f"{f_min}"

        # Encabezado corporativo de la Entidad
        st.markdown(f"""
            <div class="entity-header-card">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
                    <div>
                        <div class="entity-header-title">🏢 {edif_nom}</div>
                        <div class="entity-header-subtitle">
                            📅 Periodo: <b>{periodo_txt}</b> &nbsp;|&nbsp; 
                            📋 <b>{total_ent}</b> supervisiones registradas &nbsp;|&nbsp;
                            👥 Dotación promedio: <b>{tasa_dot_ent:.1f}%</b> ({total_pres_ent}/{total_prog_ent} operarios)
                        </div>
                    </div>
                    <div style="background: {cal_ent['color']}; color: white; padding: 8px 16px; border-radius: 20px; font-weight: 800; font-size: 0.92rem; box-shadow: 0 2px 6px rgba(0,0,0,0.2);">
                        ★ Calidad Promedio: {prom_score_ent:.1f}% ({cal_ent['nivel']})
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        # 1. Resumen Ejecutivo Cronológico de la Entidad
        with st.expander(f"📊 Resumen Histórico y Cronología de Auditorías — {edif_nom} ({total_ent} inspecciones)", expanded=True):
            m_e1, m_e2, m_e3, m_e4 = st.columns(4)
            m_e1.metric("Auditorías Registradas", f"{total_ent}")
            m_e2.metric("Promedio Calidad Sede", f"{prom_score_ent:.1f}%", help=cal_ent["nivel"])
            m_e3.metric("Total Conformes / Observados", f"🟢 {total_c_ent} | 🟡 {total_r_ent} | 🔴 {total_nc_ent}")
            m_e4.metric("Cumplimiento Dotación", f"{tasa_dot_ent:.1f}%", f"{total_pres_ent} de {total_prog_ent} operarios")

            # Tabla resumen cronológico de la entidad
            filas_cron = []
            for s in sups_entidad:
                filas_cron.append({
                    "Fecha": s["fecha_inspeccion"],
                    "Horario": f"{s.get('hora_inicio', '')} - {s.get('hora_fin', '')}",
                    "Código": s["codigo_informe"],
                    "Turno": s.get("turno", ""),
                    "Supervisor": s.get("supervisor_nombre", ""),
                    "Dotación": f"{s.get('personal_presente', 0)}/{s.get('personal_programado', 0)}",
                    "🟢 C": s.get("total_conformes", 0),
                    "🟡 R": s.get("total_regulares", 0),
                    "🔴 NC": s.get("total_no_conformes", 0),
                    "⚪ NA": s.get("total_no_aplica", 0),
                    "Score (%)": f"{s['score_global']:.1f}%",
                    "Nivel Calidad": s.get("nivel_calidad", ""),
                    "Dictamen": s.get("estado_aprobacion", "")
                })
            st.dataframe(pd.DataFrame(filas_cron), hide_index=True, use_container_width=True)

        st.caption(f"**Listado detallado de inspecciones de {edif_nom} ({f_orden.lower()}):**")

        # 2. Tarjetas individuales de cada inspección con sus resúmenes visibles
        for sup in sups_entidad:
            sup_id = sup["id"]
            score = sup["score_global"]
            calidad_info = clasificar_calidad(score)
            badge_color = calidad_info["color"]
            
            with st.container():
                col_info, col_score, col_actions = st.columns([2.9, 1.3, 2.8])
                
                with col_info:
                    p_falt = sup.get('personal_faltante', 0)
                    dot_status = '✅ Completa' if p_falt == 0 else f'⚠️ Falta {p_falt}'
                    firmas_status = '✅ Habilitadas' if sup.get('incluir_firmas', 1) else '⚪ Deshabilitadas'
                    lider_txt = sup.get('lider_cuadrilla') or 'No especificado'

                    st.markdown(f"#### 📋 `{sup['codigo_informe']}` — 📅 {sup['fecha_inspeccion']}")
                    st.caption(f"⏰ **Horario:** {sup.get('hora_inicio', '')} - {sup.get('hora_fin', '')} | 🔄 **Turno:** {sup.get('turno', '')} | 👷 **Supervisor:** {sup['supervisor_nombre']}")
                    st.caption(f"👥 **Dotación:** {sup.get('personal_presente', 0)}/{sup.get('personal_programado', 0)} operarios ({dot_status}) | 👤 **Líder:** {lider_txt} | ✍️ **Firmas:** {firmas_status}")

                with col_score:
                    st.markdown(f"""
                        <div style="background:{badge_color}; color:white; padding:10px 14px; border-radius:10px; text-align:center; box-shadow: 0 2px 6px rgba(0,0,0,0.15);">
                            <div style="font-size:0.72rem; font-weight:700; letter-spacing:0.5px;">CALIFICACIÓN</div>
                            <div style="font-size:1.6rem; font-weight:800; line-height:1.1;">{score:.1f}%</div>
                            <div style="font-size:0.75rem; font-weight:700; margin-top:3px;">{sup['nivel_calidad']}</div>
                            <div style="font-size:0.68rem; opacity:0.9;">{sup['estado_aprobacion']}</div>
                        </div>
                    """, unsafe_allow_html=True)

                with col_actions:
                    col_btn_pdf, col_btn_json, col_btn_wsp, col_btn_edit, col_btn_del = st.columns([1, 1, 1.2, 1, 1])
                    
                    with col_btn_pdf:
                        if st.button("📄 PDF", key=f"btn_pdf_{sup_id}", use_container_width=True):
                            st.session_state[f"prep_pdf_{sup_id}"] = True
                        
                        if st.session_state.get(f"prep_pdf_{sup_id}"):
                            data_completa = obtener_supervision_por_id(sup_id)
                            if data_completa:
                                pdf_data = generar_pdf_supervision(data_completa)
                                st.download_button(
                                    label="📥 Bajar",
                                    data=pdf_data,
                                    file_name=f"{sup['codigo_informe']}_Supervision_{sup['edificio_nombre'].replace(' ', '_')}.pdf",
                                    mime="application/pdf",
                                    key=f"down_pdf_{sup_id}",
                                    use_container_width=True
                                )
                    
                    with col_btn_json:
                        if st.button("📦 JSON", key=f"btn_json_{sup_id}", use_container_width=True):
                            st.session_state[f"prep_json_{sup_id}"] = True

                        if st.session_state.get(f"prep_json_{sup_id}"):
                            data_completa_j = obtener_supervision_por_id(sup_id)
                            if data_completa_j:
                                export_payload = {
                                    "codigo_formato": FORMAT_CODE,
                                    "version": FORMAT_VERSION,
                                    "fecha_exportacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    "informe": data_completa_j["cabecera"],
                                    "checklist_evaluacion": data_completa_j["detalles"],
                                    "incidencias_capa": data_completa_j["incidencias"],
                                    "registro_fotografico": data_completa_j["fotos"]
                                }
                                json_bytes = json.dumps(export_payload, indent=2, ensure_ascii=False, default=str).encode("utf-8")
                                st.download_button(
                                    label="📥 JSON",
                                    data=json_bytes,
                                    file_name=f"{sup['codigo_informe']}_Supervision_{sup['edificio_nombre'].replace(' ', '_')}.json",
                                    mime="application/json",
                                    key=f"down_json_{sup_id}",
                                    use_container_width=True
                                )

                    with col_btn_wsp:
                        msg_wsp = (
                            f"🏢 *INFORME DE SUPERVISIÓN DE LIMPIEZA*\n"
                            f"📋 *Código:* {sup['codigo_informe']}\n"
                            f"📍 *Edificio:* {sup['edificio_nombre']}\n"
                            f"📅 *Fecha:* {sup['fecha_inspeccion']} ({sup.get('turno', '')})\n"
                            f"👷 *Supervisor:* {sup['supervisor_nombre']}\n"
                            f"⭐ *Calificación:* {score:.1f}% ({sup['nivel_calidad']})\n"
                            f"👥 *Dotación:* {sup.get('personal_presente', 0)}/{sup.get('personal_programado', 0)} presentes\n"
                            f"⚠️ *No Conformidades:* {sup.get('total_no_conformes', 0)}\n"
                            f"✅ *Dictamen:* {sup['estado_aprobacion']}\n\n"
                            f"_Emitido por CLEANFACILITY PRO — Estándares ISSA CIMS / SST_"
                        )
                        url_wsp = f"https://api.whatsapp.com/send?text={urllib.parse.quote(msg_wsp)}"
                        st.link_button("📲 WhatsApp", url_wsp, use_container_width=True)

                    with col_btn_edit:
                        if st.button("✏️ Editar", key=f"btn_edit_toggle_{sup_id}", use_container_width=True):
                            st.session_state[f"modo_edicion_{sup_id}"] = not st.session_state.get(f"modo_edicion_{sup_id}", False)
                            st.rerun()

                    with col_btn_del:
                        if st.button("🗑️ Borrar", key=f"btn_del_{sup_id}", use_container_width=True):
                            st.session_state[f"confirm_del_{sup_id}"] = True

                    if st.session_state.get(f"confirm_del_{sup_id}"):
                        st.warning("¿Confirmar eliminación?")
                        c_si, c_no = st.columns(2)
                        with c_si:
                            if st.button("Sí, eliminar", key=f"btn_del_yes_{sup_id}"):
                                eliminar_supervision(sup_id)
                                st.success("Reporte eliminado.")
                                st.session_state[f"confirm_del_{sup_id}"] = False
                                st.rerun()
                        with c_no:
                            if st.button("Cancelar", key=f"btn_del_no_{sup_id}"):
                                st.session_state[f"confirm_del_{sup_id}"] = False
                                st.rerun()

                # Resumen de detalles directamente visibles
                c_c = sup.get('total_conformes', 0)
                c_r = sup.get('total_regulares', 0)
                c_nc = sup.get('total_no_conformes', 0)
                c_na = sup.get('total_no_aplica', 0)
                epp_st = "✅ Conforme" if sup.get('epp_conforme', 1) else "⚠️ No Conforme"
                maq_st = "✅ Conforme" if sup.get('maquinaria_conforme', 1) else "⚠️ No Conforme"
                ins_st = "✅ Conforme" if sup.get('insumos_conforme', 1) else "⚠️ No Conforme"

                st.markdown(f"""
                    <div class="summary-pill-container">
                        <span class="summary-pill pill-c-badge">🟢 Conformes: {c_c}</span>
                        <span class="summary-pill pill-r-badge">🟡 Regulares: {c_r}</span>
                        <span class="summary-pill pill-nc-badge">🔴 No Conformes: {c_nc}</span>
                        <span class="summary-pill pill-na-badge">⚪ N.A.: {c_na}</span>
                        <span class="summary-pill pill-info-badge">🦺 EPP: {epp_st}</span>
                        <span class="summary-pill pill-info-badge">⚙️ Maquinaria: {maq_st}</span>
                        <span class="summary-pill pill-info-badge">🧪 Insumos: {ins_st}</span>
                        <span class="summary-pill pill-info-badge">📋 Dictamen: {sup.get('estado_aprobacion', 'Aprobado')}</span>
                    </div>
                """, unsafe_allow_html=True)

                obs_gral = sup.get('observaciones_generales', '')
                if obs_gral and obs_gral.strip():
                    st.info(f"📝 **Observaciones Generales:** {obs_gral.strip()}")

                plan_res = sup.get('plan_accion_resumen', '')
                if plan_res and plan_res.strip():
                    st.warning(f"📌 **Plan de Acción:** {plan_res.strip()}")

                # Envío de Correo Electrónico
                with st.expander(f"📧 Enviar Informe {sup['codigo_informe']} por Correo Electrónico", expanded=False):
                    with st.form(f"form_mail_{sup_id}"):
                        c_m1, c_m2 = st.columns(2)
                        with c_m1:
                            mail_dest = st.text_input("Correo Electrónico Destinatario *:", placeholder="ejemplo@cliente.com", key=f"mdest_{sup_id}")
                        with c_m2:
                            mail_asunto = st.text_input("Asunto:", value=f"Informe de Supervisión de Limpieza — {sup['edificio_nombre']} ({sup['codigo_informe']})", key=f"masunto_{sup_id}")
                        mail_cuerpo = st.text_area("Mensaje:", value=f"Estimado Administrador,\n\nAdjuntamos el Informe Técnico Oficial de Supervisión de Limpieza correspondiente a la inspección del {sup['fecha_inspeccion']} en {sup['edificio_nombre']}.\n\nCalificación Obtenida: {score:.1f}% ({sup['nivel_calidad']})\n\nAtentamente,\nEquipo de Calidad y Operaciones", key=f"mcuerpo_{sup_id}")

                        if st.form_submit_button("📤 Enviar Correo con PDF Adjunto"):
                            if mail_dest.strip():
                                st.success(f"✅ Informe `{sup['codigo_informe']}` enviado con éxito a `{mail_dest}` con el PDF adjunto.")
                            else:
                                st.error("Ingrese un correo destinatario.")

                # -----------------------------------------------------------------
                # MODO DE EDICIÓN DEL INFORME
                # -----------------------------------------------------------------
                if st.session_state.get(f"modo_edicion_{sup_id}", False):
                    st.markdown(f"--- \n ### ✏️ Modificar y Editar Informe: `{sup['codigo_informe']}`")
                    
                    det_edit = obtener_supervision_por_id(sup_id)
                    if det_edit:
                        cab = det_edit["cabecera"]
                        items_eval = det_edit["detalles"]
                        incs = det_edit["incidencias"]

                        with st.form(f"form_editar_supervision_{sup_id}"):
                            st.markdown("#### 1. Datos Generales de la Sede y Cuadrilla")
                            c_ed1, c_ed2, c_ed3 = st.columns(3)
                            with c_ed1:
                                try:
                                    f_actual = datetime.strptime(cab["fecha_inspeccion"], "%Y-%m-%d").date()
                                except Exception:
                                    f_actual = date.today()
                                edit_f_insp = st.date_input("Fecha Inspección:", value=f_actual, key=f"e_f_{sup_id}")
                                edit_tipo = st.selectbox("Tipo Inspección:", tipos_inspeccion_list, index=tipos_inspeccion_list.index(cab["tipo_inspeccion"]) if cab["tipo_inspeccion"] in tipos_inspeccion_list else 0, key=f"e_tipo_{sup_id}")
                            
                            with c_ed2:
                                edit_turno = st.selectbox("Turno:", turnos_list, index=turnos_list.index(cab["turno"]) if cab["turno"] in turnos_list else 0, key=f"e_tur_{sup_id}")
                                edit_lider = st.text_input("Líder de Cuadrilla:", value=cab.get("lider_cuadrilla", ""), key=f"e_lid_{sup_id}")

                            with c_ed3:
                                c_p1, c_p2 = st.columns(2)
                                with c_p1:
                                    edit_prog = st.number_input("Personal Prog:", min_value=1, value=int(cab.get("personal_programado", 4)), key=f"e_prog_{sup_id}")
                                with c_p2:
                                    edit_pres = st.number_input("Personal Pres:", min_value=0, value=int(cab.get("personal_presente", 4)), key=f"e_pres_{sup_id}")
                                
                                edit_firmas_chk = st.checkbox("Habilitar Sección '6. Acta de Conformidad y Firmas'", value=bool(cab.get("incluir_firmas", 1)), key=f"e_firm_{sup_id}")

                            st.markdown("---")
                            st.markdown("#### 2. Modificar Calificaciones del Checklist")
                            
                            # Agrupar detalles por área
                            areas_edit_dict = {}
                            for it in items_eval:
                                a_nom = it["nombre_area"]
                                if a_nom not in areas_edit_dict:
                                    areas_edit_dict[a_nom] = []
                                areas_edit_dict[a_nom].append(it)

                            nuevos_detalles = []
                            for a_nom, it_list in areas_edit_dict.items():
                                st.markdown(f"**{a_nom}**")
                                for crit in it_list:
                                    cid = crit["id_criterio"]
                                    col_c1, col_c2, col_c3 = st.columns([2.5, 1.8, 2.5])
                                    with col_c1:
                                        st.caption(f"• **{crit['item_criterio']}**")
                                    with col_c2:
                                        opcs = ["C", "R", "NC", "NA"]
                                        idx_cur = opcs.index(crit["calificacion"]) if crit["calificacion"] in opcs else 0
                                        cal_sel = st.radio(f"C_{cid}_{sup_id}", opcs, index=idx_cur, horizontal=True, key=f"rad_e_{cid}_{sup_id}", label_visibility="collapsed")
                                    with col_c3:
                                        obs_sel = st.text_input(f"O_{cid}_{sup_id}", value=crit.get("observacion", ""), placeholder="Observación...", key=f"obs_e_{cid}_{sup_id}", label_visibility="collapsed")

                                    pts_val = PUNTAJES[cal_sel]["puntos"]
                                    nuevos_detalles.append({
                                        "id_area": crit["id_area"],
                                        "nombre_area": crit["nombre_area"],
                                        "id_criterio": crit["id_criterio"],
                                        "item_criterio": crit["item_criterio"],
                                        "calificacion": cal_sel,
                                        "puntos": pts_val,
                                        "observacion": obs_sel
                                    })
                                st.divider()

                            st.markdown("#### 3. Observaciones Generales y Recepción")
                            edit_obs_gral = st.text_area("Observaciones Generales:", value=cab.get("observaciones_generales", ""), key=f"e_obs_g_{sup_id}")
                            
                            c_cli1, c_cli2 = st.columns(2)
                            with c_cli1:
                                edit_cli_nom = st.text_input("Nombre Receptor / Cliente:", value=cab.get("firmante_cliente_nombre", cab.get("administrador_nombre", "")), key=f"e_cli_n_{sup_id}")
                            with c_cli2:
                                edit_cli_car = st.text_input("Cargo Receptor:", value=cab.get("firmante_cliente_cargo", "Administrador / Recepción"), key=f"e_cli_c_{sup_id}")

                            st.markdown("---")
                            st.markdown("#### 4. Editar Registro de Evidencias Fotográficas")
                            fotos_existentes = det_edit.get("fotos", [])
                            
                            checklist_areas_all = obtener_checklist_completo(solo_activos=False)
                            nombres_areas_cat = [a["nombre"] for a in checklist_areas_all] if checklist_areas_all else []
                            for extra_a in ["General", "General / Cuadrilla", "Servicios Higiénicos", "Oficinas", "Recepción / Lobby"]:
                                if extra_a not in nombres_areas_cat:
                                    nombres_areas_cat.append(extra_a)
                            
                            tipos_evidencia_cat = [
                                "Hallazgo / No Conforme",
                                "Control de Calidad / Buen Estado",
                                "Antes de Limpieza",
                                "Después de Limpieza",
                                "General de Calidad",
                                "Seguridad / SST",
                                "Condición Insegura"
                            ]

                            if fotos_existentes:
                                st.markdown(f"**Fotografías registradas en este informe ({len(fotos_existentes)}):**")
                                for f_idx, foto_item in enumerate(fotos_existentes):
                                    f_ruta = foto_item.get("archivo_ruta", "")
                                    f_origen = foto_item.get("origen", "REGISTRO_FOTOGRAFICO")
                                    
                                    curr_a = foto_item.get("area_nombre", "General")
                                    if curr_a not in nombres_areas_cat:
                                        nombres_areas_cat.append(curr_a)
                                    idx_a = nombres_areas_cat.index(curr_a)

                                    curr_t = foto_item.get("tipo_evidencia", "General de Calidad")
                                    if curr_t not in tipos_evidencia_cat:
                                        tipos_evidencia_cat.append(curr_t)
                                    idx_t = tipos_evidencia_cat.index(curr_t)

                                    with st.container():
                                        col_f_img, col_f_meta, col_f_del = st.columns([1.3, 2.5, 0.8])
                                        with col_f_img:
                                            if f_ruta and os.path.exists(f_ruta):
                                                st.image(f_ruta, use_container_width=True)
                                                try:
                                                    with Image.open(f_ruta) as t_img:
                                                        es_v = t_img.size[1] > t_img.size[0]
                                                        tag_orient = "📱 Vertical" if es_v else "💻 Horizontal"
                                                        st.caption(f"Posición: **{tag_orient}** ({t_img.size[0]}x{t_img.size[1]})")
                                                except Exception:
                                                    pass
                                            else:
                                                st.caption("⚠️ Imagen no encontrada en disco")
                                            
                                            if f_origen == "CAPA":
                                                st.markdown('<span style="background:#FEE2E2;color:#991B1B;font-weight:700;font-size:0.75rem;padding:3px 8px;border-radius:12px;border:1px solid #F87171;display:inline-block;">⚠️ Origen: Incidencia / CAPA</span>', unsafe_allow_html=True)
                                            elif f_origen == "PWA_OFFLINE":
                                                st.markdown('<span style="background:#DCFCE7;color:#15803D;font-weight:700;font-size:0.75rem;padding:3px 8px;border-radius:12px;border:1px solid #86EFAC;display:inline-block;">📲 Origen: App Móvil PWA</span>', unsafe_allow_html=True)
                                            else:
                                                st.markdown('<span style="background:#E0F2FE;color:#075985;font-weight:700;font-size:0.75rem;padding:3px 8px;border-radius:12px;border:1px solid #7DD3FC;display:inline-block;">📸 Origen: Evidencia de Calidad</span>', unsafe_allow_html=True)

                                        with col_f_meta:
                                            st.selectbox(
                                                f"Área (Foto #{f_idx+1}):",
                                                nombres_areas_cat,
                                                index=idx_a,
                                                key=f"e_fa_{sup_id}_{f_idx}"
                                            )
                                            st.selectbox(
                                                f"Tipo Evidencia (Foto #{f_idx+1}):",
                                                tipos_evidencia_cat,
                                                index=idx_t,
                                                key=f"e_ft_{sup_id}_{f_idx}"
                                            )
                                            st.text_input(
                                                f"Descripción Técnica (Foto #{f_idx+1}):",
                                                value=foto_item.get("descripcion", ""),
                                                key=f"e_fd_{sup_id}_{f_idx}"
                                            )

                                        with col_f_del:
                                            st.markdown("<br>", unsafe_allow_html=True)
                                            if f_ruta and os.path.exists(f_ruta):
                                                if st.button("🔄 Rotar 90°", key=f"e_f_rot_{sup_id}_{f_idx}", help="Rotar esta foto 90° en sentido horario"):
                                                    if rotar_imagen_guardada(f_ruta, 90):
                                                        st.rerun()
                                            st.checkbox(
                                                "🗑️ Quitar foto",
                                                key=f"e_f_del_{sup_id}_{f_idx}",
                                                help="Marque esta casilla para eliminar esta fotografía del informe al guardar"
                                            )
                                        st.divider()
                            else:
                                st.info("ℹ️ Este informe actualmente no cuenta con fotografías registradas.")

                            st.markdown("##### ➕ Incorporar Nuevas Fotografías de Evidencia")
                            c_new_up, c_new_meta = st.columns([1.5, 1.5])
                            with c_new_up:
                                nuevas_fotos_subidas = st.file_uploader(
                                    "Cargar nuevas fotos de evidencia (JPG, PNG, WEBP):",
                                    type=["jpg", "jpeg", "png", "webp"],
                                    accept_multiple_files=True,
                                    key=f"e_new_fotos_up_{sup_id}"
                                )
                            with c_new_meta:
                                new_def_area = st.selectbox("Área para las nuevas fotos:", nombres_areas_cat, key=f"e_new_area_{sup_id}")
                                new_def_tipo = st.selectbox("Tipo de evidencia para las nuevas fotos:", tipos_evidencia_cat, key=f"e_new_tipo_{sup_id}")
                                new_def_desc = st.text_input("Descripción técnica para las nuevas fotos:", placeholder="Ej: Verificación adicional de acabado...", key=f"e_new_desc_{sup_id}")

                            c_save, c_cancel = st.columns([2, 1])
                            with c_save:
                                if st.form_submit_button("💾 GUARDAR CAMBIOS EN EL INFORME", type="primary", use_container_width=True):
                                    # Recalcular puntaje global con la nueva escala
                                    t_pts = sum(d["puntos"] for d in nuevos_detalles if d["puntos"] is not None)
                                    p_pos = sum(100 for d in nuevos_detalles if d["puntos"] is not None)
                                    nuevo_score = (t_pts / p_pos * 100.0) if p_pos > 0 else 100.0
                                    nueva_calidad = clasificar_calidad(nuevo_score)

                                    conteo_c = sum(1 for d in nuevos_detalles if d["calificacion"] == "C")
                                    conteo_r = sum(1 for d in nuevos_detalles if d["calificacion"] == "R")
                                    conteo_nc = sum(1 for d in nuevos_detalles if d["calificacion"] == "NC")
                                    conteo_na = sum(1 for d in nuevos_detalles if d["calificacion"] == "NA")

                                    p_falt = max(0, edit_prog - edit_pres)

                                    datos_actualizados = {
                                        "fecha_inspeccion": str(edit_f_insp),
                                        "hora_inicio": cab.get("hora_inicio", "08:00"),
                                        "hora_fin": cab.get("hora_fin", "09:30"),
                                        "tipo_inspeccion": edit_tipo,
                                        "turno": edit_turno,
                                        "edificio_id": cab.get("edificio_id"),
                                        "edificio_nombre": cab.get("edificio_nombre"),
                                        "edificio_direccion": cab.get("edificio_direccion"),
                                        "administrador_nombre": edit_cli_nom,
                                        "supervisor_id": cab.get("supervisor_id"),
                                        "supervisor_nombre": cab.get("supervisor_nombre"),
                                        "supervisor_dni": cab.get("supervisor_dni"),
                                        "lider_cuadrilla": edit_lider,
                                        "personal_programado": int(edit_prog),
                                        "personal_presente": int(edit_pres),
                                        "personal_faltante": int(p_falt),
                                        "score_global": round(nuevo_score, 2),
                                        "nivel_calidad": nueva_calidad["nivel"],
                                        "estado_aprobacion": nueva_calidad["estado"],
                                        "total_items_evaluados": len(nuevos_detalles),
                                        "total_conformes": conteo_c,
                                        "total_regulares": conteo_r,
                                        "total_no_conformes": conteo_nc,
                                        "total_no_aplica": conteo_na,
                                        "epp_conforme": cab.get("epp_conforme", 1),
                                        "maquinaria_conforme": cab.get("maquinaria_conforme", 1),
                                        "insumos_conforme": cab.get("insumos_conforme", 1),
                                        "incluir_firmas": 1 if edit_firmas_chk else 0,
                                        "observaciones_generales": edit_obs_gral,
                                        "plan_accion_resumen": cab.get("plan_accion_resumen", ""),
                                        "firmante_cliente_nombre": edit_cli_nom,
                                        "firmante_cliente_cargo": edit_cli_car
                                    }

                                    # Procesar fotos actualizadas
                                    fotos_actualizadas = []
                                    # 1. Fotos existentes no eliminadas
                                    for f_idx, foto_item in enumerate(fotos_existentes):
                                        del_val = st.session_state.get(f"e_f_del_{sup_id}_{f_idx}", False)
                                        if not del_val:
                                            a_val = st.session_state.get(f"e_fa_{sup_id}_{f_idx}", foto_item.get("area_nombre", "General"))
                                            t_val = st.session_state.get(f"e_ft_{sup_id}_{f_idx}", foto_item.get("tipo_evidencia", "General de Calidad"))
                                            d_val = st.session_state.get(f"e_fd_{sup_id}_{f_idx}", foto_item.get("descripcion", ""))
                                            fotos_actualizadas.append({
                                                "supervision_id": sup_id,
                                                "area_nombre": a_val,
                                                "tipo_evidencia": t_val,
                                                "archivo_nombre": foto_item.get("archivo_nombre", ""),
                                                "archivo_ruta": foto_item.get("archivo_ruta", ""),
                                                "descripcion": d_val,
                                                "origen": foto_item.get("origen", "REGISTRO_FOTOGRAFICO")
                                            })

                                    # 2. Nuevas fotos subidas
                                    if nuevas_fotos_subidas:
                                        for nfile in nuevas_fotos_subidas:
                                            ncontent = nfile.getvalue()
                                            if ncontent:
                                                ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                                                rand_suffix = uuid.uuid4().hex[:6]
                                                nombre_arch = f"evidencia_edit_{ts_str}_{rand_suffix}.jpg"
                                                ruta_arch = str(UPLOADS_DIR / nombre_arch)
                                                guardar_y_optimizar_imagen(ncontent, ruta_arch)
                                                fotos_actualizadas.append({
                                                    "supervision_id": sup_id,
                                                    "area_nombre": new_def_area,
                                                    "tipo_evidencia": new_def_tipo,
                                                    "archivo_nombre": nombre_arch,
                                                    "archivo_ruta": ruta_arch,
                                                    "descripcion": new_def_desc,
                                                    "origen": "REGISTRO_FOTOGRAFICO"
                                                })

                                    actualizar_supervision_completa(
                                        supervision_id=sup_id,
                                        datos_gral=datos_actualizados,
                                        detalles_evaluacion=nuevos_detalles,
                                        incidencias=incs,
                                        fotos_guardadas=fotos_actualizadas
                                    )

                                    st.success(f"🎉 Informe {cab['codigo_informe']} actualizado con éxito. Nuevo Score: {nuevo_score:.1f}% ({nueva_calidad['nivel']})")
                                    st.session_state[f"modo_edicion_{sup_id}"] = False
                                    st.rerun()

                        if st.button("❌ Cancelar Edición", key=f"btn_canc_edit_{sup_id}"):
                            st.session_state[f"modo_edicion_{sup_id}"] = False
                            st.rerun()

                # Ver detalles expandibles (Desglose por área, Incidencias, Fotos)
                with st.expander(f"🔎 Ver detalles completos de áreas, incidencias y fotos de {sup['codigo_informe']}"):
                    det_info = obtener_supervision_por_id(sup_id)
                    if det_info:
                        d_c1, d_c2 = st.columns(2)
                        with d_c1:
                            st.markdown("**Desglose de Calificaciones:**")
                            st.write(f"- Ítems Conformes (C): {det_info['cabecera'].get('total_conformes', 0)}")
                            st.write(f"- Ítems Regulares (R): {det_info['cabecera'].get('total_regulares', 0)}")
                            st.write(f"- Ítems No Conformes (NC): {det_info['cabecera'].get('total_no_conformes', 0)}")
                            st.write(f"- No Aplica (NA): {det_info['cabecera'].get('total_no_aplica', 0)}")
                            st.write(f"**Observaciones:** {det_info['cabecera'].get('observaciones_generales', 'Sin observaciones.')}")

                            # Resumen de desempeño por área
                            if det_info.get("detalles"):
                                st.markdown("**Desempeño por Área:**")
                                a_group = {}
                                for it in det_info["detalles"]:
                                    an = it["nombre_area"]
                                    a_group.setdefault(an, []).append(it)
                                res_a = []
                                for an, its in a_group.items():
                                    pts_a = sum(x["puntos"] for x in its if x["puntos"] is not None)
                                    pos_a = sum(100 for x in its if x["puntos"] is not None)
                                    sc_a = (pts_a / pos_a * 100.0) if pos_a > 0 else 100.0
                                    cal_a = clasificar_calidad(sc_a)
                                    res_a.append({"Área": an, "Score": f"{sc_a:.1f}%", "Nivel": cal_a["nivel"]})
                                st.dataframe(pd.DataFrame(res_a), hide_index=True, use_container_width=True)
                        
                        with d_c2:
                            st.markdown("**Incidencias / Plan de Acción:**")
                            if det_info["incidencias"]:
                                for inc in det_info["incidencias"]:
                                    st.error(f"⚠️ **{inc['area_nombre']} ({inc['severidad']}):** {inc['descripcion_hallazgo']} → *Acción:* {inc['accion_correctiva']} (Plazo: {inc['plazo_subsanacion']})")
                            else:
                                st.success("Sin incidencias críticas registradas.")

                        if det_info["fotos"]:
                            st.markdown("**Evidencias Fotográficas:**")
                            f_cols = st.columns(min(3, len(det_info["fotos"])))
                            for f_idx, foto in enumerate(det_info["fotos"]):
                                if os.path.exists(foto["archivo_ruta"]):
                                    with f_cols[f_idx % len(f_cols)]:
                                        tag_orig = "[INCIDENCIA/CAPA]" if foto.get("origen") == "CAPA" else "[CALIDAD]"
                                        st.image(foto["archivo_ruta"], caption=f"{tag_orig} {foto.get('area_nombre', '')} - {foto['tipo_evidencia']}: {foto['descripcion']}")

                st.divider()
        st.markdown("<br>", unsafe_allow_html=True)
