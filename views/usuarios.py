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
    st.title("DIRECTORIO Y USUARIOS")
    render_back_button()
    mostrar_notificaciones()

    rol = st.session_state.get('rol', '')

    if rol == 'Admin':
        tab_crear, tab_gestionar, tab_herramientas = st.tabs(["➕ NUEVO REGISTRO", "✏️ GESTIONAR", "🔧 HERRAMIENTAS"])
    else:
        tab_crear, tab_gestionar = st.tabs(["➕ NUEVO REGISTRO", "✏️ GESTIONAR"])
        tab_herramientas = None

    with tab_crear:
        _render_crear()

    with tab_gestionar:
        _render_gestionar()

    if tab_herramientas is not None:
        with tab_herramientas:
            _render_herramientas()


# ==============================================================================
# ➕ CREAR USUARIO O EMPRESA (INTERRUPTOR INTELIGENTE)
# ==============================================================================
def _render_crear():
    st.subheader("Registrar en el Sistema")
    
    # 🔥 INTERRUPTOR DE MODO
    tipo_registro = st.radio(
        "¿Qué tipo de perfil deseas registrar?", 
        ["👤 Personal Interno (Tendrán acceso al sistema)", "🏢 Empresa Contratista / Tercero (Solo para asignar OTs, sin acceso)"],
        horizontal=False
    )
    
    st.markdown("---")

    with st.form("new_user_form"):
        es_interno = "Interno" in tipo_registro
        
        if es_interno:
            c1, c2 = st.columns(2)
            documento = c1.text_input("Documento/ID", key="new_user_doc")
            nombre = c2.text_input("Nombre Completo", key="new_user_name")
            password = c1.text_input("Contraseña para el sistema", type="password", key="new_user_pass")
            rol = c2.selectbox("Permisos en el Sistema", ["Tecnico", "Programador", "Admin"], key="new_user_rol")
            
            c3, c4 = st.columns(2)
            tipo_personal = c3.selectbox("Rol Operativo", ["Técnico Interno", "Administrador"], key="new_user_tipo")
            estado_disp = c4.selectbox("Estado de Disponibilidad", ["Activo", "Vacaciones", "Incapacitado", "Permiso Especial"], key="new_user_estado")
            
            st.caption(f"🔒 Contraseña: Mínimo {PASSWORD_MIN_LENGTH} caracteres, mayúscula, minúscula y número.")
        
        else:
            # MODO EMPRESA
            st.info("💡 Las empresas contratistas no tienen contraseña ni acceso al sistema, solo sirven para que puedas asignarles trabajos en la Torre de Control.")
            c1, c2 = st.columns(2)
            documento = c1.text_input("NIT / RUT (Identificación)", key="new_emp_doc")
            nombre = c2.text_input("Razón Social (Nombre de la Empresa)", key="new_emp_name")
            estado_disp = st.selectbox("Estado del Contratista", ["Activo", "Inactivo / Suspendido"], key="new_emp_estado")
            
            # Datos ocultos que el sistema necesita pero el admin no debe llenar
            password = "Contratista_12345!" 
            rol = "Tecnico"
            tipo_personal = "Contratista Externo"

        st.markdown("<br>", unsafe_allow_html=True)
        submitted = st.form_submit_button("💾 GUARDAR REGISTRO", type="primary", use_container_width=True)

        if submitted:
            if documento and nombre and password:
                if not validar_usuario_unico(documento):
                    agregar_notificacion('error', 'Ese Documento/NIT ya está registrado.')
                else:
                    if es_interno:
                        pass_valida, pass_error = validar_politica_password(password)
                        if not pass_valida:
                            agregar_notificacion('error', pass_error)
                            st.stop()
                    else:
                        pass_valida = True
                    
                    if pass_valida:
                        try:
                            res = supabase.table("usuarios").insert({
                                "documento": documento, 
                                "nombre": nombre,
                                "password": hashear_password(password), 
                                "rol": rol,
                                "tipo_personal": tipo_personal,
                                "estado_disponibilidad": estado_disp
                            }).execute()
                            if res.data:
                                st.cache_data.clear()
                                registrar_accion_critica("CREAR_REGISTRO", documento, f"Nombre: {nombre}, Tipo: {tipo_personal}")
                                agregar_notificacion('success', f'{nombre} registrado con éxito.')
                                st.rerun()
                            else:
                                agregar_notificacion('error', 'Error al registrar en BD.')
                        except Exception as e:
                            agregar_notificacion('error', f'Error de BD: {e}')
            else:
                agregar_notificacion('warning', 'Complete todos los campos obligatorios.')


# ==============================================================================
# ✏️ GESTIONAR USUARIOS / EMPRESAS
# ==============================================================================
def _render_gestionar():
    df_users = run_query("usuarios")
    if not df_users.empty:
        st.subheader("Seleccionar Registro para Gestionar")
        
        # Le agregamos un emoji al nombre dependiendo de si es empresa o interno
        opciones = {}
        for _, row in df_users.iterrows():
            icono = "🏢" if row.get('tipo_personal') == 'Contratista Externo' else "👤"
            opciones[f"{icono} {row['nombre']} (ID: {row['id']})"] = row['id']
            
        user_options_list = ["-- Seleccione --"] + list(opciones.keys())
        selected_option = st.selectbox("Buscar por nombre:", user_options_list, key="user_selector")

        st.markdown("### Directorio Completo")
        cols_to_show = ['documento', 'nombre', 'tipo_personal', 'estado_disponibilidad']
        st.dataframe(df_users[cols_to_show], hide_index=True, use_container_width=True)

        if selected_option != "-- Seleccione --":
            user_id = opciones[selected_option]
            selected_user = df_users[df_users['id'] == user_id].iloc[0]
            es_contratista = selected_user.get('tipo_personal') == 'Contratista Externo'

            st.markdown("---")
            st.markdown(f"### Editando: **{selected_user['nombre']}**")

            with st.form(key=f"edit_user_form_{user_id}"):
                c1, c2 = st.columns(2)
                
                if es_contratista:
                    edit_doc = c1.text_input("NIT / RUT", value=selected_user['documento'])
                    edit_name = c2.text_input("Razón Social", value=selected_user['nombre'])
                    
                    estado_options = ["Activo", "Inactivo / Suspendido"]
                    curr_estado = selected_user.get('estado_disponibilidad', 'Activo')
                    if pd.isna(curr_estado) or curr_estado not in estado_options: curr_estado = 'Activo'
                    new_estado = st.selectbox("Estado del Contratista", estado_options, index=estado_options.index(curr_estado))
                    
                    # Ocultos
                    new_rol = selected_user['rol']
                    new_tipo = "Contratista Externo"
                    new_password = ""
                else:
                    edit_doc = c1.text_input("Documento/ID", value=selected_user['documento'])
                    edit_name = c2.text_input("Nombre Completo", value=selected_user['nombre'])
                    
                    rol_options = ["Tecnico", "Programador", "Admin"]
                    current_rol_index = rol_options.index(selected_user['rol']) if selected_user['rol'] in rol_options else 0
                    new_rol = c1.selectbox("Permisos en el Sistema", rol_options, index=current_rol_index)
                    
                    new_password = c2.text_input("Nueva Contraseña (Vacío = no cambiar)", type="password")
                    
                    tipo_options = ["Técnico Interno", "Administrador"]
                    curr_tipo_val = selected_user.get('tipo_personal', 'Técnico Interno')
                    if pd.isna(curr_tipo_val) or curr_tipo_val not in tipo_options: curr_tipo_val = "Técnico Interno"
                    new_tipo = c1.selectbox("Rol Operativo", tipo_options, index=tipo_options.index(curr_tipo_val))

                    estado_options = ["Activo", "Vacaciones", "Incapacitado", "Permiso Especial"]
                    curr_estado_val = selected_user.get('estado_disponibilidad', 'Activo')
                    if pd.isna(curr_estado_val) or curr_estado_val not in estado_options: curr_estado_val = 'Activo'
                    new_estado = c2.selectbox("Estado de Disponibilidad", estado_options, index=estado_options.index(curr_estado_val))

                    if new_password:
                        st.caption(f"🔒 Mínimo {PASSWORD_MIN_LENGTH} caracteres, mayúscula, minúscula y número.")
                
                st.markdown("<br>", unsafe_allow_html=True)
                update_submitted = st.form_submit_button("✅ ACTUALIZAR", type="primary", use_container_width=True)

                if update_submitted:
                    if new_rol != selected_user['rol']:
                        if check_open_orders(user_id):
                            agregar_notificacion('error', f'**{selected_user["nombre"]}** tiene OTs pendientes. Ciérrelas antes de cambiar su rol de sistema.')
                            st.stop()
                    if not validar_usuario_unico(edit_doc, user_id):
                        agregar_notificacion('error', 'El documento o NIT ya está en uso por otro registro.')
                    else:
                        update_data = {
                            "documento": edit_doc, 
                            "nombre": edit_name, 
                            "rol": new_rol,
                            "tipo_personal": new_tipo,
                            "estado_disponibilidad": new_estado
                        }
                        cambios = []
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
                            registrar_accion_critica("ACTUALIZAR_REGISTRO", st.session_state.get('usuario', '?'), f"Registro: {edit_name}")
                            agregar_notificacion('success', f'{edit_name} actualizado correctamente.')
                            st.rerun()
                        except Exception as e:
                            agregar_notificacion('error', f'Error al actualizar: {e}')

            st.markdown("---")
            st.markdown("### 🗑️ Zona de Eliminación")
            if check_open_orders(user_id):
                st.markdown(f"""
                    <div style='background:rgba(239,68,68,0.15);border:2px solid #EF4444;border-radius:8px;padding:20px;text-align:center;'>
                        <p style='color:#FCA5A5;margin:0;font-size:1.1rem;'>⚠️ <strong>ELIMINACIÓN BLOQUEADA</strong></p>
                        <p style='color:#FEE2E2;margin-top:10px;font-size:0.95rem;'><strong>{selected_user['nombre']}</strong> tiene Órdenes de Trabajo pendientes.</p>
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.warning(f"⚠️ Eliminar permanentemente a **{selected_user['nombre']}**")
                confirm_del_user = st.text_input("Escriba ELIMINAR para confirmar", key=f"confirm_del_user_{user_id}", placeholder="ELIMINAR")
                if st.button("🗑️ ELIMINAR PERMANENTEMENTE", type="secondary",
                             use_container_width=True, key=f"delete_btn_{user_id}",
                             disabled=(confirm_del_user.strip().upper() != "ELIMINAR")):
                    try:
                        supabase.table("usuarios").delete().eq("id", user_id).execute()
                        st.cache_data.clear()
                        registrar_accion_critica("ELIMINAR_REGISTRO", st.session_state.get('usuario', '?'), f"Eliminado: {selected_user['nombre']}")
                        agregar_notificacion('delete', f'{selected_user["nombre"]} eliminado.')
                        st.rerun()
                    except Exception as e:
                        agregar_notificacion('error', f'Error al eliminar: {e}')
    else:
        st.info("El directorio está vacío. Use la pestaña 'NUEVO REGISTRO'.")


# ==============================================================================
# 🔧 HERRAMIENTAS DE ADMIN
# ==============================================================================
def _render_herramientas():
    st.subheader("Herramientas de Administración")

    st.markdown("#### 🔄 Regenerar Códigos QR")
    st.markdown("""
    Regenera los QR de **todos** los activos con la URL actual del despliegue.
    """)

    from utils.qr import BASE_URL_APP
    st.info(f"🌐 **URL actual:** `{BASE_URL_APP}`")

    if st.button("🔄 REGENERAR TODOS LOS QRs", type="primary", use_container_width=True, key="btn_regenerar_qrs"):
        from utils.qr import regenerar_todos_los_qrs
        with st.spinner("Regenerando QRs... Esto puede tomar un momento."):
            exitosos, fallidos, total = regenerar_todos_los_qrs()
        if fallidos == 0:
            st.success(f"✅ {exitosos}/{total} QRs regenerados correctamente.")
        else:
            st.warning(f"⚠️ {exitosos}/{total} exitosos, {fallidos} fallidos.")

    st.markdown("---")

    st.markdown("#### 📧 Migrar Correos Antiguos")
    st.markdown("""
    Si tienes correos anexados a órdenes que se ven como "📧 Correo adjunto" sin
    poder ver el contenido, este botón los actualiza al nuevo formato.
    """)

    col_mig1, col_mig2 = st.columns(2)
    with col_mig1:
        if st.button("🔍 Verificar correos pendientes", type="secondary", use_container_width=True, key="btn_verificar_migracion"):
            from utils.migrate_emails import ejecutar_migracion
            with st.spinner("Analizando bitácora..."):
                n_migrados, n_total, errores = ejecutar_migracion(solo_verificar=True)
            if n_total == 0:
                st.success("✅ No hay correos pendientes de migrar.")
            else:
                st.warning(f"📋 {n_total} correo(s) pendiente(s) de migrar.")

    with col_mig2:
        if st.button("🔄 Migrar correos ahora", type="primary", use_container_width=True, key="btn_ejecutar_migracion"):
            from utils.migrate_emails import ejecutar_migracion
            with st.spinner("Migrando correos..."):
                n_migrados, n_total, errores = ejecutar_migracion(solo_verificar=False)
            if n_migrados > 0:
                st.success(f"✅ {n_migrados}/{n_total} correo(s) migrado(s) correctamente.")
                st.rerun()
            elif n_total == 0:
                st.success("✅ No hay correos pendientes de migrar.")
            else:
                st.error(f"❌ Hubo {len(errores)} error(es).")

    # ── Migración individual ──
    st.markdown("**🎯 Migrar una orden específica:**")
    orden_id_mig = st.number_input("ID de Orden", min_value=1, step=1, key="migrar_orden_id_herramientas")
    if st.button("Migrar solo esta orden", use_container_width=True, key="btn_migrar_orden_individual"):
        from utils.migrate_emails import ejecutar_migracion
        with st.spinner(f"Migrando Orden #{orden_id_mig}..."):
            n_migrados, n_total, errores = ejecutar_migracion(orden_id=int(orden_id_mig), solo_verificar=False)
        if n_migrados > 0:
            st.success(f"✅ Orden #{orden_id_mig}: {n_migrados} correo(s) migrado(s).")
        elif n_total == 0:
            st.info(f"ℹ️ Orden #{orden_id_mig}: No hay correos pendientes.")
        else:
            st.error(f"❌ Orden #{orden_id_mig}: {len(errores)} error(es).")

    st.markdown("---")

    st.markdown("#### ℹ️ Información del Sistema")
    try:
        from utils.db import supabase
        n_activos = supabase.table("activos").select("id", count="exact").execute().count or 0
        n_ordenes = supabase.table("ordenes").select("id", count="exact").execute().count or 0
        n_usuarios = supabase.table("usuarios").select("id", count="exact").execute().count or 0

        c1, c2, c3 = st.columns(3)
        c1.metric("📦 Activos", n_activos)
        c2.metric("🛠️ Órdenes", n_ordenes)
        c3.metric("👥 Directorio (Pers/Emp)", n_usuarios)
    except Exception as e:
        st.warning(f"No se pudo cargar la info: {e}")
