import streamlit as st
import pandas as pd
from utils.db import supabase, run_query
from utils.helpers import (
    mostrar_notificaciones, agregar_notificacion, validar_usuario_unico,
    check_open_orders, hashear_password, registrar_accion_critica,
    validar_politica_password, PASSWORD_MIN_LENGTH
)
from utils.nav_button import render_back_button


def render():
    st.title("USUARIOS")
    render_back_button()
    mostrar_notificaciones()

    rol = st.session_state.get('rol', '')

    if rol == 'Admin':
        tab_crear, tab_gestionar, tab_herramientas = st.tabs(["CREAR USUARIO", "GESTIONAR USUARIOS", "🔧 HERRAMIENTAS"])
    else:
        tab_crear, tab_gestionar = st.tabs(["CREAR USUARIO", "GESTIONAR USUARIOS"])
        tab_herramientas = None

    with tab_crear:
        _render_crear()

    with tab_gestionar:
        _render_gestionar()

    if tab_herramientas is not None:
        with tab_herramientas:
            _render_herramientas()


# ==============================================================================
# ➕ CREAR USUARIO
# ==============================================================================
def _render_crear():
    st.subheader("Registrar Nuevo Usuario")
    with st.form("new_user_form"):
        c1, c2 = st.columns(2)
        documento = c1.text_input("Documento/ID", key="new_user_doc")
        nombre = c2.text_input("Nombre Completo", key="new_user_name")
        password = c1.text_input("Contraseña", type="password", key="new_user_pass")
        st.caption(f"🔒 Mínimo {PASSWORD_MIN_LENGTH} caracteres, mayúscula, minúscula y número.")
        rol = c2.selectbox("Rol", ["Tecnico", "Programador", "Admin"], key="new_user_rol")
        submitted = st.form_submit_button("REGISTRAR USUARIO", type="primary")

        if submitted:
            if documento and nombre and password and rol:
                if not validar_usuario_unico(documento):
                    agregar_notificacion('error', 'El documento ya existe en el sistema.')
                else:
                    pass_valida, pass_error = validar_politica_password(password)
                    if not pass_valida:
                        agregar_notificacion('error', pass_error)
                    else:
                        try:
                            res = supabase.table("usuarios").insert({
                                "documento": documento, "nombre": nombre,
                                "password": hashear_password(password), "rol": rol
                            }).execute()
                            if res.data:
                                st.cache_data.clear()
                                registrar_accion_critica("CREAR_USUARIO", documento, f"Nombre: {nombre}, Rol: {rol}")
                                agregar_notificacion('success', f'Usuario {nombre} registrado con éxito.')
                                st.rerun()
                            else:
                                agregar_notificacion('error', 'Error al registrar el usuario.')
                        except Exception as e:
                            agregar_notificacion('error', f'Error de base de datos: {e}')
            else:
                agregar_notificacion('warning', 'Por favor, complete todos los campos.')


# ==============================================================================
# ✏️ GESTIONAR USUARIOS
# ==============================================================================
def _render_gestionar():
    df_users = run_query("usuarios")
    if not df_users.empty:
        st.subheader("Seleccionar Usuario para Gestionar")
        user_options = {f"{row['nombre']} (ID: {row['id']})": row['id'] for _, row in df_users.iterrows()}
        user_options_list = ["-- Seleccione un usuario --"] + list(user_options.keys())
        selected_option = st.selectbox("Usuario:", user_options_list, key="user_selector")

        st.markdown("### Lista Completa de Usuarios")
        st.dataframe(df_users[['id', 'documento', 'nombre', 'rol']], hide_index=True, use_container_width=True)

        if selected_option != "-- Seleccione un usuario --":
            user_id = user_options[selected_option]
            selected_user = df_users[df_users['id'] == user_id].iloc[0]

            st.markdown("---")
            st.markdown(f"### Editando: **{selected_user['nombre']}** (ID: {user_id})")

            with st.form(key=f"edit_user_form_{user_id}"):
                c1, c2 = st.columns(2)
                edit_doc = c1.text_input("Documento/ID", value=selected_user['documento'])
                edit_name = c2.text_input("Nombre Completo", value=selected_user['nombre'])
                rol_options = ["Tecnico", "Programador", "Admin"]
                current_rol_index = rol_options.index(selected_user['rol']) if selected_user['rol'] in rol_options else 0
                new_rol = st.selectbox("Rol", rol_options, index=current_rol_index)
                new_password = st.text_input("Nueva Contraseña (Dejar vacío para no cambiar)", type="password")
                if new_password:
                    st.caption(f"🔒 Mínimo {PASSWORD_MIN_LENGTH} caracteres, mayúscula, minúscula y número.")
                st.markdown("<br>", unsafe_allow_html=True)
                update_submitted = st.form_submit_button("✅ ACTUALIZAR USUARIO", type="primary", use_container_width=True)

                if update_submitted:
                    if new_rol != selected_user['rol']:
                        if check_open_orders(user_id):
                            agregar_notificacion('error',
                                f'El usuario **{selected_user["nombre"]}** tiene Órdenes pendientes. Debe cerrarlas antes de cambiar su rol.')
                            st.stop()
                    if not validar_usuario_unico(edit_doc, user_id):
                        agregar_notificacion('error', 'El documento ya está en uso por otro usuario.')
                    else:
                        update_data = {"documento": edit_doc, "nombre": edit_name, "rol": new_rol}
                        cambios = []
                        if new_rol != selected_user['rol']:
                            cambios.append(f"Rol: {selected_user['rol']} → {new_rol}")
                        if new_password:
                            pass_valida, pass_error = validar_politica_password(new_password)
                            if not pass_valida:
                                agregar_notificacion('error', pass_error)
                                st.stop()
                            update_data["password"] = hashear_password(new_password)
                            cambios.append("Contraseña actualizada")
                        try:
                            supabase.table("usuarios").update(update_data).eq("id", user_id).execute()
                            st.cache_data.clear()
                            if cambios:
                                registrar_accion_critica("ACTUALIZAR_USUARIO",
                                                         st.session_state.get('usuario', '?'),
                                                         f"Usuario: {edit_name} — {', '.join(cambios)}")
                            agregar_notificacion('success', f'Usuario {edit_name} actualizado.')
                            st.rerun()
                        except Exception as e:
                            agregar_notificacion('error', f'Error al actualizar: {e}')

            st.markdown("---")
            st.markdown("### 🗑️ Zona de Eliminación")
            has_open_orders = check_open_orders(user_id)
            if has_open_orders:
                st.markdown(f"""
                    <div style='background:rgba(239,68,68,0.15);border:2px solid #EF4444;border-radius:8px;padding:20px;text-align:center;'>
                        <p style='color:#FCA5A5;margin:0;font-size:1.1rem;'>⚠️ <strong>ELIMINACIÓN BLOQUEADA</strong></p>
                        <p style='color:#FEE2E2;margin-top:10px;font-size:0.95rem;'>El usuario <strong>{selected_user['nombre']}</strong> tiene Órdenes de Trabajo pendientes.</p>
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.warning(f"⚠️ Esta acción eliminará permanentemente al usuario **{selected_user['nombre']}**")
                confirm_del_user = st.text_input("Escriba ELIMINAR para confirmar", key=f"confirm_del_user_{user_id}", placeholder="ELIMINAR")
                if st.button("🗑️ ELIMINAR USUARIO PERMANENTEMENTE", type="secondary",
                             use_container_width=True, key=f"delete_btn_{user_id}",
                             disabled=(confirm_del_user.strip().upper() != "ELIMINAR")):
                    try:
                        supabase.table("usuarios").delete().eq("id", user_id).execute()
                        st.cache_data.clear()
                        registrar_accion_critica("ELIMINAR_USUARIO", st.session_state.get('usuario', '?'),
                                                 f"Eliminado: {selected_user['nombre']} (ID: {user_id})")
                        agregar_notificacion('delete', f'Usuario {selected_user["nombre"]} eliminado.')
                        st.rerun()
                    except Exception as e:
                        agregar_notificacion('error', f'Error al eliminar: {e}')
    else:
        st.info("No se encontraron usuarios. Use la pestaña 'CREAR USUARIO'.")


# ==============================================================================
# 🔧 HERRAMIENTAS DE ADMIN
# ==============================================================================
def _render_herramientas():
    st.subheader("Herramientas de Administración")

    # ── Regenerar QRs ──
    st.markdown("#### 🔄 Regenerar Códigos QR")
    st.markdown("""
    Regenera los QR de **todos** los activos con la URL actual del despliegue.
    Útil cuando:
    - La URL de la app cambió
    - Los QRs existentes no funcionan
    - Se migró a otro hosting
    """)

    from utils.qr import BASE_URL_APP
    st.info(f"🌐 **URL actual:** `{BASE_URL_APP}`")

    if st.button("🔄 REGENERAR TODOS LOS QRs", type="primary", use_container_width=True, key="btn_regenerar_qrs"):
        from utils.qr import regenerar_todos_los_qrs
        with st.spinner("Regenerando QRs... Esto puede tomar un momento."):
            exitosos, fallidos, total = regenerar_todos_los_qrs()
        if fallidos == 0:
            st.success(f"✅ {exitosos}/{total} QRs regenerados correctamente.")
            registrar_accion_critica("REGENERAR_QRS", st.session_state.get('usuario', '?'),
                                     f"Regenerados: {exitosos}/{total}")
        else:
            st.warning(f"⚠️ {exitosos}/{total} exitosos, {fallidos} fallidos.")
            registrar_accion_critica("REGENERAR_QRS", st.session_state.get('usuario', '?'),
                                     f"Exitosos: {exitosos}, Fallidos: {fallidos}, Total: {total}")

    st.markdown("---")

    # ── Info del sistema ──
    st.markdown("#### ℹ️ Información del Sistema")
    try:
        from utils.db import supabase
        n_activos = supabase.table("activos").select("id", count="exact").execute().count or 0
        n_ordenes = supabase.table("ordenes").select("id", count="exact").execute().count or 0
        n_usuarios = supabase.table("usuarios").select("id", count="exact").execute().count or 0

        c1, c2, c3 = st.columns(3)
        c1.metric("📦 Activos", n_activos)
        c2.metric("🛠️ Órdenes", n_ordenes)
        c3.metric("👤 Usuarios", n_usuarios)
    except Exception as e:
        st.warning(f"No se pudo cargar la info: {e}")
