"""
Punto de Entrada Principal (Entry Point):
Sistema de Gestión y Reporte de Supervisión de Limpieza de Edificios (CLEANFACILITY PRO).
Conforme a Normas Técnicas ISSA CIMS, OSHA y Ley N° 29783 de Seguridad y Salud en el Trabajo.
"""
import os
import sys

# Si se ejecuta directamente con 'python app.py', redirigir automáticamente a Streamlit CLI
if __name__ == "__main__":
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        if get_script_run_ctx(suppress_warning=True) is None:
            from streamlit.web import cli as stcli
            sys.argv = ["streamlit", "run", sys.argv[0], "--server.port=8502"]
            sys.exit(stcli.main())
    except Exception:
        pass

import streamlit as st
from config import (
    SYSTEM_TITLE, SYSTEM_SUBTITLE, FORMAT_CODE, FORMAT_VERSION,
    COMPANY_NAME, NORMATIVE_REFERENCES, STATIC_DIR
)
from database import init_db
from modules.nueva_supervision import render_formulario_nueva_supervision
from modules.historial import render_historial_supervisiones
from modules.dashboard import render_dashboard_analitica
from modules.configuracion_maestros import render_modulo_configuracion
from modules.capa_tracker import render_modulo_capa
from modules.cronograma import render_modulo_cronograma
from modules.recursos_operativos import render_modulo_recursos
from modules.reportes_consolidados import render_modulo_consolidados
from modules.auth import render_login, render_user_sidebar


# Configuración global de la página
st.set_page_config(
    page_title=f"{SYSTEM_TITLE} | Supervisión de Limpieza de Edificios",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicializar Base de Datos SQLite
init_db()

# Cargar estilos CSS personalizados
css_path = STATIC_DIR / "css" / "style.css"
if os.path.exists(css_path):
    with open(css_path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def render_normativa_estandares():
    """Renderiza la sección de manuales, código de colores y estándares técnicos de limpieza."""
    st.markdown("""
        <div class="header-hero">
            <h1>📚 Manual Técnico, Normativa y Buenas Prácticas de Limpieza</h1>
            <p>Protocolos de desinfección, código de colores para microfibras/mopas y estándares de seguridad SST.</p>
        </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### 🎨 Código Internacional de Colores para Insumos")
        st.markdown("""
        Para prevenir la **contaminación cruzada** en edificios corporativos y residenciales:
        - 🔴 **ROJO:** Exclusivo para inodoros, urinarios y zonas de alto riesgo biológico en baños.
        - 🟡 **AMARILLO:** Lavamanos, espejos, azulejos y superficies secundarias de servicios higiénicos.
        - 🔵 **AZUL:** Áreas generales, escritorios de oficina, vidrios interiores y pasadizos.
        - 🟢 **VERDE:** Comedores, cafeterías, kitchenette y manipulación de alimentos.
        """)

        st.markdown("### 🦺 Seguridad y Salud en el Trabajo (Ley 29783)")
        st.markdown("""
        - **Señalética Obligatoria:** Colocar el cono/caballete *"Cuidado: Piso Mojado"* antes de iniciar el trapeado.
        - **EPP Obligatorio:** Uso de guantes impermeables para lavado y lentes de protección durante dilución de químicos.
        - **Ergonomía:** Ajuste de mangos de mopas a la altura del hombro para evitar lesiones lumbares.
        """)

    with c2:
        st.markdown("### 🧪 Matriz de Dosificación de Químicos de Limpieza")
        st.markdown("""
        | Producto Químico | Dilución Recomendada | Superficie / Aplicación | Tiempo de Contacto |
        |---|---|---|---|
        | **Detergente Neutro** | 1:100 (10 ml / Litro) | Pisos de porcelanato, mármol y vinilo | Inmediato |
        | **Desinfectante Amonio 5ta Gen** | 1:128 (8 ml / Litro) | Manijas, botoneras, cabinas y baños | 10 Minutos |
        | **Limpiavidrios Antiestático** | Puro / 1:1 | Mamparas, ventanas y espejos | Secado con jalador |
        | **Desincrustante Ácido** | 1:10 (Uso focalizado) | Fondo de inodoros y sarro adherido | 5 Minutos con enjuague |
        | **Abrillantador de Acero** | Puro (Paño seco) | Paneles y puertas de ascensores | Frotado unidireccional |
        """)

        st.markdown("### 📜 Normativa y Estándares Aplicables")
        for norma in NORMATIVE_REFERENCES:
            st.markdown(f"- ✅ **{norma}**")


def main():
    """Función principal de navegación del sistema con control de acceso por usuario y contraseña."""
    # 1. Comprobar si el usuario está autenticado en la sesión
    if not st.session_state.get("autenticado", False):
        render_login()
        return

    usuario_actual = st.session_state.get("usuario_actual", {})
    rol_original = usuario_actual.get("rol", "👔 Administrador / Jefe de Operaciones")

    # 2. Barra lateral de navegación
    with st.sidebar:
        st.markdown(f"### 🏢 {SYSTEM_TITLE}")
        st.caption(f"**{COMPANY_NAME}**\n\nFormato: `{FORMAT_CODE}` | Rev. `{FORMAT_VERSION}`")
        st.markdown("---")

        # Perfil del usuario autenticado con botón de Cerrar Sesión
        render_user_sidebar(usuario_actual)

        # Si el usuario es Administrador, permitir simular vista de otros perfiles
        rol_efectivo = rol_original
        if "Administrador" in rol_original:
            sim_rol = st.selectbox(
                "👁️ MODO DE VISTA (SIMULAR PERFIL):",
                [
                    "👔 Administrador / Jefe de Operaciones (Acceso Total)",
                    "👷 Supervisor de Campo",
                    "🏢 Cliente / Administrador Edificio"
                ],
                index=0,
                key="sel_simular_rol"
            )
            rol_efectivo = sim_rol

        st.markdown("---")

        # Menú dinámico según el rol
        if "Administrador" in rol_efectivo:
            modulos_disponibles = [
                "📋 Nueva Supervisión",
                "🚨 Seguimiento Incidencias (CAPA)",
                "📅 Cronograma & Planificador",
                "📑 Historial de Informes",
                "📊 Dashboard & KPIs (Pareto)",
                "📑 Informe Consolidado Mensual",
                "📦 Insumos & Maquinarias",
                "⚙️ Configuración & Maestros",
                "📚 Normativa & Estándares"
            ]
        elif "Supervisor" in rol_efectivo:
            modulos_disponibles = [
                "📋 Nueva Supervisión",
                "🚨 Seguimiento Incidencias (CAPA)",
                "📅 Cronograma & Planificador",
                "📑 Historial de Informes",
                "📦 Insumos & Maquinarias",
                "📚 Normativa & Estándares"
            ]
        else:  # Cliente / Administrador de Edificio
            modulos_disponibles = [
                "📑 Historial de Informes",
                "🚨 Seguimiento Incidencias (CAPA)",
                "📊 Dashboard & KPIs (Pareto)",
                "📑 Informe Consolidado Mensual",
                "📚 Normativa & Estándares"
            ]

        opcion = st.radio(
            "MÓDULOS DISPONIBLES:",
            modulos_disponibles,
            index=0
        )

        st.markdown("---")
        st.info("💡 **Consejo:** Puede sincronizar inspecciones tomadas offline en la PWA móvil importando el archivo JSON en **'Nueva Supervisión'**.")

    # Renderizado condicional del módulo seleccionado
    if opcion == "📋 Nueva Supervisión":
        render_formulario_nueva_supervision()
    elif opcion == "🚨 Seguimiento Incidencias (CAPA)":
        render_modulo_capa()
    elif opcion == "📅 Cronograma & Planificador":
        render_modulo_cronograma()
    elif opcion == "📑 Historial de Informes":
        render_historial_supervisiones()
    elif opcion == "📊 Dashboard & KPIs (Pareto)":
        render_dashboard_analitica()
    elif opcion == "📑 Informe Consolidado Mensual":
        render_modulo_consolidados()
    elif opcion == "📦 Insumos & Maquinarias":
        render_modulo_recursos()
    elif opcion == "⚙️ Configuración & Maestros":
        render_modulo_configuracion()
    elif opcion == "📚 Normativa & Estándares":
        render_normativa_estandares()


if __name__ == "__main__":
    main()

