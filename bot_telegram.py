import logging
import os
import sys
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from supabase import create_client
import cloudinary
import cloudinary.uploader
from io import BytesIO
from flask import Flask
from threading import Thread

# ==============================================================================
# 1. SERVIDOR WEB "KEEP ALIVE"
# ==============================================================================
app = Flask('')

# Silenciamos los logs de Flask para que no estorben, solo errores
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

@app.route('/')
def home():
    return "Bot Orión Activo 🤖"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ==============================================================================
# 2. CARGA DE CREDENCIALES
# ==============================================================================
print("🔍 Iniciando sistema...")

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
CLOUDINARY_CLOUD = os.environ.get("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_KEY = os.environ.get("CLOUDINARY_API_KEY")
CLOUDINARY_SECRET = os.environ.get("CLOUDINARY_API_SECRET")

# Validación rápida
if not TELEGRAM_TOKEN:
    print("❌ ERROR FATAL: No se encontró TELEGRAM_TOKEN en las variables de entorno.")
    sys.exit(1)

# ==============================================================================
# 3. INICIALIZACIÓN DE SERVICIOS
# ==============================================================================
try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    cloudinary.config(
        cloud_name = CLOUDINARY_CLOUD,
        api_key = CLOUDINARY_KEY,
        api_secret = CLOUDINARY_SECRET,
        secure = True
    )
except Exception as e:
    print(f"❌ Error conectando servicios: {e}")

# Activamos logs DETALLADOS para ver si Telegram nos habla
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO 
)

# ==============================================================================
# 4. LÓGICA DEL BOT
# ==============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"📩 Recibido comando /start de {update.effective_user.first_name}") # Log de depuración
    
    user = update.effective_user.first_name
    args = context.args 
    context.user_data.clear()

    if args:
        activo_id = args[0]
        try:
            res = supabase.table("activos").select("nombre").eq("id", activo_id).execute()
            nombre = res.data[0]['nombre'] if res.data else "Equipo Escaneado"
        except: nombre = "Equipo"
        
        context.user_data['origen'] = 'qr'
        context.user_data['activo_id'] = activo_id
        await update.message.reply_text(f"✅ Equipo: *{nombre}*.\n📸 Envíame una **FOTO**.", parse_mode='Markdown')
    else:
        context.user_data['origen'] = 'manual'
        await update.message.reply_text(f"👋 Hola {user}.\n📍 **¿En qué ÁREA estás?**")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"📩 Texto recibido: {update.message.text}") # Log de depuración
    
    texto = update.message.text
    origen = context.user_data.get('origen')

    if not origen:
        await start(update, context)
        return

    if origen == 'manual' and 'area_reportada' not in context.user_data:
        context.user_data['area_reportada'] = texto
        await update.message.reply_text(f"👍 Entendido: **{texto}**.\n📸 Ahora envíame una **FOTO**.")
        return

    if 'foto_url' in context.user_data:
        await update.message.reply_text("💾 Guardando reporte...")
        
        datos = {
            "solicitante_id": f"{update.effective_user.first_name} (Telegram)",
            "chat_id": update.effective_chat.id,
            "descripcion": texto,
            "foto_url": context.user_data['foto_url'],
            "estado": "Pendiente",
            "prioridad_sugerida": "Media",
            "activo_id": int(context.user_data['activo_id']) if origen == 'qr' else None,
            "area_reportada": "Escaneado por QR" if origen == 'qr' else context.user_data['area_reportada']
        }

        try:
            # ⚠️ IMPORTANTE: Si la tabla 'solicitudes' no existe, cambiar a 'ordenes'
            supabase.table("solicitudes").insert(datos).execute()
            await update.message.reply_text("🚀 **¡Reporte Enviado!**")
            context.user_data.clear()
        except Exception as e:
            print(f"❌ Error Supabase: {e}")
            await update.message.reply_text(f"❌ Error al guardar: {e}")
    else:
        await update.message.reply_text("📸 Falta la foto. Envíala antes de describir el problema.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📩 Foto recibida...") # Log de depuración
    
    origen = context.user_data.get('origen')
    if not origen:
        await update.message.reply_text("⚠️ Usa /start primero.")
        return

    file = await update.message.photo[-1].get_file()
    out = BytesIO()
    await file.download_to_memory(out)
    out.seek(0)
    
    msg = await update.message.reply_text("⏳ Subiendo...")
    try:
        res = cloudinary.uploader.upload(out, folder="orion_reportes_telegram")
        context.user_data['foto_url'] = res.get('secure_url')
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg.message_id)
        await update.message.reply_text("✅ Foto lista.\n📝 **Describe el problema:**")
    except Exception as e:
        print(f"❌ Error Cloudinary: {e}")
        await update.message.reply_text("❌ Error subiendo foto.")

# ==============================================================================
# 5. EJECUCIÓN PRINCIPAL
# ==============================================================================
if __name__ == '__main__':
    # 1. Arrancar servidor web en segundo plano
    print("🌍 Iniciando servidor web...")
    keep_alive()

    # 2. Configurar y arrancar el bot
    try:
        print("🤖 Configurando Bot...")
        application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        
        # Handlers
        application.add_handler(CommandHandler('start', start))
        application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
        
        print("🚀 EL BOT ESTÁ ESCUCHANDO (Polling)...")
        
        # EL TRUCO: drop_pending_updates=True borra basura vieja y elimina conflictos de webhooks
        application.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        print(f"❌ Error fatal: {e}")
