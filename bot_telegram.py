import logging
import os
import sys
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from supabase import create_client
import cloudinary
import cloudinary.uploader
import toml
from io import BytesIO
import os
from flask import Flask
from threading import Thread

# --- CÓDIGO PARA MANTENER VIVO EL BOT EN RENDER ---
app = Flask('')

@app.route('/')
def home():
    return "¡Hola! Soy el Bot de Orión y estoy vivo 🤖"

def run():
    # Render asigna un puerto en la variable de entorno PORT, o usa 8080 por defecto
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()
# --------------------------------------------------

# ==============================================================================
# 1. CARGA SEGURA DE CREDENCIALES
# ==============================================================================
print("🔍 Buscando archivo secrets.toml...")

try:
    # Buscamos el archivo en la ruta estándar de Streamlit
    secrets_path = ".streamlit/secrets.toml"
    
    if not os.path.exists(secrets_path):
        print(f"❌ ERROR: No encuentro el archivo en: {os.path.abspath(secrets_path)}")
        sys.exit(1)
        
    # Cargamos el archivo
    secrets = toml.load(secrets_path)
    print("✅ Archivo encontrado. Leyendo claves...")

    # Extraemos las claves (Si falla aquí, es porque falta agregarlas al archivo toml)
    TELEGRAM_TOKEN = secrets["telegram"]["token"]
    SUPABASE_URL = secrets["supabase"]["SUPABASE_URL"]
    SUPABASE_KEY = secrets["supabase"]["SUPABASE_KEY"]
    CLOUDINARY_CLOUD = secrets["cloudinary"]["cloud_name"]
    CLOUDINARY_KEY = secrets["cloudinary"]["api_key"]
    CLOUDINARY_SECRET = secrets["cloudinary"]["api_secret"]
    
    print("🔒 Credenciales cargadas correctamente.")

except KeyError as e:
    print(f"❌ ERROR DE CONFIGURACIÓN: Falta la sección o clave {e} en secrets.toml")
    print("💡 Asegúrate de agregar [telegram] token = '...' en tu archivo secrets.toml")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error inesperado cargando configuración: {e}")
    sys.exit(1)

# ==============================================================================
# 2. INICIALIZACIÓN DE SERVICIOS
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
    print(f"❌ Error conectando con Supabase o Cloudinary: {e}")
    sys.exit(1)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ==============================================================================
# 3. LÓGICA DEL BOT
# ==============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.first_name
    args = context.args 
    context.user_data.clear()

    if args:
        # MODO QR
        activo_id = args[0]
        try:
            res = supabase.table("activos").select("nombre").eq("id", activo_id).execute()
            nombre = res.data[0]['nombre'] if res.data else "Equipo Escaneado"
        except: nombre = "Equipo"
        
        context.user_data['origen'] = 'qr'
        context.user_data['activo_id'] = activo_id
        await update.message.reply_text(f"✅ Equipo: *{nombre}*.\n📸 Envíame una **FOTO**.", parse_mode='Markdown')
    else:
        # MODO MANUAL
        context.user_data['origen'] = 'manual'
        await update.message.reply_text(f"👋 Hola {user}.\n📍 **¿En qué ÁREA estás?**")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            "descripcion": texto,
            "foto_url": context.user_data['foto_url'],
            "estado": "Pendiente",
            "prioridad_sugerida": "Media",
            "activo_id": int(context.user_data['activo_id']) if origen == 'qr' else None,
            "area_reportada": "Escaneado por QR" if origen == 'qr' else context.user_data['area_reportada']
        }

        try:
            supabase.table("solicitudes").insert(datos).execute()
            await update.message.reply_text("🚀 **¡Reporte Enviado!**")
            context.user_data.clear()
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")
    else:
        await update.message.reply_text("📸 Falta la foto. Envíala antes de describir el problema.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    origen = context.user_data.get('origen')
    if not origen:
        await update.message.reply_text("⚠️ Usa /start primero.")
        return
    if origen == 'manual' and 'area_reportada' not in context.user_data:
        await update.message.reply_text("📍 Primero dime el ÁREA.")
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
        await update.message.reply_text("❌ Error subiendo foto.")

    if __name__ == '__main__':
    # 1. Verificación del Token (Tu código original)
    if not TELEGRAM_TOKEN or "PEGA_AQUI" in TELEGRAM_TOKEN:
        print("❌ ERROR: El Token de Telegram no parece válido. Revisa secrets.toml")
        sys.exit(1)

    # 2. ENCENDER EL SERVIDOR WEB (Esto mantiene vivo a Render)
    print("🌍 Iniciando servidor web 'Keep Alive'...")
    keep_alive()

    # 3. ARRANCAR EL BOT
    print("🤖 Bot de Orión Iniciado y escuchando...")
    # Asegúrate de que tu variable se llame 'application' o 'updater' según tu código anterior
    application.run_polling()
        
    try:
        application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        application.add_handler(CommandHandler('start', start))
        application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
        
        print("🤖 Bot ORIÓN conectado y escuchando de forma segura...")
        application.run_polling()
    except Exception as e:
        print(f"❌ Error al iniciar el bot: {e}")
