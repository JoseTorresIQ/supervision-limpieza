"""
Módulo de Gestión de Sedes, Edificios y Cuadrillas:
Maestro de clientes, inmuebles, supervisores y parámetros operativos de servicio.
"""
import streamlit as st
import pandas as pd
from database import (
    obtener_lista_edificios, obtener_lista_supervisores,
    agregar_edificio, agregar_supervisor
)


def render_gestion_edificios():
    """Renderiza el módulo maestro de edificios y personal de supervisión."""
    st.markdown("""
        <div class="header-hero">
            <h1>🏢 Gestión de Edificios, Sedes y Supervisores</h1>
            <p>Configuración de inmuebles atendidos, dotación asignada por contrato y catálogo de supervisores.</p>
        </div>
    """, unsafe_allow_html=True)

    tab_edif, tab_sup = st.tabs(["🏢 Catálogo de Edificios", "👷 Catálogo de Supervisores"])

    # ---------------------------------------------------------
    # TAB 1: EDIFICIOS
    # ---------------------------------------------------------
    with tab_edif:
        st.markdown("### 🏢 Edificios y Centros Corporativos Registrados")
        edificios = obtener_lista_edificios()

        if edificios:
            df_edif = pd.DataFrame(edificios)[[
                "id", "nombre", "direccion", "distrito_ciudad",
                "administrador_contacto", "telefono_email", "num_pisos", "dotacion_personal_asignada"
            ]]
            df_edif.columns = ["ID", "Edificio / Sede", "Dirección", "Distrito", "Administrador", "Contacto", "Pisos", "Dotación"]
            st.dataframe(df_edif, use_container_width=True, hide_index=True)
        else:
            st.info("No hay edificios registrados en la base de datos.")

        st.markdown("---")
        with st.expander("➕ Registrar Nuevo Edificio / Condominio", expanded=False):
            with st.form("form_nuevo_edificio", clear_on_submit=True):
                col_e1, col_e2 = st.columns(2)
                with col_e1:
                    nom_edif = st.text_input("Nombre del Edificio / Sede:", placeholder="Ej: Torre Corporativa Begonias", key="add_nom_edif")
                    dir_edif = st.text_input("Dirección Completa:", placeholder="Ej: Calle Las Begonias 441", key="add_dir_edif")
                    dist_edif = st.text_input("Distrito / Ciudad:", value="San Isidro, Lima", key="add_dist_edif")
                    admin_edif = st.text_input("Administrador / Contacto en Sede:", placeholder="Ej: Ing. Jorge Alarcón", key="add_admin_edif")
                
                with col_e2:
                    tel_edif = st.text_input("Teléfono / Correo de Contacto:", placeholder="Ej: 998765432 / admin@begonias.pe", key="add_tel_edif")
                    col_p, col_s, col_d = st.columns(3)
                    with col_p:
                        pisos_edif = st.number_input("N° Pisos:", min_value=1, max_value=100, value=12, key="add_pisos_edif")
                    with col_s:
                        sotanos_edif = st.number_input("N° Sótanos:", min_value=0, max_value=10, value=2, key="add_sotanos_edif")
                    with col_d:
                        dotacion_edif = st.number_input("Dotación Operarios:", min_value=1, max_value=100, value=4, key="add_dot_edif")
                    
                    obs_edif = st.text_area("Observaciones Contractuales o Exigencias:", placeholder="Ej: Exigencia de pulido de mármol quincenal.", key="add_obs_edif")

                if st.form_submit_button("💾 Guardar Nuevo Edificio", type="primary"):
                    if nom_edif.strip() and dir_edif.strip():
                        agregar_edificio(
                            nombre=nom_edif,
                            direccion=dir_edif,
                            distrito=dist_edif,
                            administrador=admin_edif,
                            telefono=tel_edif,
                            pisos=int(pisos_edif),
                            sotanos=int(sotanos_edif),
                            dotacion=int(dotacion_edif),
                            observaciones=obs_edif
                        )
                        st.success(f"Edificio '{nom_edif}' registrado exitosamente.")
                        st.rerun()
                    else:
                        st.error("Por favor ingrese al menos el nombre y la dirección del edificio.")

    # ---------------------------------------------------------
    # TAB 2: SUPERVISORES
    # ---------------------------------------------------------
    with tab_sup:
        st.markdown("### 👷 Supervisores e Inspectores Habilitados")
        supervisores = obtener_lista_supervisores()

        if supervisores:
            df_sup = pd.DataFrame(supervisores)[["id", "nombre_completo", "dni_ce", "cargo", "telefono"]]
            df_sup.columns = ["ID", "Nombre Completo", "DNI / Carnet", "Cargo", "Teléfono"]
            st.dataframe(df_sup, use_container_width=True, hide_index=True)
        else:
            st.info("No hay supervisores registrados.")

        st.markdown("---")
        with st.expander("➕ Registrar Nuevo Supervisor", expanded=False):
            with st.form("form_nuevo_supervisor", clear_on_submit=True):
                col_s1, col_s2 = st.columns(2)
                with col_s1:
                    nom_sup = st.text_input("Nombre Completo:", placeholder="Ej: Pedro Valdivia Huamán", key="add_nom_sup")
                    dni_sup = st.text_input("DNI o Carnet de Extranjería:", placeholder="Ej: 45892147", key="add_dni_sup")
                with col_s2:
                    cargo_sup = st.text_input("Cargo:", value="Supervisor de Operaciones y Calidad", key="add_cargo_sup")
                    tel_sup = st.text_input("Teléfono Móvil:", placeholder="Ej: +51 987 112 233", key="add_tel_sup")

                if st.form_submit_button("💾 Guardar Supervisor", type="primary"):
                    if nom_sup.strip() and dni_sup.strip():
                        agregar_supervisor(
                            nombre=nom_sup,
                            dni=dni_sup,
                            cargo=cargo_sup,
                            telefono=tel_sup
                        )
                        st.success(f"Supervisor '{nom_sup}' registrado exitosamente.")
                        st.rerun()
                    else:
                        st.error("Por favor ingrese el nombre completo y el DNI.")
