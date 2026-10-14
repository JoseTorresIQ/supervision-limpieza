"""
Módulo de Autenticación, Control de Accesos y Gestión de Sesiones:
Interfaz de ingreso con contraseña según usuarios y roles (Admin, Supervisor, Cliente).
"""
import streamlit as st
from config import SYSTEM_TITLE, COMPANY_NAME, FORMAT_CODE, FORMAT_VERSION
from database import autenticar_usuario, obtener_lista_usuarios


def render_login():
    """Renderiza la pantalla de inicio de sesión con contraseña según usuario."""
    st.markdown("""
        <div style="text-align: center; margin-bottom: 24px; padding: 20px 10px;">
            <div style="display: inline-block; background: linear-gradient(135deg, #0F172A 0%, #1E293B 50%, #0369A1 100%); padding: 18px 28px; border-radius: 20px; box-shadow: 0 10px 25px -5px rgba(2, 132, 199, 0.3); border: 1px solid rgba(255, 255, 255, 0.1);">
                <div style="font-size: 2.2rem; font-weight: 800; color: #FFFFFF; letter-spacing: -0.5px; margin-bottom: 4px;">
                    🏢 CLEANFACILITY PRO
                </div>
                <div style="font-size: 0.95rem; color: #94A3B8; font-weight: 500;">
                    Sistema de Gestión y Supervisión de Limpieza de Edificios
                </div>
                <div style="margin-top: 10px; display: flex; justify-content: center; gap: 8px; flex-wrap: wrap;">
                    <span class="badge-tag">ISSA CIMS Standard</span>
                    <span class="badge-tag">SST Ley N° 29783</span>
                    <span class="badge-tag">Formato {format_code} Rev. {format_version}</span>
                </div>
            </div>
        </div>
    """.format(format_code=FORMAT_CODE, format_version=FORMAT_VERSION), unsafe_allow_html=True)

    col_izq, col_card, col_der = st.columns([1, 1.8, 1])

    with col_card:
        st.markdown("""
            <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 16px; padding: 24px 28px; box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);">
                <h2 style="font-size: 1.35rem; font-weight: 800; color: #0F172A; margin: 0 0 6px 0; display: flex; align-items: center; gap: 8px;">
                    🔐 Iniciar Sesión en el Sistema
                </h2>
                <p style="font-size: 0.88rem; color: #64748B; margin: 0 0 18px 0;">
                    Ingrese su usuario y contraseña asignada para acceder a los módulos autorizados según su perfil.
                </p>
            </div>
        """, unsafe_allow_html=True)

        with st.form("form_inicio_sesion"):
            u_input = st.text_input(
                "👤 Nombre de Usuario o Correo:",
                placeholder="ej. admin, supervisor, cliente",
                key="input_login_user"
            )
            p_input = st.text_input(
                "🔑 Contraseña:",
                type="password",
                placeholder="Ingrese su contraseña",
                key="input_login_pass"
            )

            btn_login = st.form_submit_button(
                "🚀 INICIAR SESIÓN",
                type="primary",
                use_container_width=True
            )

            if btn_login:
                if not u_input.strip() or not p_input.strip():
                    st.error("⚠️ Ingrese su usuario y contraseña para continuar.")
                else:
                    auth_res = autenticar_usuario(u_input, p_input)
                    if not auth_res:
                        st.error("❌ Credenciales incorrectas. Verifique su usuario y contraseña.")
                    elif isinstance(auth_res, dict) and auth_res.get("error") == "inactivo":
                        st.warning("⚠️ Su cuenta se encuentra inactiva. Comuníquese con el Administrador de Operaciones.")
                    else:
                        st.session_state["autenticado"] = True
                        st.session_state["usuario_actual"] = auth_res
                        st.success(f"🎉 ¡Bienvenido(a), {auth_res['nombre_completo']}! Accediendo...")
                        st.rerun()

        # Botones de Acceso Rápido / Demo para facilitar pruebas al usuario
        with st.expander("🔑 Credenciales de Acceso Rápidas / Perfiles Demo", expanded=True):
            st.caption("Seleccione un perfil para probar el acceso instantáneo con sus permisos correspondientes:")
            
            c_d1, c_d2, c_d3 = st.columns(3)
            with c_d1:
                if st.button("👔 Administrador\n`admin / admin123`", key="btn_quick_admin", use_container_width=True):
                    auth_res = autenticar_usuario("admin", "admin123")
                    if auth_res and not auth_res.get("error"):
                        st.session_state["autenticado"] = True
                        st.session_state["usuario_actual"] = auth_res
                        st.rerun()
            
            with c_d2:
                if st.button("👷 Supervisor\n`supervisor / super123`", key="btn_quick_super", use_container_width=True):
                    auth_res = autenticar_usuario("supervisor", "super123")
                    if auth_res and not auth_res.get("error"):
                        st.session_state["autenticado"] = True
                        st.session_state["usuario_actual"] = auth_res
                        st.rerun()

            with c_d3:
                if st.button("🏢 Cliente Sede\n`cliente / cliente123`", key="btn_quick_cliente", use_container_width=True):
                    auth_res = autenticar_usuario("cliente", "cliente123")
                    if auth_res and not auth_res.get("error"):
                        st.session_state["autenticado"] = True
                        st.session_state["usuario_actual"] = auth_res
                        st.rerun()

            st.markdown("""
                <div style="font-size:0.75rem; color:#64748B; margin-top:10px; line-height: 1.4;">
                    • <b>Administrador:</b> Acceso total a auditorías, CAPA, cronogramas, consolidados, reportes y configuración.<br>
                    • <b>Supervisor:</b> Registro de nuevas auditorías, checklist técnico, fotos, control de insumos y equipos.<br>
                    • <b>Cliente / Junta:</b> Consulta exclusiva de informes de su sede, indicadores de calidad y consolidados PDF.
                </div>
            """, unsafe_allow_html=True)


def render_user_sidebar(usuario: dict):
    """Renderiza la tarjeta del usuario autenticado en la barra lateral con opción de cerrar sesión."""
    rol_str = usuario.get("rol", "")
    if "Administrador" in rol_str:
        icono_rol = "👔"
        badge_bg = "#0284C7"
    elif "Supervisor" in rol_str:
        icono_rol = "👷"
        badge_bg = "#10B981"
    else:
        icono_rol = "🏢"
        badge_bg = "#8B5CF6"

    st.markdown(f"""
        <div style="background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%); border-radius: 12px; padding: 14px 16px; margin-bottom: 12px; color: white; border-left: 4px solid {badge_bg}; box-shadow: 0 4px 10px rgba(0,0,0,0.1);">
            <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.5px; color: #94A3B8; font-weight: 700;">
                USUARIO CONECTADO
            </div>
            <div style="font-size: 0.98rem; font-weight: 800; margin: 4px 0 2px 0; color: #FFFFFF; display: flex; align-items: center; gap: 6px;">
                <span>{icono_rol}</span> <span>{usuario.get('nombre_completo', 'Usuario')}</span>
            </div>
            <div style="display: inline-block; background: {badge_bg}; color: white; padding: 2px 8px; border-radius: 6px; font-size: 0.7rem; font-weight: 700; margin-top: 3px;">
                {usuario.get('rol', '')}
            </div>
            <div style="font-size: 0.75rem; color: #CBD5E1; margin-top: 5px;">
                {usuario.get('cargo') or 'Usuario del Sistema'}
            </div>
        </div>
    """, unsafe_allow_html=True)

    if st.button("🚪 Cerrar Sesión", key="btn_logout_sidebar", use_container_width=True, type="secondary"):
        st.session_state.pop("autenticado", None)
        st.session_state.pop("usuario_actual", None)
        st.session_state.pop("sel_rol_usuario", None)
        st.rerun()
