"""
Módulo Integral de Configuración, Maestros y Parámetros del Sistema:
Permite agregar, editar y eliminar todas las opciones desplegables de Nueva Supervisión:
- Edificios y Sedes
- Supervisores e Inspectores
- Tipos de Inspección
- Turnos de Trabajo
- Áreas y Criterios Técnicos del Checklist
"""
import os
import io
import zipfile
from datetime import datetime
import streamlit as st
import pandas as pd
from config import DATA_DIR, UPLOADS_DIR
from database import (
    DB_PATH,
    obtener_parametro, guardar_parametro,
    obtener_lista_edificios, agregar_edificio, actualizar_edificio, eliminar_edificio_db,
    obtener_lista_supervisores, agregar_supervisor, actualizar_supervisor, eliminar_supervisor_db,
    obtener_tipos_inspeccion, agregar_tipo_inspeccion, actualizar_tipo_inspeccion, eliminar_tipo_inspeccion,
    obtener_turnos_trabajo, agregar_turno_trabajo, actualizar_turno_trabajo, eliminar_turno_trabajo,
    obtener_areas_raw, obtener_criterios_raw, agregar_area_catalogo, actualizar_area_catalogo, eliminar_area_catalogo,
    agregar_criterio_catalogo, actualizar_criterio_catalogo, eliminar_criterio_catalogo,
    obtener_lista_usuarios, agregar_usuario, actualizar_usuario, cambiar_password_usuario, eliminar_usuario_db
)


def render_modulo_configuracion():
    """Renderiza el centro de administración y edición de opciones desplegables y maestros."""
    st.markdown("""
        <div class="header-hero">
            <h1>⚙️ Centro de Configuración & Opciones Maestras</h1>
            <p>Administre, agregue y edite las opciones desplegables de Nueva Supervisión, datos de la Empresa, Edificios, Supervisores y Criterios.</p>
            <div class="header-badges">
                <span class="badge-tag">🏢 Empresa & Membrete</span>
                <span class="badge-tag">🏢 Edificios</span>
                <span class="badge-tag">👷 Supervisores</span>
                <span class="badge-tag">📋 Tipos de Inspección</span>
                <span class="badge-tag">⏰ Turnos</span>
                <span class="badge-tag">🧹 Zonas & Criterios</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    tab_emp, tab_edif, tab_sup, tab_tipos, tab_turnos, tab_areas, tab_users, tab_backup, tab_smtp = st.tabs([
        "🏢 Empresa & Membrete",
        "🏢 Edificios & Sedes",
        "👷 Supervisores",
        "📋 Tipos de Inspección",
        "⏰ Turnos de Trabajo",
        "🧹 Zonas & Criterios Checklist",
        "👥 Usuarios & Accesos",
        "💾 Copia de Seguridad (Backup)",
        "📧 Servidor de Correo (SMTP)"
    ])

    # -------------------------------------------------------------
    # TAB 0: DATOS DE LA EMPRESA Y MEMBRETE (EDITABLE)
    # -------------------------------------------------------------
    with tab_emp:
        st.markdown("### 🏢 Datos de la Empresa y Membrete Oficial del Reporte")
        st.caption("Esta información se estampa automáticamente en el encabezado y pie de página de los reportes PDF generados.")

        emp_actual = obtener_parametro("empresa_nombre", "SERVICIOS INTEGRALES DE LIMPIEZA Y FACILITY MANAGEMENT S.A.C.")
        sub_actual = obtener_parametro("empresa_subtitulo", "Control de Calidad, Estándares de Higiene y Cumplimiento de Servicio")
        cod_actual = obtener_parametro("formato_codigo", "FOR-SGI-LMP-04")
        ver_actual = obtener_parametro("formato_version", "2.4 - 2026")

        with st.form("form_datos_empresa"):
            c_emp1, c_emp2 = st.columns(2)
            with c_emp1:
                nuevo_emp_nom = st.text_input("Razón Social o Nombre de la Empresa *:", value=emp_actual, key="cfg_emp_nom")
                nuevo_emp_sub = st.text_input("Subtítulo Institucional:", value=sub_actual, key="cfg_emp_sub")
            with c_emp2:
                nuevo_form_cod = st.text_input("Código Oficial del Formato:", value=cod_actual, key="cfg_form_cod")
                nuevo_form_ver = st.text_input("Versión de Revisión:", value=ver_actual, key="cfg_form_ver")

            if st.form_submit_button("💾 Guardar Datos de Empresa", type="primary"):
                if nuevo_emp_nom.strip():
                    guardar_parametro("empresa_nombre", nuevo_emp_nom.strip())
                    guardar_parametro("empresa_subtitulo", nuevo_emp_sub.strip())
                    guardar_parametro("formato_codigo", nuevo_form_cod.strip())
                    guardar_parametro("formato_version", nuevo_form_ver.strip())
                    st.success("✅ Datos de la empresa y membrete actualizados exitosamente.")
                    st.rerun()
                else:
                    st.error("Ingrese el nombre de la empresa.")

    # -------------------------------------------------------------
    # TAB 1: GESTIÓN DE EDIFICIOS (AGREGAR / EDITAR / ELIMINAR)
    # -------------------------------------------------------------
    with tab_edif:
        st.markdown("### 🏢 Catálogo de Edificios y Sedes Atendidas")
        edificios = obtener_lista_edificios(solo_activos=False)

        if edificios:
            df_edif = pd.DataFrame(edificios)[[
                "id", "nombre", "direccion", "distrito_ciudad",
                "administrador_contacto", "telefono_email", "num_pisos", "dotacion_personal_asignada", "activo"
            ]]
            df_edif.columns = ["ID", "Edificio / Sede", "Dirección", "Distrito", "Administrador", "Contacto", "Pisos", "Dotación", "Activo"]
            st.dataframe(df_edif, use_container_width=True, hide_index=True)
        else:
            st.info("No hay edificios registrados.")

        col_add_e, col_edit_e = st.columns(2)

        # ➕ AGREGAR EDIFICIO
        with col_add_e:
            with st.expander("➕ Agregar Nuevo Edificio", expanded=False):
                with st.form("form_add_edificio", clear_on_submit=True):
                    nom_e = st.text_input("Nombre del Edificio / Sede *:", placeholder="Ej: Torre Corporativa Begonias", key="add_e_nom")
                    dir_e = st.text_input("Dirección Completa *:", placeholder="Ej: Calle Las Begonias 441", key="add_e_dir")
                    dist_e = st.text_input("Distrito / Ciudad:", value="San Isidro, Lima", key="add_e_dist")
                    admin_e = st.text_input("Administrador de Sede:", placeholder="Ej: Ing. Jorge Alarcón", key="add_e_admin")
                    tel_e = st.text_input("Teléfono / Correo:", placeholder="Ej: 998765432 / admin@begonias.pe", key="add_e_tel")
                    
                    c_p, c_s, c_d = st.columns(3)
                    with c_p:
                        pisos_e = st.number_input("Pisos:", min_value=1, max_value=100, value=12, key="add_e_p")
                    with c_s:
                        sotanos_e = st.number_input("Sótanos:", min_value=0, max_value=10, value=2, key="add_e_s")
                    with c_d:
                        dot_e = st.number_input("Dotación:", min_value=1, max_value=100, value=4, key="add_e_dot")
                    
                    obs_e = st.text_area("Observaciones Contractuales:", key="add_e_obs")

                    if st.form_submit_button("💾 Guardar Nuevo Edificio", type="primary", use_container_width=True):
                        if nom_e.strip() and dir_e.strip():
                            agregar_edificio(nom_e, dir_e, dist_e, admin_e, tel_e, int(pisos_e), int(sotanos_e), int(dot_e), obs_e)
                            st.success(f"Edificio '{nom_e}' registrado exitosamente.")
                            st.rerun()
                        else:
                            st.error("Ingrese el nombre y la dirección.")

        # ✏️ EDITAR EDIFICIO
        with col_edit_e:
            with st.expander("✏️ Editar o Modificar Edificio Existente", expanded=False):
                if edificios:
                    dict_edif = {f"{e['nombre']} (ID: {e['id']})": e for e in edificios}
                    edif_sel_str = st.selectbox("Seleccionar Edificio a Modificar:", list(dict_edif.keys()), key="sel_edit_edif")
                    edif_sel = dict_edif[edif_sel_str]

                    with st.form(f"form_edit_edif_{edif_sel['id']}"):
                        edit_nom = st.text_input("Nombre del Edificio:", value=edif_sel["nombre"], key="ed_nom")
                        edit_dir = st.text_input("Dirección:", value=edif_sel["direccion"], key="ed_dir")
                        edit_dist = st.text_input("Distrito / Ciudad:", value=edif_sel.get("distrito_ciudad", "Lima"), key="ed_dist")
                        edit_admin = st.text_input("Administrador:", value=edif_sel.get("administrador_contacto", ""), key="ed_admin")
                        edit_tel = st.text_input("Contacto / Teléfono:", value=edif_sel.get("telefono_email", ""), key="ed_tel")

                        c_ep, c_es, c_ed = st.columns(3)
                        with c_ep:
                            edit_pisos = st.number_input("Pisos:", min_value=1, max_value=100, value=int(edif_sel.get("num_pisos", 10)), key="ed_pisos")
                        with c_es:
                            edit_sot = st.number_input("Sótanos:", min_value=0, max_value=10, value=int(edif_sel.get("num_sotanos", 2)), key="ed_sot")
                        with c_ed:
                            edit_dot = st.number_input("Dotación:", min_value=1, max_value=100, value=int(edif_sel.get("dotacion_personal_asignada", 4)), key="ed_dot")

                        edit_obs = st.text_area("Observaciones:", value=edif_sel.get("observaciones", ""), key="ed_obs")
                        edit_activo = st.checkbox("Edificio Activo (visible en Nueva Supervisión)", value=bool(edif_sel.get("activo", 1)), key="ed_act")

                        c_btn_save, c_btn_del = st.columns([2, 1])
                        with c_btn_save:
                            if st.form_submit_button("💾 Guardar Cambios", type="primary", use_container_width=True):
                                actualizar_edificio(
                                    edif_sel["id"], edit_nom, edit_dir, edit_dist, edit_admin, edit_tel,
                                    int(edit_pisos), int(edit_sot), int(edit_dot), edit_obs, 1 if edit_activo else 0
                                )
                                st.success("Edificio actualizado correctamente.")
                                st.rerun()

                    # Opción de eliminar fuera del form para evitar submit accidental
                    if st.button(f"🗑️ Eliminar Edificio ({edif_sel['nombre']})", key=f"btn_del_e_{edif_sel['id']}"):
                        eliminar_edificio_db(edif_sel["id"])
                        st.success("Edificio eliminado.")
                        st.rerun()
                else:
                    st.info("No hay edificios para editar.")

    # -------------------------------------------------------------
    # TAB 2: GESTIÓN DE SUPERVISORES (AGREGAR / EDITAR / ELIMINAR)
    # -------------------------------------------------------------
    with tab_sup:
        st.markdown("### 👷 Catálogo de Supervisores e Inspectores")
        supervisores = obtener_lista_supervisores(solo_activos=False)

        if supervisores:
            df_sup = pd.DataFrame(supervisores)[["id", "nombre_completo", "dni_ce", "cargo", "telefono", "activo"]]
            df_sup.columns = ["ID", "Nombre Completo", "DNI / Carnet", "Cargo", "Teléfono", "Activo"]
            st.dataframe(df_sup, use_container_width=True, hide_index=True)
        else:
            st.info("No hay supervisores registrados.")

        col_add_s, col_edit_s = st.columns(2)

        # ➕ AGREGAR SUPERVISOR
        with col_add_s:
            with st.expander("➕ Agregar Nuevo Supervisor", expanded=False):
                with st.form("form_add_sup", clear_on_submit=True):
                    nom_s = st.text_input("Nombre Completo *:", placeholder="Ej: Pedro Valdivia Huamán", key="add_s_nom")
                    dni_s = st.text_input("DNI o Carnet *:", placeholder="Ej: 45892147", key="add_s_dni")
                    cargo_s = st.text_input("Cargo:", value="Supervisor de Operaciones y Calidad", key="add_s_cargo")
                    tel_s = st.text_input("Teléfono Móvil:", placeholder="Ej: +51 987 112 233", key="add_s_tel")

                    if st.form_submit_button("💾 Guardar Supervisor", type="primary", use_container_width=True):
                        if nom_s.strip() and dni_s.strip():
                            agregar_supervisor(nom_s, dni_s, cargo_s, tel_s)
                            st.success(f"Supervisor '{nom_s}' registrado exitosamente.")
                            st.rerun()
                        else:
                            st.error("Ingrese el nombre y DNI.")

        # ✏️ EDITAR SUPERVISOR
        with col_edit_s:
            with st.expander("✏️ Editar Supervisor Existente", expanded=False):
                if supervisores:
                    dict_sup = {f"{s['nombre_completo']} (DNI: {s['dni_ce']})": s for s in supervisores}
                    sup_sel_str = st.selectbox("Seleccionar Supervisor a Modificar:", list(dict_sup.keys()), key="sel_edit_sup")
                    sup_sel = dict_sup[sup_sel_str]

                    with st.form(f"form_edit_sup_{sup_sel['id']}"):
                        edit_s_nom = st.text_input("Nombre Completo:", value=sup_sel["nombre_completo"], key="es_nom")
                        edit_s_dni = st.text_input("DNI / Carnet:", value=sup_sel["dni_ce"], key="es_dni")
                        edit_s_cargo = st.text_input("Cargo:", value=sup_sel.get("cargo", "Supervisor"), key="es_cargo")
                        edit_s_tel = st.text_input("Teléfono:", value=sup_sel.get("telefono", ""), key="es_tel")
                        edit_s_act = st.checkbox("Supervisor Activo (visible en selector)", value=bool(sup_sel.get("activo", 1)), key="es_act")

                        if st.form_submit_button("💾 Guardar Cambios", type="primary", use_container_width=True):
                            actualizar_supervisor(sup_sel["id"], edit_s_nom, edit_s_dni, edit_s_cargo, edit_s_tel, 1 if edit_s_act else 0)
                            st.success("Supervisor actualizado correctamente.")
                            st.rerun()

                    if st.button(f"🗑️ Eliminar Supervisor ({sup_sel['nombre_completo']})", key=f"btn_del_s_{sup_sel['id']}"):
                        eliminar_supervisor_db(sup_sel["id"])
                        st.success("Supervisor eliminado.")
                        st.rerun()
                else:
                    st.info("No hay supervisores para editar.")

    # -------------------------------------------------------------
    # TAB 3: GESTIÓN DE TIPOS DE INSPECCIÓN (DESPLEGABLE)
    # -------------------------------------------------------------
    with tab_tipos:
        st.markdown("### 📋 Opciones Desplegables: Tipos de Inspección")
        st.caption("Estas opciones aparecen en el menú desplegable **'Tipo de Inspección'** en el formulario de Nueva Supervisión.")

        tipos_raw = obtener_tipos_inspeccion(solo_activos=False)

        if isinstance(tipos_raw, list) and tipos_raw and isinstance(tipos_raw[0], dict):
            df_tipos = pd.DataFrame(tipos_raw)[["id", "nombre", "descripcion", "activo"]]
            st.dataframe(df_tipos, use_container_width=True, hide_index=True)
        
        col_t_add, col_t_edit = st.columns(2)

        # ➕ AGREGAR TIPO DE INSPECCIÓN
        with col_t_add:
            with st.expander("➕ Agregar Nuevo Tipo de Inspección", expanded=False):
                with st.form("form_add_tipo", clear_on_submit=True):
                    nuevo_t_nom = st.text_input("Nombre del Tipo de Inspección *:", placeholder="Ej: Auditoría Ambiental y Manejo de Residuos", key="add_t_nom")
                    nuevo_t_desc = st.text_input("Descripción / Propósito:", placeholder="Ej: Inspección enfocada en cuartos de basura y segregación.", key="add_t_desc")

                    if st.form_submit_button("💾 Agregar Tipo", type="primary", use_container_width=True):
                        if nuevo_t_nom.strip():
                            agregar_tipo_inspeccion(nuevo_t_nom, nuevo_t_desc)
                            st.success(f"Tipo '{nuevo_t_nom}' agregado exitosamente.")
                            st.rerun()
                        else:
                            st.error("Ingrese el nombre del tipo de inspección.")

        # ✏️ EDITAR TIPO DE INSPECCIÓN
        with col_t_edit:
            with st.expander("✏️ Editar o Eliminar Tipo de Inspección", expanded=False):
                if isinstance(tipos_raw, list) and tipos_raw and isinstance(tipos_raw[0], dict):
                    dict_t = {t["nombre"]: t for t in tipos_raw}
                    t_sel_nom = st.selectbox("Seleccionar Tipo a Modificar:", list(dict_t.keys()), key="sel_edit_t")
                    t_sel = dict_t[t_sel_nom]

                    with st.form(f"form_edit_tipo_{t_sel['id']}"):
                        ed_t_nom = st.text_input("Nombre:", value=t_sel["nombre"], key="et_nom")
                        ed_t_desc = st.text_input("Descripción:", value=t_sel.get("descripcion", ""), key="et_desc")
                        ed_t_act = st.checkbox("Activo en lista desplegable", value=bool(t_sel.get("activo", 1)), key="et_act")

                        if st.form_submit_button("💾 Guardar Cambios", type="primary", use_container_width=True):
                            actualizar_tipo_inspeccion(t_sel["id"], ed_t_nom, ed_t_desc, 1 if ed_t_act else 0)
                            st.success("Tipo de inspección actualizado.")
                            st.rerun()

                    if st.button(f"🗑️ Eliminar Tipo ({t_sel['nombre']})", key=f"btn_del_t_{t_sel['id']}"):
                        eliminar_tipo_inspeccion(t_sel["id"])
                        st.success("Tipo de inspección eliminado.")
                        st.rerun()

    # -------------------------------------------------------------
    # TAB 4: GESTIÓN DE TURNOS DE TRABAJO (DESPLEGABLE)
    # -------------------------------------------------------------
    with tab_turnos:
        st.markdown("### ⏰ Opciones Desplegables: Turnos Operativos")
        st.caption("Estas opciones aparecen en el menú desplegable **'Turno de Trabajo'** en Nueva Supervisión.")

        turnos_raw = obtener_turnos_trabajo(solo_activos=False)

        if isinstance(turnos_raw, list) and turnos_raw and isinstance(turnos_raw[0], dict):
            df_turnos = pd.DataFrame(turnos_raw)[["id", "nombre", "horario_referencial", "activo"]]
            st.dataframe(df_turnos, use_container_width=True, hide_index=True)

        col_tu_add, col_tu_edit = st.columns(2)

        # ➕ AGREGAR TURNO
        with col_tu_add:
            with st.expander("➕ Agregar Nuevo Turno", expanded=False):
                with st.form("form_add_turno", clear_on_submit=True):
                    nuevo_tu_nom = st.text_input("Nombre del Turno *:", placeholder="Ej: Turno Especial Fin de Semana (08:00 - 17:00)", key="add_tu_nom")
                    nuevo_tu_hor = st.text_input("Horario Referencial:", placeholder="Ej: Sábados y Domingos 08:00 a 17:00", key="add_tu_hor")

                    if st.form_submit_button("💾 Agregar Turno", type="primary", use_container_width=True):
                        if nuevo_tu_nom.strip():
                            agregar_turno_trabajo(nuevo_tu_nom, nuevo_tu_hor)
                            st.success(f"Turno '{nuevo_tu_nom}' registrado exitosamente.")
                            st.rerun()
                        else:
                            st.error("Ingrese el nombre del turno.")

        # ✏️ EDITAR TURNO
        with col_tu_edit:
            with st.expander("✏️ Editar o Eliminar Turno", expanded=False):
                if isinstance(turnos_raw, list) and turnos_raw and isinstance(turnos_raw[0], dict):
                    dict_tu = {tu["nombre"]: tu for tu in turnos_raw}
                    tu_sel_nom = st.selectbox("Seleccionar Turno a Modificar:", list(dict_tu.keys()), key="sel_edit_tu")
                    tu_sel = dict_tu[tu_sel_nom]

                    with st.form(f"form_edit_turno_{tu_sel['id']}"):
                        ed_tu_nom = st.text_input("Nombre del Turno:", value=tu_sel["nombre"], key="etu_nom")
                        ed_tu_hor = st.text_input("Horario:", value=tu_sel.get("horario_referencial", ""), key="etu_hor")
                        ed_tu_act = st.checkbox("Activo en lista desplegable", value=bool(tu_sel.get("activo", 1)), key="etu_act")

                        if st.form_submit_button("💾 Guardar Cambios", type="primary", use_container_width=True):
                            actualizar_turno_trabajo(tu_sel["id"], ed_tu_nom, ed_tu_hor, 1 if ed_tu_act else 0)
                            st.success("Turno actualizado correctamente.")
                            st.rerun()

                    if st.button(f"🗑️ Eliminar Turno ({tu_sel['nombre']})", key=f"btn_del_tu_{tu_sel['id']}"):
                        eliminar_turno_trabajo(tu_sel["id"])
                        st.success("Turno eliminado.")
                        st.rerun()

    # -------------------------------------------------------------
    # TAB 5: GESTIÓN DE ZONAS Y CRITERIOS DEL CHECKLIST
    # -------------------------------------------------------------
    with tab_areas:
        st.markdown("### 🧹 Catálogo de Zonas y Criterios Técnicos del Checklist")
        st.caption("Personalice las áreas a inspeccionar (Lobby, Ascensores, Baños, etc.) y los criterios específicos que se evalúan en cada una.")

        areas_list = obtener_areas_raw()

        # 1. GESTIÓN DE ÁREAS / ZONAS
        st.markdown("#### 🏢 1. Zonas del Inmueble (Áreas Principales)")
        if areas_list:
            df_a = pd.DataFrame(areas_list)[["id", "id_area", "nombre", "icono", "orden", "activo"]]
            st.dataframe(df_a, use_container_width=True, hide_index=True)

        col_a_add, col_a_edit = st.columns(2)
        with col_a_add:
            with st.expander("➕ Agregar Nueva Zona / Área", expanded=False):
                with st.form("form_add_area", clear_on_submit=True):
                    id_a_new = st.text_input("Identificador Único (sin espacios) *:", placeholder="Ej: cafeteria_comedor", key="add_id_a")
                    nom_a_new = st.text_input("Nombre de la Zona *:", placeholder="Ej: 11. Comedor, Cocina y Cafetería", key="add_nom_a")
                    ico_a_new = st.text_input("Icono / Emoji:", value="🍽️", key="add_ico_a")
                    ord_a_new = st.number_input("Orden:", value=len(areas_list) + 1, key="add_ord_a")

                    if st.form_submit_button("💾 Guardar Zona", type="primary", use_container_width=True):
                        if id_a_new.strip() and nom_a_new.strip():
                            agregar_area_catalogo(id_a_new.strip().lower(), nom_a_new.strip(), ico_a_new, int(ord_a_new))
                            st.success(f"Zona '{nom_a_new}' agregada.")
                            st.rerun()
                        else:
                            st.error("Complete el ID y el nombre.")

        with col_a_edit:
            with st.expander("✏️ Editar o Eliminar Zona", expanded=False):
                if areas_list:
                    dict_ar = {f"{a['nombre']} ({a['id_area']})": a for a in areas_list}
                    ar_sel_str = st.selectbox("Seleccionar Zona:", list(dict_ar.keys()), key="sel_edit_ar")
                    ar_sel = dict_ar[ar_sel_str]

                    with st.form(f"form_edit_ar_{ar_sel['id']}"):
                        ed_ar_nom = st.text_input("Nombre:", value=ar_sel["nombre"], key="ear_nom")
                        ed_ar_ico = st.text_input("Icono:", value=ar_sel.get("icono", "🏢"), key="ear_ico")
                        ed_ar_ord = st.number_input("Orden:", value=int(ar_sel.get("orden", 0)), key="ear_ord")
                        ed_ar_act = st.checkbox("Zona Activa", value=bool(ar_sel.get("activo", 1)), key="ear_act")

                        if st.form_submit_button("💾 Guardar Cambios de Zona", type="primary", use_container_width=True):
                            actualizar_area_catalogo(ar_sel["id"], ed_ar_nom, ed_ar_ico, int(ed_ar_ord), 1 if ed_ar_act else 0)
                            st.success("Zona actualizada.")
                            st.rerun()

                    if st.button(f"🗑️ Eliminar Zona ({ar_sel['nombre']})", key=f"btn_del_ar_{ar_sel['id']}"):
                        eliminar_area_catalogo(ar_sel["id"])
                        st.success("Zona y sus criterios eliminados.")
                        st.rerun()

        st.markdown("---")

        # 2. GESTIÓN DE CRITERIOS TÉCNICOS POR ÁREA
        st.markdown("#### 🔍 2. Criterios Técnicos Evaluables dentro de cada Zona")
        
        if areas_list:
            dict_ar_c = {a["nombre"]: a["id_area"] for a in areas_list}
            zona_filtro = st.selectbox("Seleccionar Zona para ver/gestionar sus criterios:", list(dict_ar_c.keys()), key="sel_z_crit")
            id_zona_sel = dict_ar_c[zona_filtro]

            criterios_zona = obtener_criterios_raw(id_zona_sel)
            if criterios_zona:
                df_c = pd.DataFrame(criterios_zona)[["id", "id_criterio", "item", "descripcion", "orden", "activo"]]
                st.dataframe(df_c, use_container_width=True, hide_index=True)
            else:
                st.info("Esta zona aún no tiene criterios técnicos asignados.")

            col_c_add, col_c_edit = st.columns(2)
            
            with col_c_add:
                with st.expander(f"➕ Agregar Criterio a '{zona_filtro}'", expanded=False):
                    with st.form("form_add_crit", clear_on_submit=True):
                        id_c_new = st.text_input("ID Criterio (sin espacios):", placeholder=f"{id_zona_sel}_nuevo_item", key="add_id_c")
                        item_c_new = st.text_input("Elemento / Ítem a Evaluar *:", placeholder="Ej: Mesas y Sillas Desinfectadas", key="add_item_c")
                        desc_c_new = st.text_area("Descripción Técnica del Estándar:", placeholder="Ej: Superficies libres de grasa, migajas y desinfectadas con amonio.", key="add_desc_c")
                        ord_c_new = st.number_input("Orden:", value=len(criterios_zona) + 1, key="add_ord_c")

                        if st.form_submit_button("💾 Guardar Criterio", type="primary", use_container_width=True):
                            if item_c_new.strip():
                                final_id_c = id_c_new.strip() if id_c_new.strip() else f"{id_zona_sel}_{len(criterios_zona)+1}"
                                agregar_criterio_catalogo(final_id_c, id_zona_sel, item_c_new.strip(), desc_c_new, int(ord_c_new))
                                st.success(f"Criterio '{item_c_new}' agregado a la zona.")
                                st.rerun()
                            else:
                                st.error("Ingrese el nombre del elemento a evaluar.")

            with col_c_edit:
                with st.expander("✏️ Editar o Eliminar Criterio", expanded=False):
                    if criterios_zona:
                        dict_cr = {c["item"]: c for c in criterios_zona}
                        cr_sel_nom = st.selectbox("Seleccionar Criterio a Modificar:", list(dict_cr.keys()), key="sel_cr_mod")
                        cr_sel = dict_cr[cr_sel_nom]

                        with st.form(f"form_edit_cr_{cr_sel['id']}"):
                            ed_cr_item = st.text_input("Elemento:", value=cr_sel["item"], key="ecr_item")
                            ed_cr_desc = st.text_area("Descripción Técnica:", value=cr_sel.get("descripcion", ""), key="ecr_desc")
                            ed_cr_ord = st.number_input("Orden:", value=int(cr_sel.get("orden", 0)), key="ecr_ord")
                            ed_cr_act = st.checkbox("Criterio Activo", value=bool(cr_sel.get("activo", 1)), key="ecr_act")

                            if st.form_submit_button("💾 Guardar Cambios de Criterio", type="primary", use_container_width=True):
                                actualizar_criterio_catalogo(cr_sel["id"], ed_cr_item, ed_cr_desc, int(ed_cr_ord), 1 if ed_cr_act else 0)
                                st.success("Criterio actualizado.")
                                st.rerun()

                        if st.button(f"🗑️ Eliminar Criterio ({cr_sel['item']})", key=f"btn_del_cr_{cr_sel['id']}"):
                            eliminar_criterio_catalogo(cr_sel["id"])
                            st.success("Criterio eliminado.")
                            st.rerun()

    # -------------------------------------------------------------
    # TAB 6: COPIA DE SEGURIDAD (BACKUP) Y RESTAURACIÓN EN 1 CLIC
    # -------------------------------------------------------------
    with tab_backup:
        st.markdown("### 💾 Copia de Seguridad Completa (Backup) & Restauración")
        st.caption("Genere un respaldo comprimido (.zip) con la base de datos SQLite y todas las fotografías de evidencia.")

        import zipfile
        import io
        from config import DATA_DIR, UPLOADS_DIR
        from database import DB_PATH

        c_bk1, c_bk2 = st.columns(2)

        with c_bk1:
            st.markdown("#### 📦 Descargar Respaldo del Sistema")
            st.markdown("""
            El paquete de respaldo incluye:
            - ✅ Base de datos SQLite (`supervision_limpieza.db`)
            - ✅ Fotografías y evidencias fotográficas (`static/uploads/`)
            - ✅ Catálogo de maestros, parámetros e historial completo
            """)

            # Generar ZIP en memoria
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                if os.path.exists(DB_PATH):
                    zf.write(DB_PATH, arcname="supervision_limpieza.db")
                if os.path.exists(UPLOADS_DIR):
                    for raiz, _, archivos in os.walk(UPLOADS_DIR):
                        for arc in archivos:
                            ruta_completa = os.path.join(raiz, arc)
                            arc_rel = os.path.relpath(ruta_completa, UPLOADS_DIR)
                            zf.write(ruta_completa, arcname=os.path.join("uploads", arc_rel))

            zip_buf.seek(0)
            st.download_button(
                label="📥 DESCARGAR COPIA DE SEGURIDAD (.ZIP)",
                data=zip_buf,
                file_name=f"Backup_CleanFacilityPro_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                mime="application/zip",
                type="primary",
                use_container_width=True
            )

        with c_bk2:
            st.markdown("#### 📥 Restaurar Copia de Seguridad")
            st.warning("⚠️ **Atención:** La restauración reemplazará la base de datos actual con la del respaldo.")
            archivo_zip_restaurar = st.file_uploader("Seleccionar archivo de respaldo (.zip):", type=["zip"], key="up_backup_restore")

            if archivo_zip_restaurar:
                if st.button("⚠️ Confirmar y Restaurar Respaldo", type="secondary", use_container_width=True):
                    try:
                        with zipfile.ZipFile(archivo_zip_restaurar, "r") as zf_in:
                            for miembro in zf_in.namelist():
                                if miembro == "supervision_limpieza.db":
                                    with open(DB_PATH, "wb") as f_db:
                                        f_db.write(zf_in.read(miembro))
                                elif miembro.startswith("uploads/"):
                                    nom_rel = miembro.replace("uploads/", "")
                                    if nom_rel:
                                        ruta_des = UPLOADS_DIR / nom_rel
                                        os.makedirs(ruta_des.parent, exist_ok=True)
                                        with open(ruta_des, "wb") as f_img:
                                            f_img.write(zf_in.read(miembro))
                        st.success("🎉 ¡Copia de seguridad restaurada exitosamente! Recargando...")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al restaurar respaldo: {e}")

    # -------------------------------------------------------------
    # TAB 7: SERVIDOR DE CORREO SMTP
    # -------------------------------------------------------------
    with tab_smtp:
        st.markdown("### 📧 Configuración de Servidor de Correo (SMTP)")
        st.caption("Parámetros para el despacho automático de informes técnicos en PDF a clientes y administradores.")

        smtp_srv = obtener_parametro("email_smtp_servidor", "smtp.gmail.com")
        smtp_prt = obtener_parametro("email_smtp_puerto", "587")
        smtp_rem = obtener_parametro("email_smtp_remitente", "calidad@cleanfacilitypro.pe")

        with st.form("form_cfg_smtp"):
            c_s1, c_s2 = st.columns(2)
            with c_s1:
                n_srv = st.text_input("Servidor SMTP (Host):", value=smtp_srv, key="smtp_h")
                n_prt = st.text_input("Puerto SMTP:", value=smtp_prt, key="smtp_p")
            with c_s2:
                n_rem = st.text_input("Correo Remitente:", value=smtp_rem, key="smtp_r")
                n_pwd = st.text_input("Contraseña / App Password:", type="password", placeholder="••••••••••••", key="smtp_pass")

            if st.form_submit_button("💾 Guardar Parámetros de Correo", type="primary"):
                guardar_parametro("email_smtp_servidor", n_srv.strip())
                guardar_parametro("email_smtp_puerto", n_prt.strip())
                guardar_parametro("email_smtp_remitente", n_rem.strip())
                st.success("✅ Configuración de servidor SMTP guardada.")
                st.rerun()

    # -------------------------------------------------------------
    # TAB 8: GESTIÓN DE USUARIOS Y ACCESOS
    # -------------------------------------------------------------
    with tab_users:
        st.markdown("### 👥 Administración de Usuarios, Contraseñas y Roles")
        st.caption("Controle los accesos al sistema según usuarios, perfiles de autorización y contraseñas seguras.")

        usuarios_list = obtener_lista_usuarios()
        edificios_todos = obtener_lista_edificios(solo_activos=False)
        nombres_edificios_opc = ["Todos"] + [e["nombre"] for e in edificios_todos]

        # Tabla resumen de usuarios
        filas_u = []
        for u in usuarios_list:
            filas_u.append({
                "ID": u["id"],
                "Usuario": u["username"],
                "Nombre Completo": u["nombre_completo"],
                "Perfil / Rol": u["rol"],
                "Cargo": u.get("cargo", "") or "No especificado",
                "Email": u.get("email", "") or "No especificado",
                "Sede Asignada": u.get("edificio_asignado", "Todos"),
                "Estado": "✅ Activo" if u.get("activo", 1) else "⚪ Inactivo",
                "Último Acceso": u.get("ultimo_acceso") or "Sin ingresos previos"
            })
        st.dataframe(pd.DataFrame(filas_u), hide_index=True, use_container_width=True)

        st.markdown("---")
        col_u1, col_u2 = st.columns([1, 1])

        roles_disponibles = [
            "👔 Administrador / Jefe de Operaciones",
            "👷 Supervisor de Campo",
            "🏢 Cliente / Administrador Edificio"
        ]

        with col_u1:
            st.markdown("#### ➕ Registrar Nuevo Usuario")
            with st.form("form_nuevo_usuario"):
                n_usr = st.text_input("Nombre de Usuario (Login) *:", placeholder="ej. jessica.alvarado", key="nu_user")
                n_nom = st.text_input("Nombre y Apellidos *:", placeholder="ej. Jessica Alvarado Peña", key="nu_nom")
                n_pwd = st.text_input("Contraseña Temporal / Inicial *:", type="password", placeholder="Mínimo 4 caracteres", key="nu_pass")
                n_rol = st.selectbox("Perfil / Rol de Acceso *:", roles_disponibles, index=1, key="nu_rol")
                n_car = st.text_input("Cargo o Función:", placeholder="ej. Supervisora de Calidad", key="nu_car")
                n_ema = st.text_input("Correo Electrónico:", placeholder="correo@empresa.com", key="nu_ema")
                n_sed = st.selectbox("Sede / Edificio Asignado:", nombres_edificios_opc, index=0, key="nu_sed")

                if st.form_submit_button("💾 Crear Usuario", type="primary", use_container_width=True):
                    if not n_usr.strip() or not n_pwd.strip() or not n_nom.strip():
                        st.error("Usuario, contraseña y nombre completo son campos obligatorios.")
                    else:
                        ok, msg = agregar_usuario(
                            username=n_usr.strip(),
                            password=n_pwd.strip(),
                            nombre_completo=n_nom.strip(),
                            rol=n_rol,
                            cargo=n_car.strip(),
                            email=n_ema.strip(),
                            edificio_asignado=n_sed
                        )
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

        with col_u2:
            st.markdown("#### ✏️ Modificar Usuario & Contraseña")
            if usuarios_list:
                mapa_u = {f"{u['nombre_completo']} (@{u['username']})": u for u in usuarios_list}
                u_sel_nom = st.selectbox("Seleccionar Usuario para Editar:", list(mapa_u.keys()), key="sel_u_edit")
                u_sel = mapa_u[u_sel_nom]
                u_id = u_sel["id"]

                with st.form(f"form_editar_usuario_{u_id}"):
                    e_nom = st.text_input("Nombre y Apellidos:", value=u_sel["nombre_completo"], key=f"eu_nom_{u_id}")
                    e_rol = st.selectbox("Perfil / Rol:", roles_disponibles, index=roles_disponibles.index(u_sel["rol"]) if u_sel["rol"] in roles_disponibles else 0, key=f"eu_rol_{u_id}")
                    e_car = st.text_input("Cargo:", value=u_sel.get("cargo", "") or "", key=f"eu_car_{u_id}")
                    e_ema = st.text_input("Correo Electrónico:", value=u_sel.get("email", "") or "", key=f"eu_ema_{u_id}")
                    e_sed = st.selectbox("Sede Asignada:", nombres_edificios_opc, index=nombres_edificios_opc.index(u_sel.get("edificio_asignado", "Todos")) if u_sel.get("edificio_asignado") in nombres_edificios_opc else 0, key=f"eu_sed_{u_id}")
                    e_act = st.checkbox("Usuario Activo (Permitir Ingreso)", value=bool(u_sel.get("activo", 1)), key=f"eu_act_{u_id}")

                    st.markdown("---")
                    st.caption("🔑 Si desea cambiar la contraseña de este usuario, ingrese la nueva contraseña:")
                    e_pwd_nuevo = st.text_input("Nueva Contraseña (dejar en blanco para no modificar):", type="password", key=f"eu_new_pass_{u_id}")

                    if st.form_submit_button("💾 Guardar Cambios del Perfil", type="primary", use_container_width=True):
                        ok, msg = actualizar_usuario(
                            usuario_id=u_id,
                            nombre_completo=e_nom.strip(),
                            rol=e_rol,
                            cargo=e_car.strip(),
                            email=e_ema.strip(),
                            activo=1 if e_act else 0,
                            edificio_asignado=e_sed
                        )
                        if e_pwd_nuevo and len(e_pwd_nuevo.strip()) >= 4:
                            cambiar_password_usuario(u_id, e_pwd_nuevo.strip())
                        
                        if ok:
                            st.success("✅ Perfil de usuario actualizado con éxito.")
                            st.rerun()
                        else:
                            st.error(msg)

                # Opción de eliminación de usuario (protegiendo admin principal)
                if u_sel["username"] != "admin":
                    if st.button(f"🗑️ Eliminar Usuario '@{u_sel['username']}'", key=f"btn_del_u_{u_id}", type="secondary"):
                        ok_del, msg_del = eliminar_usuario_db(u_id)
                        if ok_del:
                            st.success(msg_del)
                            st.rerun()
                        else:
                            st.error(msg_del)
                else:
                    st.info("🛡️ El usuario administrador principal ('admin') está protegido y no se puede eliminar.")

