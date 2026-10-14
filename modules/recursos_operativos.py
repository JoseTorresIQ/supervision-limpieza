"""
Módulo de Gestión de Recursos Operativos:
Control de stock de químicos e insumos de limpieza (Kardex) y
ficha técnica de mantenimiento preventivo de maquinarias y equipos.
"""
import io
import streamlit as st
import pandas as pd
from datetime import datetime, date

from database import (
    obtener_insumos, agregar_insumo, registrar_movimiento_insumo, eliminar_insumo,
    obtener_maquinarias, agregar_maquinaria, actualizar_maquinaria, eliminar_maquinaria,
    obtener_lista_edificios
)


def render_modulo_recursos():
    """Renderiza la gestión de insumos y mantenimiento de maquinaria."""
    st.markdown("""
        <div class="header-hero">
            <h1>📦 Recursos Operativos: Químicos, Insumos & Maquinarias</h1>
            <p>Control de existencias de químicos, kardex de insumos y hoja de vida de equipos de limpieza industrial.</p>
            <div class="header-badges">
                <span class="badge-tag">🧪 Stock de Químicos</span>
                <span class="badge-tag">⚠️ Alerta Stock Crítico</span>
                <span class="badge-tag">⚙️ Mantenimiento Preventivo</span>
                <span class="badge-tag">🧼 Equipamiento Industrial</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    tab_insumos, tab_maquinas = st.tabs([
        "🧪 Control de Stock & Insumos",
        "⚙️ Maquinarias & Mantenimiento"
    ])

    edificios = obtener_lista_edificios(solo_activos=True)
    nombres_edif = ["Todos"] + [e["nombre"] for e in edificios]

    # -------------------------------------------------------------
    # TAB 1: INSUMOS Y QUÍMICOS DE LIMPIEZA
    # -------------------------------------------------------------
    with tab_insumos:
        st.markdown("### 🧪 Inventario de Insumos y Dosificación por Edificio")

        f_edif_ins = st.selectbox("Filtrar por Edificio:", nombres_edif, key="ins_f_edif")
        insumos = obtener_insumos(filtro_edificio=f_edif_ins)

        # Detectar insumos en stock crítico
        criticos = [i for i in insumos if i["stock_actual"] <= i["stock_minimo"]]
        if criticos:
            st.warning(f"⚠️ **Atención:** Se detectaron {len(criticos)} productos en stock crítico o agotándose:")
            for c in criticos:
                st.markdown(f"- 🔴 **{c['producto_nombre']}** en *{c['edificio_nombre']}*: Stock Actual `{c['stock_actual']} {c['unidad_medida']}` (Mínimo: `{c['stock_minimo']}`).")

        st.markdown("---")
        col_t1, col_t2 = st.tabs(["📋 Lista de Insumos & Movimientos", "➕ Registrar Nuevo Producto"])

        with col_t2:
            st.markdown("#### ➕ Registrar Producto / Insumo en Sede")
            with st.form("form_nuevo_insumo", clear_on_submit=True):
                c_i1, c_i2 = st.columns(2)
                with c_i1:
                    e_sel = st.selectbox("Edificio Asignado *:", [e["nombre"] for e in edificios], key="add_ins_edif")
                    p_nom = st.text_input("Nombre del Producto / Químico *:", placeholder="Ej: Cera Acrílica Alto Brillo", key="add_ins_nom")
                    p_cat = st.selectbox("Categoría:", ["Químicos de Limpieza", "Desinfectantes", "Cristales", "Insumos Sanitarios", "Bolsas y Residuos", "Herramientas y Mopas"], key="add_ins_cat")
                with c_i2:
                    p_uni = st.selectbox("Unidad de Medida:", ["Galones", "Litros", "Rollos", "Paquetes (x50)", "Unidades", "Kilos"], key="add_ins_uni")
                    p_stock = st.number_input("Stock Inicial:", min_value=0.0, value=5.0, step=1.0, key="add_ins_ini")
                    p_min = st.number_input("Stock Mínimo de Alerta:", min_value=0.0, value=2.0, step=1.0, key="add_ins_min")

                if st.form_submit_button("💾 Guardar Insumo", type="primary"):
                    e_obj = next((e for e in edificios if e["nombre"] == e_sel), None)
                    if e_obj and p_nom.strip():
                        agregar_insumo(
                            edificio_id=e_obj["id"],
                            edificio_nombre=e_sel,
                            producto_nombre=p_nom.strip(),
                            categoria=p_cat,
                            unidad_medida=p_uni,
                            stock_actual=float(p_stock),
                            stock_minimo=float(p_min)
                        )
                        st.success(f"Insumo '{p_nom}' registrado exitosamente.")
                        st.rerun()

        with col_t1:
            if not insumos:
                st.info("No hay insumos registrados para esta sede.")
            else:
                for ins in insumos:
                    es_critico = ins["stock_actual"] <= ins["stock_minimo"]
                    semaforo = "🔴 CRÍTICO" if es_critico else "🟢 NORMAL"

                    with st.expander(f"{semaforo} | {ins['producto_nombre']} — {ins['stock_actual']} {ins['unidad_medida']} ({ins['edificio_nombre']})", expanded=es_critico):
                        ci1, ci2 = st.columns([2, 1.5])
                        with ci1:
                            st.markdown(f"**Categoría:** `{ins['categoria']}`")
                            st.markdown(f"**Stock Actual:** `{ins['stock_actual']} {ins['unidad_medida']}` | **Stock Mínimo:** `{ins['stock_minimo']} {ins['unidad_medida']}`")
                            st.caption(f"Última actualización: {ins.get('ultimo_movimiento', 'N/D')}")
                        with ci2:
                            st.markdown("##### 🔄 Registrar Movimiento Kardex")
                            with st.form(f"form_mov_{ins['id']}"):
                                t_mov = st.selectbox("Tipo:", ["Egreso", "Ingreso", "Ajuste"], key="kmov_t_" + str(ins["id"]))
                                cant = st.number_input("Cantidad:", min_value=0.5, value=1.0, step=0.5, key="kmov_c_" + str(ins["id"]))
                                resp = st.text_input("Responsable:", value="Líder de Cuadrilla", key="kmov_r_" + str(ins["id"]))
                                mot = st.text_input("Motivo / Destino:", placeholder="Ej: Mopado pisos 1 al 5", key="kmov_m_" + str(ins["id"]))
                                if st.form_submit_button("Aplicar"):
                                    registrar_movimiento_insumo(ins["id"], t_mov, cant, resp, mot)
                                    st.success("Movimiento registrado.")
                                    st.rerun()

    # -------------------------------------------------------------
    # TAB 2: MAQUINARIAS Y MANTENIMIENTO
    # -------------------------------------------------------------
    with tab_maquinas:
        st.markdown("### ⚙️ Inventario de Maquinarias y Plan de Mantenimiento")

        f_edif_maq = st.selectbox("Filtrar por Edificio:", nombres_edif, key="maq_f_edif")
        maquinas = obtener_maquinarias(filtro_edificio=f_edif_maq)

        tab_m_list, tab_m_add = st.tabs(["📋 Equipos Registrados", "➕ Registrar Maquinaria"])

        with tab_m_add:
            st.markdown("#### ➕ Registrar Nueva Maquinaria")
            with st.form("form_nueva_maquina", clear_on_submit=True):
                cm1, cm2 = st.columns(2)
                with cm1:
                    cod_eq = st.text_input("Código Interno *:", placeholder="Ej: LUST-03", key="maq_cod")
                    tipo_eq = st.selectbox("Tipo de Equipo *:", ["Lustradora Rotativa de 17\"", "Aspiradora Industrial Seco/Líquido", "Hidrolavadora de Alta Presión", "Fregadora Automática", "Soplador / Secador de Alfombras", "Pulidora de Granito"], key="maq_tipo")
                    marca_eq = st.text_input("Marca y Modelo *:", placeholder="Ej: Kärcher Professional NT 70", key="maq_marca")
                    serie_eq = st.text_input("Número de Serie:", placeholder="Ej: SN-4829104", key="maq_serie")
                with cm2:
                    ed_maq = st.selectbox("Edificio Asignado *:", [e["nombre"] for e in edificios], key="maq_edif")
                    est_maq = st.selectbox("Estado Operativo:", ["Operativo", "En Mantenimiento", "Fuera de Servicio"], key="maq_est")
                    f_adq = st.date_input("Fecha de Adquisición:", value=date.today(), key="maq_fadq")
                    f_prox = st.date_input("Próximo Mantenimiento:", value=date.today() + pd.Timedelta(days=90), key="maq_fprox")
                    obs_maq = st.text_area("Observaciones Técnicas:", placeholder="Ej: Requiere revisión de carbones.", key="maq_obs")

                if st.form_submit_button("💾 Guardar Maquinaria", type="primary"):
                    e_obj = next((e for e in edificios if e["nombre"] == ed_maq), None)
                    if cod_eq.strip() and marca_eq.strip():
                        agregar_maquinaria(
                            codigo_equipo=cod_eq.strip().upper(),
                            tipo_maquinaria=tipo_eq,
                            marca_modelo=marca_eq.strip(),
                            serie=serie_eq.strip(),
                            edificio_id=e_obj["id"] if e_obj else None,
                            edificio_nombre=ed_maq,
                            estado_operativo=est_maq,
                            fecha_adq=str(f_adq),
                            ultimo_mant=str(date.today()),
                            prox_mant=str(f_prox),
                            observaciones=obs_maq.strip()
                        )
                        st.success(f"Maquinaria '{cod_eq}' guardada exitosamente.")
                        st.rerun()

        with tab_m_list:
            if not maquinas:
                st.info("No hay maquinarias registradas.")
            else:
                for m in maquinas:
                    est = m.get("estado_operativo", "Operativo")
                    if est == "Operativo":
                        b_maq = "🟢 OPERATIVO"
                    elif est == "En Mantenimiento":
                        b_maq = "🟡 EN MANTENIMIENTO"
                    else:
                        b_maq = "🔴 FUERA DE SERVICIO"

                    with st.expander(f"{b_maq} | [{m['codigo_equipo']}] {m['tipo_maquinaria']} — {m['marca_modelo']} ({m['edificio_nombre']})"):
                        c_mq1, c_mq2 = st.columns([2, 1])
                        with c_mq1:
                            st.markdown(f"**Serie:** `{m.get('serie', 'N/D')}` | **Edificio:** `{m['edificio_nombre']}`")
                            st.markdown(f"**Último Mantenimiento:** `{m.get('ultimo_mantenimiento', 'N/D')}`")
                            st.markdown(f"**Próximo Mantenimiento Programado:** `{m.get('proximo_mantenimiento', 'N/D')}`")
                            if m.get("observaciones"):
                                st.caption(f"📝 Observaciones: {m['observaciones']}")

                        with c_mq2:
                            st.markdown("##### 🛠️ Actualizar Mantenimiento")
                            with st.form(f"form_mant_{m['id']}"):
                                n_est = st.selectbox("Estado:", ["Operativo", "En Mantenimiento", "Fuera de Servicio"], index=["Operativo", "En Mantenimiento", "Fuera de Servicio"].index(est) if est in ["Operativo", "En Mantenimiento", "Fuera de Servicio"] else 0, key=f"nm_est_{m['id']}")
                                n_prox = st.date_input("Nueva Fecha Próx. Mantenimiento:", value=date.today() + pd.Timedelta(days=90), key=f"nm_px_{m['id']}")
                                n_obs = st.text_input("Nota de Mantenimiento:", value=m.get("observaciones", ""), key=f"nm_ob_{m['id']}")
                                if st.form_submit_button("Actualizar"):
                                    actualizar_maquinaria(
                                        equipo_id=m["id"],
                                        estado_operativo=n_est,
                                        ultimo_mant=str(date.today()),
                                        prox_mant=str(n_prox),
                                        observaciones=n_obs.strip()
                                    )
                                    st.success("Ficha de maquinaria actualizada.")
                                    st.rerun()
