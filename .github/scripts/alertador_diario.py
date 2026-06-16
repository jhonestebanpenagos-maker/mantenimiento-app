# alertador_diario.py
# Se ejecuta cada 24h via GitHub Actions
# Alerta sobre solicitudes y correos sin gestionar >48h

import os
import sys
import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta
import requests

# =====================================================
# CONFIGURACIÓN
# =====================================================
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GMAIL_CORREO = os.environ.get("GMAIL_CORREO")
GMAIL_PASSWORD = os.environ.get("GMAIL_PASSWORD")

UMBRAL_HORAS = 48  # Alertar después de 48 horas

# Validación de credenciales
errores = []
if not SUPABASE_URL:
    errores.append("SUPABASE_URL")
if not SUPABASE_KEY:
    errores.append("SUPABASE_KEY")
if not TELEGRAM_TOKEN:
    errores.append("TELEGRAM_TOKEN")

if errores:
    print(f"❌ Faltan variables de entorno: {', '.join(errores)}")
    sys.exit(1)

# =====================================================
# CONEXIÓN A SUPABASE
# =====================================================
from supabase import create_client

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# =====================================================
# FUNCIONES TELEGRAM
# =====================================================
def enviar_telegram(chat_id, mensaje):
    """Envía mensaje por Telegram."""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        resp = requests.post(url, json={
            "chat_id": chat_id,
            "text": mensaje,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }, timeout=15)
        if resp.status_code == 200:
            print(f"  ✅ Enviado a chat_id={chat_id}")
            return True
        else:
            print(f"  ⚠️ Error Telegram {resp.status_code}: {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"  ❌ Error enviando Telegram: {e}")
        return False


def obtener_admins():
    """Obtiene admins con chat_id de Telegram configurado."""
    try:
        res = supabase.table("usuarios").select("nombre, chat_id, rol").execute()
        admins = [
            u for u in (res.data or [])
            if u.get("rol") == "Admin" and u.get("chat_id")
        ]
        return admins
    except Exception as e:
        print(f"❌ Error obteniendo admins: {e}")
        return []


# =====================================================
# 1. SOLICITUDES ANTIGUAS (>48h)
# =====================================================
def revisar_solicitudes():
    """Consulta solicitudes pendientes con más de 48 horas."""
    print("\n📥 Revisando solicitudes pendientes...")
    try:
        res = supabase.table("solicitudes").select("*").eq("estado", "Pendiente").execute()
        todas = res.data or []
        print(f"  Total pendientes: {len(todas)}")

        umbral = datetime.now() - timedelta(hours=UMBRAL_HORAS)
        antiguas = []

        for sol in todas:
            fecha_str = sol.get("fecha_solicitud") or sol.get("fecha_creacion") or ""
            if not fecha_str:
                continue
            try:
                fecha = datetime.fromisoformat(fecha_str.replace("Z", "+00:00").replace("+00:00", ""))
            except Exception:
                try:
                    fecha = datetime.fromisoformat(fecha_str[:19])
                except Exception:
                    continue

            if fecha < umbral:
                horas = (datetime.now() - fecha).total_seconds() / 3600
                sol["_horas"] = horas
                sol["_dias"] = int(horas / 24)
                antiguas.append(sol)

        print(f"  Antiguas (>48h): {len(antiguas)}")
        return antiguas

    except Exception as e:
        print(f"❌ Error consultando solicitudes: {e}")
        return []


# =====================================================
# 2. CORREOS EN LIMBO (>48h sin gestionar)
# =====================================================
def _decodificar_header(header_val):
    if not header_val:
        return ""
    partes = decode_header(header_val)
    resultado = []
    for parte, charset in partes:
        if isinstance(parte, bytes):
            resultado.append(parte.decode(charset or 'utf-8', errors='replace'))
        else:
            resultado.append(str(parte))
    return ' '.join(resultado)


def _parsear_fecha(date_str):
    if not date_str:
        return None
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        return None


def revisar_correos_limbo():
    """Compara Gmail vs emails_procesados para encontrar correos en limbo >48h."""
    print("\n📧 Revisando correos en limbo...")

    if not GMAIL_CORREO or not GMAIL_PASSWORD:
        print("  ⚠️ Credenciales de Gmail no configuradas. Saltando revisión de correos.")
        return []

    # 1. Obtener message_ids ya procesados
    try:
        res = supabase.table("emails_procesados").select("message_id").execute()
        procesados = {row["message_id"].strip() for row in (res.data or []) if row.get("message_id")}
        print(f"  Procesados en BD: {len(procesados)}")
    except Exception as e:
        print(f"  ⚠️ Error consultando procesados: {e}")
        procesados = set()

    # 2. También obtener pendientes guardados (ya están en el radar)
    try:
        res_pend = supabase.table("emails_pendientes").select("message_id").execute()
        en_pendientes = {row["message_id"].strip() for row in (res_pend.data or []) if row.get("message_id")}
        print(f"  Pendientes en BD: {len(en_pendientes)}")
    except Exception:
        en_pendientes = set()

    # 3. Conectar a Gmail y descargar headers de últimos 7 días
    try:
        import socket
        socket.setdefaulttimeout(30)
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.socket().settimeout(30)
        mail.login(GMAIL_CORREO, GMAIL_PASSWORD)
        mail.select("INBOX")
    except Exception as e:
        print(f"  ❌ Error conectando a Gmail: {e}")
        return []

    # Buscar correos de los últimos 7 días
    fecha_desde = (datetime.now() - timedelta(days=7)).strftime("%d-%b-%Y")
    try:
        status, mensajes = mail.search(None, f'(SINCE "{fecha_desde}")')
        if status != "OK":
            print("  ⚠️ Error buscando correos en Gmail")
            mail.logout()
            return []

        ids = mensajes[0].split()
        print(f"  Correos en Gmail (últimos 7 días): {len(ids)}")
    except Exception as e:
        print(f"  ❌ Error buscando: {e}")
        mail.logout()
        return []

    # 4. Descargar headers y filtrar
    umbral = datetime.now() - timedelta(hours=UMBRAL_HORAS)
    en_limbo = []

    for msg_id in ids[-100:]:  # Últimos 100 como máximo
        try:
            status, datos = mail.fetch(msg_id, "(BODY.PEEK[HEADER])")
            if status != "OK" or not datos[0]:
                continue

            raw_header = datos[0][1]
            msg = email.message_from_bytes(raw_header)

            message_id = (msg.get("Message-ID") or "").strip()
            if not message_id:
                continue

            # Saltar si ya fue procesado o está pendiente
            if message_id in procesados or message_id in en_pendientes:
                continue

            # Verificar fecha
            fecha_dt = _parsear_fecha(msg.get("Date"))
            if not fecha_dt:
                continue

            # Solo alertar si >48h
            if fecha_dt > umbral:
                continue

            # ¡Está en limbo!
            horas = (datetime.now() - fecha_dt).total_seconds() / 3600
            en_limbo.append({
                "message_id": message_id,
                "remitente": _decodificar_header(msg.get("From", "")),
                "asunto": _decodificar_header(msg.get("Subject", "")),
                "fecha": fecha_dt.isoformat(),
                "horas": horas,
                "dias": int(horas / 24),
            })

        except Exception as e:
            continue

    mail.logout()
    print(f"  Correos en limbo (>48h): {len(en_limbo)}")
    return en_limbo


# =====================================================
# 3. CONSTRUIR Y ENVIAR ALERTA
# =====================================================
def construir_mensaje(solicitudes, correos):
    """Construye el mensaje de alerta para Telegram."""
    lineas = []
    lineas.append("🚨 *ORIÓN — Alerta diaria de items sin gestionar*")
    lineas.append(f"_{datetime.now().strftime('%d/%m/%Y %H:%M')}_")
    lineas.append("━" * 30)

    # Solicitudes
    if solicitudes:
        lineas.append("")
        lineas.append(f"📥 *SOLICITUDES SIN ATENDER ({len(solicitudes)}):*")
        for sol in solicitudes[:10]:  # Máximo 10
            desc = (sol.get("descripcion") or "Sin descripción")[:50]
            solicitante = sol.get("solicitante_id", "Desconocido")
            dias = sol.get("_dias", "?")
            lineas.append(f"• #{sol['id']} — {solicitante} — _{desc}_ — *{dias} días*")
        if len(solicitudes) > 10:
            lineas.append(f"  _...y {len(solicitudes) - 10} más_")

    # Correos en limbo
    if correos:
        lineas.append("")
        lineas.append(f"📧 *CORREOS EN LIMBO ({len(correos)}):*")
        for corr in correos[:10]:  # Máximo 10
            asunto = (corr.get("asunto") or "Sin asunto")[:50]
            remitente = (corr.get("remitente") or "Desconocido")[:30]
            dias = corr.get("dias", "?")
            lineas.append(f"• _{asunto}_ — {remitente} — *{dias} días*")
        if len(correos) > 10:
            lineas.append(f"  _...y {len(correos) - 10} más_")

    if not solicitudes and not correos:
        return None  # No hay nada que alertar

    lineas.append("")
    lineas.append("━" * 30)
    lineas.append("👉 *Gestiona en ORIÓN:*")
    lineas.append("")
    if solicitudes:
        lineas.append("📥 *Solicitudes:* https://mantenimiento-app-fv9et6lbtpzrpbgjecqjfe.streamlit.app?go=buzon")
    if correos:
        lineas.append("📧 *Correos:* https://mantenimiento-app-fv9et6lbtpzrpbgjecqjfe.streamlit.app?go=correo")

    return "\n".join(lineas)


def marcar_alertados(solicitudes, correos):
    """Marca items como alertados para no repetir en la próxima ejecución."""
    for sol in solicitudes:
        try:
            supabase.table("alertas_enviadas").upsert({
                "tipo": "solicitud",
                "item_id": str(sol["id"]),
                "alertado_en": datetime.now().isoformat(),
            }).execute()
        except Exception:
            pass

    for corr in correos:
        try:
            supabase.table("alertas_enviadas").upsert({
                "tipo": "correo",
                "item_id": corr["message_id"],
                "alertado_en": datetime.now().isoformat(),
            }).execute()
        except Exception:
            pass


def filtrar_ya_alertados(solicitudes, correos):
    """Filtra items que ya fueron alertados en ejecuciones anteriores."""
    try:
        res = supabase.table("alertas_enviadas").select("tipo, item_id").execute()
        alertados = set()
        for row in (res.data or []):
            alertados.add(f"{row['tipo']}:{row['item_id']}")
    except Exception:
        return solicitudes, correos

    sol_filtradas = [s for s in solicitudes if f"solicitud:{s['id']}" not in alertados]
    corr_filtrados = [c for c in correos if f"correo:{c['message_id']}" not in alertados]

    print(f"  Ya alertados anteriormente: {len(solicitudes) - len(sol_filtradas)} solicitudes, {len(correos) - len(corr_filtrados)} correos")
    return sol_filtradas, corr_filtrados


# =====================================================
# MAIN
# =====================================================
def main():
    print("=" * 50)
    print("🔔 ORIÓN — Alertador Diario")
    print(f"   Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"   Umbral: {UMBRAL_HORAS} horas")
    print("=" * 50)

    # 1. Revisar solicitudes antiguas
    solicitudes = revisar_solicitudes()

    # 2. Revisar correos en limbo
    correos = revisar_correos_limbo()

    # 3. Filtrar los que ya fueron alertados
    solicitudes, correos = filtrar_ya_alertados(solicitudes, correos)

    # 4. Construir mensaje
    mensaje = construir_mensaje(solicitudes, correos)

    if not mensaje:
        print("\n✅ Todo al día. No hay nada que alertar.")
        return

    # 5. Obtener admins y enviar
    admins = obtener_admins()
    if not admins:
        print("\n⚠️ No hay admins con chat_id configurado. No se envían alertas.")
        print("\n📋 Mensaje que se habría enviado:")
        print(mensaje)
        return

    print(f"\n📤 Enviando alerta a {len(admins)} admin(s)...")
    enviados = 0
    for admin in admins:
        if enviar_telegram(admin["chat_id"], mensaje):
            enviados += 1

    # 6. Marcar como alertados
    if enviados > 0:
        marcar_alertados(solicitudes, correos)
        print(f"\n✅ Alerta enviada a {enviados} admin(s). Items marcados como alertados.")
    else:
        print("\n❌ No se pudo enviar la alerta a ningún admin.")


if __name__ == "__main__":
    main()
