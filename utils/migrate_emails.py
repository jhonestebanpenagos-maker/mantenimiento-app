# utils/migrate_emails.py
# ==============================================================================
# Script de migración: Actualiza entradas antiguas de bitácora con correos
# al nuevo formato estructurado [📧 CORREO]...[/📧 CORREO]
#
# Ejecución:
#   streamlit run utils/migrate_emails.py
#   O desde la consola: python -c "from utils.migrate_emails import ejecutar_migracion; ejecutar_migracion()"
# ==============================================================================

import streamlit as st
import io
import re
from datetime import datetime
from utils.db import supabase, db_update


def _normalizar_fecha_correo(fecha_raw) -> str:
    """Convierte cualquier fecha de correo a ISO 8601."""
    if not fecha_raw:
        return ''
    if isinstance(fecha_raw, str):
        fecha_str = fecha_raw.strip()
        if fecha_str and fecha_str[0].isdigit():
            return fecha_str[:19]
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(fecha_str)
            return dt.strftime('%Y-%m-%dT%H:%M:%S')
        except Exception:
            pass
    if isinstance(fecha_raw, datetime):
        return fecha_raw.strftime('%Y-%m-%dT%H:%M:%S')
    return ''


def _parsear_msg_desde_url(url: str) -> dict | None:
    """
    Descarga un archivo .msg/.eml desde una URL y lo parsea.
    Retorna dict con: remitente, asunto, fecha, cuerpo
    """
    if not url:
        return None

    try:
        import requests
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            return None

        bytes_data = resp.content
        url_lower = url.lower()

        if url_lower.endswith('.msg'):
            import extract_msg
            msg = extract_msg.Message(io.BytesIO(bytes_data))
            remitente = msg.sender or 'Desconocido'
            asunto = msg.subject or '(Sin asunto)'
            fecha = msg.date or ''
            cuerpo = msg.body or ''
            # Limpiar cuerpo
            cuerpo = _limpiar_cuerpo(cuerpo)
            return {
                'remitente': remitente,
                'asunto': asunto,
                'fecha': _normalizar_fecha_correo(fecha),
                'cuerpo': cuerpo,
            }

        elif url_lower.endswith('.eml'):
            import email
            import email.policy
            msg = email.message_from_bytes(bytes_data, policy=email.policy.default)
            remitente = msg['from'] or 'Desconocido'
            asunto = msg['subject'] or '(Sin asunto)'
            fecha = msg['date'] or ''

            cuerpo = ''
            if msg.is_multipart():
                for part in msg.walk():
                    ctype = part.get_content_type()
                    if ctype == 'text/plain':
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or 'utf-8'
                            cuerpo = payload.decode(charset, errors='replace')
                        break
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    charset = msg.get_content_charset() or 'utf-8'
                    cuerpo = payload.decode(charset, errors='replace')

            cuerpo = _limpiar_cuerpo(cuerpo)
            return {
                'remitente': remitente,
                'asunto': asunto,
                'fecha': _normalizar_fecha_correo(fecha),
                'cuerpo': cuerpo,
            }

    except Exception as e:
        print(f"⚠️ Error parseando correo desde URL: {e}")
        return None


def _limpiar_cuerpo(cuerpo: str) -> str:
    """Limpia el cuerpo del correo."""
    if not cuerpo:
        return ''
    # Quitar líneas de firma
    lineas = cuerpo.split('\n')
    limpias = []
    en_firma = False
    for linea in lineas:
        if linea.strip().startswith('-- ') or linea.strip() == '--':
            en_firma = True
        if not en_firma:
            limpias.append(linea)
    resultado = '\n'.join(limpias).strip()
    # Limitar a 500 chars
    if len(resultado) > 500:
        resultado = resultado[:500] + '... [truncado]'
    return resultado


def _extraer_datos_de_mensaje_viejo(mensaje: str, usuario_text: str) -> dict:
    """
    Extrae datos de correo desde el formato viejo.
    Maneja dos formatos:
    1. usuario_text = "CORREO (remitente@dominio.com)" + mensaje con Asunto:/cuerpo
    2. usuario_text normal + mensaje = "📧 Correo adjunto." (sin datos)
    """
    datos = {}

    # Formato 1: usuario_text = "CORREO (remitente)"
    if usuario_text.startswith('CORREO (') and usuario_text.endswith(')'):
        datos['remitente'] = usuario_text[8:-1]
    elif usuario_text.startswith('CORREO ('):
        datos['remitente'] = usuario_text[8:].rstrip(')')
    else:
        datos['remitente'] = usuario_text

    # Extraer asunto del mensaje
    datos['asunto'] = '(Sin asunto)'
    datos['cuerpo'] = ''

    if mensaje:
        lineas = mensaje.split('\n')
        cuerpo_lineas = []
        en_cuerpo = False

        for linea in lineas:
            linea_strip = linea.strip()
            if linea_strip.startswith('Asunto:'):
                datos['asunto'] = linea_strip[7:].strip()
            elif linea_strip.startswith('📧 Correo de seguimiento vinculado'):
                continue  # Skip old header
            elif '---' in linea_strip and not en_cuerpo:
                en_cuerpo = True
            elif en_cuerpo:
                cuerpo_lineas.append(linea)

        datos['cuerpo'] = '\n'.join(cuerpo_lineas).strip()

    return datos


def construir_mensaje_bitacora_email(datos_email: dict) -> str:
    """Construye el mensaje estructurado para la bitácora."""
    partes = []
    partes.append("[📧 CORREO]")
    partes.append(f"Remitente: {datos_email.get('remitente', 'Desconocido')}")
    partes.append(f"Asunto: {datos_email.get('asunto', '(Sin asunto)')}")
    if datos_email.get('fecha'):
        partes.append(f"Fecha correo: {datos_email['fecha']}")
    partes.append("---")

    cuerpo = datos_email.get('cuerpo', '')
    if cuerpo:
        if len(cuerpo) > 500:
            cuerpo = cuerpo[:500] + '... [truncado]'
        partes.append(cuerpo)

    if datos_email.get('adjuntos'):
        partes.append(f"📎 {len(datos_email['adjuntos'])} adjunto(s) en el correo")

    partes.append("[/📧 CORREO]")
    return '\n'.join(partes)


def es_mensaje_email(mensaje: str) -> bool:
    """Detecta si un mensaje ya tiene el formato nuevo."""
    return '[📧 CORREO]' in (mensaje or '')


def ejecutar_migracion(orden_id: int = None, solo_verificar: bool = False):
    """
    Ejecuta la migración de correos antiguos al nuevo formato.

    Args:
        orden_id: Si se especifica, solo migra esa orden. Si es None, migra todas.
        solo_verificar: Si es True, solo muestra lo que migraría sin hacer cambios.

    Returns:
        (n_migrados, n_total, errores)
    """
    if not supabase:
        print("❌ No hay conexión a Supabase")
        return 0, 0, ["No hay conexión a Supabase"]

    # ── 1. Buscar entradas de bitácora con correos ──
    try:
        query = supabase.table("bitacora").select("*")
        if orden_id:
            query = query.eq("orden_id", int(orden_id))
        res = query.execute()
        entradas = res.data or []
    except Exception as e:
        return 0, 0, [f"Error consultando bitácora: {e}"]

    if not entradas:
        print("ℹ️ No hay entradas en la bitácora.")
        return 0, 0, []

    # ── 2. Clasificar entradas ──
    entradas_a_migrar = []

    for b in entradas:
        mensaje = b.get('mensaje', '') or ''
        usuario_text = b.get('usuario_text', '') or ''
        archivo_url = b.get('archivo_url', '') or ''

        # Skip si ya tiene formato nuevo
        if es_mensaje_email(mensaje):
            continue

        # Caso A: archivo_url es .msg/.eml y mensaje es corto/genérico
        if archivo_url.lower().endswith(('.msg', '.eml')):
            if len(mensaje) < 100 or '📧 Correo' in mensaje or 'Correo adjunto' in mensaje:
                entradas_a_migrar.append({
                    'tipo': 'archivo_msg',
                    'entrada': b,
                })
                continue

        # Caso B: usuario_text empieza con "CORREO (" (formato viejo)
        if usuario_text.startswith('CORREO ('):
            entradas_a_migrar.append({
                'tipo': 'formato_viejo',
                'entrada': b,
            })
            continue

    n_total = len(entradas_a_migrar)
    print(f"📊 Encontradas {n_total} entradas para migrar de {len(entradas)} totales.")

    if n_total == 0:
        return 0, 0, []

    if solo_verificar:
        print("\n🔍 MODO VERIFICACIÓN — No se harán cambios.\n")
        for item in entradas_a_migrar:
            b = item['entrada']
            print(f"  - Orden #{b['orden_id']} | Bitácora #{b['id']} | Tipo: {item['tipo']}")
            print(f"    Usuario: {b.get('usuario_text', '?')}")
            print(f"    Mensaje: {(b.get('mensaje', '') or '')[:80]}...")
            print(f"    URL: {(b.get('archivo_url', '') or '')[:60]}")
            print()
        return 0, n_total, []

    # ── 3. Migrar ──
    n_migrados = 0
    errores = []

    for item in entradas_a_migrar:
        b = item['entrada']
        bit_id = b['id']

        try:
            datos_correo = None

            if item['tipo'] == 'archivo_msg':
                # Descargar y parsear el .msg/.eml
                print(f"  📥 Descargando correo de Orden #{b['orden_id']}...")
                datos_correo = _parsear_msg_desde_url(b['archivo_url'])

                if not datos_correo:
                    # No se pudo parsear, usar datos mínimos
                    datos_correo = {
                        'remitente': b.get('usuario_text', 'Desconocido'),
                        'asunto': '(Correo adjunto — no se pudo parsear)',
                        'fecha': '',
                        'cuerpo': '',
                    }

            elif item['tipo'] == 'formato_viejo':
                # Extraer datos del mensaje viejo
                datos_correo = _extraer_datos_de_mensaje_viejo(
                    b.get('mensaje', ''),
                    b.get('usuario_text', '')
                )

            if datos_correo:
                nuevo_mensaje = construir_mensaje_bitacora_email(datos_correo)

                # Solo actualizar si el mensaje cambió
                if nuevo_mensaje != b.get('mensaje', ''):
                    db_update("bitacora", {"mensaje": nuevo_mensaje}, "id", bit_id)
                    n_migrados += 1
                    print(f"  ✅ Bitácora #{bit_id} migrada (Orden #{b['orden_id']})")
                else:
                    print(f"  ⏭️ Bitácora #{bit_id} sin cambios necesarios")

        except Exception as e:
            errores.append(f"Bitácora #{bit_id}: {e}")
            print(f"  ❌ Error en Bitácora #{bit_id}: {e}")

    print(f"\n{'='*50}")
    print(f"✅ Migración completada: {n_migrados}/{n_total} entradas migradas")
    if errores:
        print(f"⚠️ {len(errores)} error(es):")
        for err in errores:
            print(f"   - {err}")

    return n_migrados, n_total, errores


# ==============================================================================
# 🖥️ INTERFAZ STREAMLIT
# ==============================================================================
def render():
    st.title("🔄 Migración de Correos en Bitácora")
    st.info("Este script actualiza las entradas antiguas de bitácora que contienen correos al nuevo formato estructurado.")

    st.markdown("""
    ### ¿Qué hace?

    Detecta entradas de bitácora con correos en formatos antiguos:
    - **Formato viejo**: `usuario_text = "CORREO (remitente)"` con mensaje largo
    - **Archivo .msg/.eml**: `archivo_url` termina en `.msg`/`.eml` con mensaje genérico

    Y las convierte al nuevo formato estructurado:
    ```
    [📧 CORREO]
    Remitente: juan@empresa.com
    Asunto: Solicitud de repuesto
    Fecha correo: 2026-07-15T10:30:00
    ---
    Contenido del correo...
    [/📧 CORREO]
    ```
    """)

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔍 Verificar (sin hacer cambios)", type="secondary", use_container_width=True):
            with st.spinner("Analizando bitácora..."):
                n_migrados, n_total, errores = ejecutar_migracion(solo_verificar=True)
            if n_total == 0:
                st.success("✅ No hay entradas pendientes de migrar.")
            else:
                st.warning(f"📋 {n_total} entrada(s) pendiente(s) de migrar.")

    with col2:
        if st.button("🔄 Ejecutar Migración", type="primary", use_container_width=True):
            with st.spinner("Migrando correos..."):
                n_migrados, n_total, errores = ejecutar_migracion(solo_verificar=False)
            if n_migrados > 0:
                st.success(f"✅ {n_migrados}/{n_total} entradas migradas correctamente.")
                st.rerun()
            elif n_total == 0:
                st.success("✅ No hay entradas pendientes de migrar.")
            else:
                st.error(f"❌ Hubo {len(errores)} error(es) durante la migración.")

    # ── Migración individual por orden ──
    st.markdown("---")
    st.markdown("### 🎯 Migración individual")
    orden_id = st.number_input("ID de Orden", min_value=1, step=1, key="migrar_orden_id")

    if st.button("Migrar solo esta orden", use_container_width=True):
        with st.spinner(f"Migrando Orden #{orden_id}..."):
            n_migrados, n_total, errores = ejecutar_migracion(orden_id=int(orden_id), solo_verificar=False)
        if n_migrados > 0:
            st.success(f"✅ Orden #{orden_id}: {n_migrados} entrada(s) migrada(s).")
        elif n_total == 0:
            st.info(f"ℹ️ Orden #{orden_id}: No hay entradas pendientes.")
        else:
            st.error(f"❌ Orden #{orden_id}: {len(errores)} error(es).")


if __name__ == "__main__":
    render()
