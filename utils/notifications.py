import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime


# ==============================================================================
# 🔔 FUNCIÓN TELEGRAM
# ==============================================================================
def notificar_telegram(chat_id, mensaje, foto_url=None):
    if not chat_id:
        print("⚠️ notificar_telegram: chat_id vacío, no se envía.")
        return False
    try:
        # Buscar token: primero env var, luego secrets.toml
        import os
        token = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_TOKEN")
        if not token:
            try:
                token_raw = st.secrets["telegram"]["bot_token"]
                token = token_raw.split("/bot")[-1].split("/")[0] if "/bot" in token_raw else token_raw
            except (KeyError, FileNotFoundError):
                pass
        if not token:
            print("❌ notificar_telegram: Token de Telegram no configurado (ni env var ni secrets.toml)")
            return False

        base_url = f"https://api.telegram.org/bot{token}"
        payload = {"chat_id": chat_id, "parse_mode": "Markdown"}
        if foto_url:
            payload["caption"] = mensaje
            payload["photo"] = foto_url
            url_envio = f"{base_url}/sendPhoto"
        else:
            payload["text"] = mensaje
            url_envio = f"{base_url}/sendMessage"
        resp = requests.post(url_envio, data=payload, timeout=10)
        if resp.status_code != 200:
            print(f"⚠️ Telegram API status {resp.status_code}: {resp.text[:200]}")
            return False
        print(f"✅ Telegram enviado a chat_id={chat_id}")
        return True
    except Exception as e:
        print(f"❌ Error Telegram: {type(e).__name__}: {e}")
        return False


# ==============================================================================
# ⏱️ MOTOR DE ALERTAS SLA
# ==============================================================================
# Throttle a nivel de proceso (no por sesión): iOS/Safari recarga la pestaña al
# volver de segundo plano y crea una sesión nueva de Streamlit cada vez; sin este
# control, el chequeo SLA + envíos de Telegram se repetían en cada recarga y
# bloqueaban el render del tablero durante varios segundos.
_ULTIMO_CHECK_SLA_TS = 0.0
SLA_CHECK_INTERVALO_SEG = 600   # como máximo 1 chequeo cada 10 minutos por proceso
SLA_MAX_NOTIFICACIONES = 10     # tope de envíos de Telegram por chequeo


def verificar_sla_y_alertar(df_ordenes, df_users, df_act):
    global _ULTIMO_CHECK_SLA_TS
    if st.session_state.get('sla_verificado'):
        return

    # Si ya se revisó hace poco (en este proceso), no repetir el trabajo pesado
    if time.time() - _ULTIMO_CHECK_SLA_TS < SLA_CHECK_INTERVALO_SEG:
        st.session_state['sla_verificado'] = True
        return
    _ULTIMO_CHECK_SLA_TS = time.time()

    df_ordenes = pd.DataFrame(df_ordenes) if not isinstance(df_ordenes, pd.DataFrame) else df_ordenes
    df_users = pd.DataFrame(df_users) if not isinstance(df_users, pd.DataFrame) else df_users
    df_act = pd.DataFrame(df_act) if not isinstance(df_act, pd.DataFrame) else df_act

    LIMITES_SLA = {"Crítica": 4, "Alta": 24, "Media": 72, "Baja": 168}

    if df_ordenes.empty:
        st.session_state['sla_verificado'] = True
        return

    ahora = datetime.now()
    df_abiertas = df_ordenes[df_ordenes['estado'] == 'Abierta'].copy() \
        if 'estado' in df_ordenes.columns else pd.DataFrame()

    if df_abiertas.empty:
        st.session_state['sla_verificado'] = True
        return

    df_abiertas['fecha_dt'] = pd.to_datetime(df_abiertas['fecha_creacion'])
    df_abiertas['horas_abiertas'] = (ahora - df_abiertas['fecha_dt']).dt.total_seconds() / 3600

    map_act = dict(zip(df_act['id'], df_act['nombre'])) if not df_act.empty else {}
    map_user = dict(zip(df_users['id'].astype(str), df_users['nombre'])) if not df_users.empty else {}

    alertas_enviadas = 0
    notificaciones_enviadas = 0
    for _, orden in df_abiertas.iterrows():
        limite = LIMITES_SLA.get(orden['criticidad'], 999)
        if orden['horas_abiertas'] > limite:
            nombre_activo = map_act.get(orden['activo_id'], "Desconocido")
            nombre_tecnico = map_user.get(str(orden['tecnico_asignado']), "Sin asignar")
            horas_str = f"{orden['horas_abiertas']:.0f}h"
            mensaje = (
                f"🚨 *ALERTA SLA — OT #{orden['id']}*\n\n"
                f"📍 *Activo:* {nombre_activo}\n"
                f"🔴 *Criticidad:* {orden['criticidad']}\n"
                f"⏱️ *Tiempo abierta:* {horas_str} (límite: {limite}h)\n"
                f"👷 *Técnico:* {nombre_tecnico}\n\n"
                f"⚠️ Esta orden requiere atención inmediata."
            )
            if orden.get('chat_id') and notificaciones_enviadas < SLA_MAX_NOTIFICACIONES:
                notificar_telegram(orden.get('chat_id'), mensaje)
                notificaciones_enviadas += 1
            alertas_enviadas += 1

    if alertas_enviadas > 0:
        st.session_state['sla_alertas_count'] = alertas_enviadas
    st.session_state['sla_verificado'] = True
