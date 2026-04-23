# ==============================================================================
# utils/email_monitor.py — Monitoreo de bandeja Exchange / IMAP
# Descarga correos nuevos y los presenta en el buzón de ORIÓN para aprobación
# ==============================================================================
import streamlit as st
import pandas as pd
import re
import json
from datetime import datetime, timedelta


def _get_exchangelib():
    """Import lazy de exchangelib para no fallar si no está instalado."""
    try:
        from exchangelib import (
            Account, Credentials, Configuration, DELEGATE,
            Message, HTMLBody, FileAttachment
        )
        return Account, Credentials, Configuration, DELEGATE, Message, HTMLBody, FileAttachment
    except ImportError:
        return None, None, None, None, None, None, None


def conectar_exchange():
    """
    Conecta al buzón de Exchange usando credenciales de st.secrets.
    Retorna el Account o None si falla.
    """
    Account, Credentials, Configuration, DELEGATE, *_ = _get_exchangelib()
    if Account is None:
        st.error("❌ `exchangelib` no está instalado. Ejecuta: pip install exchangelib")
        return None

    try:
        cfg = st.secrets.get("exchange", {})
        email = cfg.get("email", "")
        username = cfg.get("username", "")
        password = cfg.get("password", "")
        server = cfg.get("server", "")
        autodiscover = cfg.get("autodiscover", True)

        if not email or not password:
            st.warning("⚠️ Credenciales de Exchange no configuradas en secrets.toml")
            return None

        creds = Credentials(username=username or email, password=password)

        if autodiscover:
            account = Account(
                primary_smtp_address=email,
                credentials=creds,
                autodiscover=True,
                access_type=DELEGATE
            )
        else:
            if not server:
                st.warning("⚠️ 'server' requerido si autodiscover=false")
                return None
            config = Configuration(server=server, credentials=creds)
            account = Account(
                primary_smtp_address=email,
                config=config,
                access_type=DELEGATE
            )

        return account

    except Exception as e:
        st.error(f"❌ Error conectando a Exchange: {type(e).__name__}")
        print(f"[EmailMonitor] Error Exchange: {e}")
        return None


def _parsear_cuerpo(item):
    """Extrae texto plano del cuerpo del correo."""
    if item.text_body:
        return item.text_body.strip()
    if item.body:
        # Limpiar HTML básico
        texto = item.body
        texto = re.sub(r'<style[^>]*>.*?</style>', '', texto, flags=re.DOTALL)
        texto = re.sub(r'<script[^>]*>.*?</script>', '', texto, flags=re.DOTALL)
        texto = re.sub(r'<[^>]+>', ' ', texto)
        texto = re.sub(r'\s+', ' ', texto).strip()
        return texto[:2000]
    return ""


def _extraer_adjuntos(item):
    """Extrae info de adjuntos del correo."""
    adjuntos = []
    if item.attachments:
        for att in item.attachments:
            if hasattr(att, 'name'):
                adjuntos.append({
                    'nombre': att.name,
                    'tipo': att.content_type or 'desconocido',
                    'tamano': att.size if hasattr(att, 'size') else 0
                })
    return adjuntos


def descargar_correos_nuevos(max_correos=20, dias_atras=3):
    """
    Descarga correos nuevos de los últimos N días.
    Retorna lista de dicts con la info de cada correo.
    """
    account = conectar_exchange()
    if not account:
        return []

    try:
        from exchangelib import Q
        ahora = datetime.now()
        desde = ahora - timedelta(days=dias_atras)

        # Buscar en Bandeja de Entrada, no leídos primero, ordenados por fecha
        bandeja = account.inbox
        correos = bandeja.filter(
            datetime_received__gte=desde
        ).order_by('-datetime_received')[:max_correos]

        resultados = []
        for item in correos:
            cuerpo = _parsear_cuerpo(item)
            adjuntos = _extraer_adjuntos(item)

            resultados.append({
                'message_id': item.message_id or str(item.id),
                'remitente': str(item.sender.email_address if item.sender else ''),
                'remitente_nombre': str(item.sender.name if item.sender else ''),
                'asunto': item.subject or '(Sin asunto)',
                'fecha': item.datetime_received.isoformat() if item.datetime_received else '',
                'cuerpo': cuerpo,
                'cuerpo_corto': cuerpo[:200],
                'adjuntos': adjuntos,
                'tiene_adjuntos': len(adjuntos) > 0,
                'leido': item.is_read if hasattr(item, 'is_read') else True,
            })

        return resultados

    except Exception as e:
        st.error(f"❌ Error descargando correos: {type(e).__name__}")
        print(f"[EmailMonitor] Error descargando: {e}")
        return []


def render_buzon_correo():
    """
    Renderiza el buzón de correo en la UI de Streamlit.
    Muestra correos pendientes y permite aprobar/rechazar para crear OT.
    """
    st.markdown("### 📧 Buzón de Correo — Exchange")
    st.caption("Revisa los correos entrantes y decide cuáles se convierten en Órdenes de Trabajo.")

    # ── Configuración en secrets ──
    cfg = st.secrets.get("exchange", {})
    if not cfg.get("email"):
        st.info("ℹ️ Para activar el monitoreo de correo, agrega la configuración de Exchange en `secrets.toml`:")
        st.code("""
[exchange]
email = "jpenagos@p......com.co"
username = "TU_USUARIO"
password = "TU_CONTRASEÑA"
server = "mail.p......com.co"
autodiscover = false
""", language="toml")
        return

    # ── Botón para descargar correos ──
    col_btn, col_info = st.columns([1, 3])
    with col_btn:
        if st.button("🔄 Revisar Correo", type="primary", use_container_width=True):
            with st.spinner("Conectando a Exchange y descargando correos..."):
                correos = descargar_correos_nuevos(max_correos=20, dias_atras=3)
                st.session_state['_correos_pendientes'] = correos
                st.rerun()

    with col_info:
        st.caption("Descarga los correos de los últimos 3 días. Solo se muestran los no procesados.")

    # ── Correos pendientes ──
    correos = st.session_state.get('_correos_pendientes', [])

    if not correos:
        st.info("📭 No hay correos descargados. Haz clic en **Revisar Correo** para buscar nuevos mensajes.")
        return

    # Filtrar ya procesados
    procesados = st.session_state.get('_correos_procesados', set())
    correos_pendientes = [c for c in correos if c['message_id'] not in procesados]

    if not correos_pendientes:
        st.success("✅ Todos los correos han sido procesados.")
        if st.button("🔄 Descargar nuevos"):
            st.session_state.pop('_correos_pendientes', None)
            st.rerun()
        return

    st.markdown(f"#### 📬 {len(correos_pendientes)} correo(s) pendiente(s)")

    for idx, correo in enumerate(correos_pendientes):
        with st.expander(
            f"{'📩' if not correo['leido'] else '📧'} {correo['asunto'][:60]} — {correo['remitente_nombre'] or correo['remitente']}",
            expanded=False
        ):
            # ── Info del correo ──
            st.markdown(f"""
            **De:** {correo['remitente_nombre']} <{correo['remitente']}>  
            **Fecha:** {correo['fecha'][:16]}  
            **Asunto:** {correo['asunto']}  
            **Adjuntos:** {', '.join(a['nombre'] for a in correo['adjuntos']) if correo['adjuntos'] else 'Ninguno'}
            """)

            # ── Cuerpo ──
            with st.expander("📄 Ver contenido del correo"):
                st.text_area(
                    "Contenido", value=correo['cuerpo'][:1000],
                    height=150, disabled=True,
                    key=f"correo_body_{idx}",
                    label_visibility="collapsed"
                )

            st.markdown("---")

            # ── Formulario de aprobación ──
            with st.form(key=f"form_correo_{idx}"):
                st.markdown("**¿Qué hacer con este correo?**")

                accion = st.radio(
                    "Acción",
                    ["✅ Crear Orden de Trabajo", "❌ Descartar (No es mantenimiento)"],
                    key=f"accion_correo_{idx}",
                    horizontal=True
                )

                if accion.startswith("✅"):
                    st.markdown("**Datos para la OT:**")

                    # Cargar activos para el dropdown
                    from utils.db import run_query
                    df_act = run_query("activos")
                    df_users = run_query("usuarios")

                    act_opciones = ["(Seleccionar activo)"]
                    if not df_act.empty:
                        act_opciones += sorted(df_act['nombre'].tolist())
                    act_opciones.append("➕ Crear nuevo activo después")

                    activo_sel = st.selectbox("Activo", act_opciones, key=f"correo_activo_{idx}")

                    c1, c2 = st.columns(2)
                    tipo = c1.selectbox("Tipo", ["Correctivo", "Preventivo", "Predictivo", "Mejora"], key=f"correo_tipo_{idx}")
                    criticidad = c2.select_slider("Criticidad", ["Baja", "Media", "Alta", "Crítica"], value="Media", key=f"correo_crit_{idx}")

                    # Técnico
                    tech_opts = {}
                    if not df_users.empty:
                        tech_opts = {u['nombre']: u['id'] for _, u in df_users.iterrows()}
                    tecnico = st.selectbox("Asignar a", list(tech_opts.keys()), key=f"correo_tecnico_{idx}") if tech_opts else None

                    # Descripción (pre-llenada con el cuerpo del correo)
                    desc_default = f"[Correo de {correo['remitente']}]\n\nAsunto: {correo['asunto']}\n\n{correo['cuerpo_corto']}"
                    descripcion = st.text_area("Descripción", value=desc_default, height=120, key=f"correo_desc_{idx}")

                submitted = st.form_submit_button(
                    "✅ PROCESAR" if accion.startswith("✅") else "🗑️ DESCARTAR",
                    type="primary" if accion.startswith("✅") else "secondary",
                    use_container_width=True
                )

                if submitted:
                    if accion.startswith("✅"):
                        if activo_sel == "(Seleccionar activo)":
                            st.error("Selecciona un activo.")
                        elif not descripcion.strip():
                            st.error("La descripción es obligatoria.")
                        elif not tecnico:
                            st.error("Asigna un técnico.")
                        else:
                            try:
                                from utils.db import db_insert
                                act_id = int(df_act[df_act['nombre'] == activo_sel].iloc[0]['id']) if activo_sel != "➕ Crear nuevo activo después" else None

                                if act_id:
                                    res = db_insert("ordenes", {
                                        "activo_id": act_id,
                                        "descripcion": descripcion.strip(),
                                        "criticidad": criticidad,
                                        "tipo_mantenimiento": tipo,
                                        "estado": "Abierta",
                                        "tecnico_asignado": str(tech_opts[tecnico]),
                                        "fecha_creacion": datetime.now().isoformat()
                                    })
                                    if res.data:
                                        nuevo_id = res.data[0]['id']
                                        # Registrar en bitácora
                                        db_insert("bitacora", {
                                            "orden_id": nuevo_id,
                                            "usuario_text": "CORREO (automático)",
                                            "mensaje": f"📧 Creada desde correo de {correo['remitente']}\nAsunto: {correo['asunto']}",
                                            "fecha": datetime.now().isoformat()
                                        })
                                        # Marcar como procesado
                                        procesados.add(correo['message_id'])
                                        st.session_state['_correos_procesados'] = procesados
                                        st.success(f"✅ Orden #{nuevo_id} creada desde correo.")
                                        st.rerun()
                                else:
                                    st.warning("⚠️ Selecciona 'Crear nuevo activo después' y crea el activo primero en el módulo de Inventario.")
                            except Exception as e:
                                st.error(f"Error creando orden: {e}")
                    else:
                        # Descartar
                        procesados.add(correo['message_id'])
                        st.session_state['_correos_procesados'] = procesados
                        st.toast("🗑️ Correo descartado.")
                        st.rerun()

    # ── Estadísticas ──
    st.markdown("---")
    total_proc = len(procesados)
    total_pend = len(correos_pendientes)
    col1, col2, col3 = st.columns(3)
    col1.metric("📬 Descargados", len(correos))
    col2.metric("⏳ Pendientes", total_pend)
    col3.metric("✅ Procesados", total_proc)
