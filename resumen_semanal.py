# resumen_semanal.py
# Se ejecuta automáticamente cada lunes a las 8am via GitHub Actions

import os
import requests
from supabase import create_client
from datetime import datetime, timedelta

# =====================================================
# CONFIGURACIÓN
# =====================================================
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
TELEGRAM_TOKEN = "8382805163:AAEfkue6AMQu6qvqyRdTmh05kIOZUOxCdwM"

def enviar_telegram(chat_id, mensaje):
    """Envía mensaje por Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={
            "chat_id": chat_id,
            "text": mensaje,
            "parse_mode": "Markdown"
        })
        print(f"✅ Mensaje enviado a {chat_id}")
    except Exception as e:
        print(f"❌ Error enviando a {chat_id}: {e}")

def generar_resumen():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ ERROR: No se encontraron variables de entorno.")
        return

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Rango de la semana anterior
    hoy       = datetime.now()
    inicio    = (hoy - timedelta(days=7)).isoformat()
    fin       = hoy.isoformat()

    print(f"Generando resumen del {inicio[:10]} al {fin[:10]}...\n")

    try:
        # 1. Órdenes de la semana
        ordenes = supabase.table("ordenes").select("*").execute()
        todas   = ordenes.data or []

        # Filtrar por semana
        def en_semana(fecha_str):
            try:
                return inicio <= fecha_str <= fin
            except:
                return False

        semana       = [o for o in todas if en_semana(o.get('fecha_creacion', ''))]
        abiertas     = [o for o in todas if o.get('estado') == 'Abierta']
        concluidas_s = [o for o in semana if o.get('estado') == 'Concluida']
        nuevas_s     = [o for o in semana]
        criticas     = [o for o in abiertas if o.get('criticidad') in ['Alta', 'Crítica']]

        # 2. Stock bajo
        repuestos   = supabase.table("repuestos").select("*").execute()
        rep_data    = repuestos.data or []
        bajo_stock  = [r for r in rep_data if r.get('stock_actual', 0) <= r.get('stock_minimo', 0)]
        sin_stock   = [r for r in bajo_stock if r.get('stock_actual', 0) == 0]

        # 3. Solicitudes pendientes
        solicitudes = supabase.table("solicitudes").select("*").eq("estado", "Pendiente").execute()
        n_solic     = len(solicitudes.data or [])

        # 4. Usuarios (para saber a quién enviar)
        usuarios_res = supabase.table("usuarios").select("*").execute()
        usuarios     = usuarios_res.data or []
        admins       = [u for u in usuarios if u.get('rol') == 'Admin' and u.get('chat_id')]

        if not admins:
            print("⚠️ No hay admins con chat_id configurado.")
            return

        # 5. Construir mensaje
        fecha_rep = hoy.strftime("%d/%m/%Y")
        semana_str = f"{(hoy - timedelta(days=7)).strftime('%d/%m')} — {hoy.strftime('%d/%m/%Y')}"

        mensaje = (
            f"📊 *RESUMEN SEMANAL ORIÓN*\n"
            f"_{semana_str}_\n"
            f"{'='*30}\n\n"

            f"🛠️ *ÓRDENES DE TRABAJO*\n"
            f"• Nuevas esta semana: *{len(nuevas_s)}*\n"
            f"• Concluidas esta semana: *{len(concluidas_s)}*\n"
            f"• Pendientes totales: *{len(abiertas)}*\n"
            f"• Críticas/Altas pendientes: *{len(criticas)}*\n\n"

            f"📬 *BUZÓN DE SOLICITUDES*\n"
            f"• Sin atender: *{n_solic}*\n\n"

            f"🔩 *INVENTARIO REPUESTOS*\n"
            f"• Bajo stock: *{len(bajo_stock)}*\n"
            f"• Sin stock: *{len(sin_stock)}*\n\n"
        )

        # Agregar detalle de críticas si hay
        if criticas:
            mensaje += f"🚨 *ÓRDENES CRÍTICAS PENDIENTES*\n"
            for o in criticas[:5]:  # máximo 5 para no hacer el mensaje gigante
                mensaje += f"• OT #{o['id']} — {o['descripcion'][:40]}...\n"
            if len(criticas) > 5:
                mensaje += f"  _...y {len(criticas) - 5} más_\n"
            mensaje += "\n"

        # Agregar detalle de sin stock si hay
        if sin_stock:
            mensaje += f"🔴 *SIN STOCK*\n"
            for r in sin_stock[:5]:
                mensaje += f"• {r['nombre']} ({r.get('referencia', 'S/R')})\n"
            if len(sin_stock) > 5:
                mensaje += f"  _...y {len(sin_stock) - 5} más_\n"
            mensaje += "\n"

        mensaje += f"_Generado automáticamente el {fecha_rep}_\n"
        mensaje += f"_Sistema ORIÓN — Mantenimiento Industrial_"

        # 6. Enviar a todos los admins
        print(f"Enviando a {len(admins)} administrador(es)...\n")
        for admin in admins:
            enviar_telegram(admin['chat_id'], mensaje)

        print("\n" + "="*40)
        print("Resumen semanal enviado correctamente.")
        print(f"  Órdenes nuevas   : {len(nuevas_s)}")
        print(f"  Pendientes total : {len(abiertas)}")
        print(f"  Críticas         : {len(criticas)}")
        print(f"  Bajo stock       : {len(bajo_stock)}")
        print("="*40)

    except Exception as e:
        print(f"❌ Error generando resumen: {e}")

if __name__ == "__main__":
    generar_resumen()
