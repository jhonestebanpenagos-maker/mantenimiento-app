import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from supabase import create_client
import cloudinary
import cloudinary.uploader
import toml
from io import BytesIO

# ==============================================================================
# 1. CONFIGURACIÓN DE CREDENCIALES
# ==============================================================================
# Intentamos cargar las claves desde .streamlit/secrets.toml automáticamente.
# Si falla, debes ponerlas manualmente en las variables de abajo.
try:
    secrets = toml.load(".streamlit/secrets.toml")
    
    TELEGRAM_TOKEN = "8382805163:AAHFklVKQZtFUblLfefnXsAfWYfPq6KK1As" # <--- ¡CAMBIAR SI ES NECESARIO!
    
    # Si usas TOML, sobreescribimos la variable de arriba
    if "telegram" in secrets and "token" in secrets["telegram"]:
        TELEGRAM_TOKEN = secrets["telegram"]["token"]
        
    SUPABASE_URL = secrets["supabase"]["SUPABASE_URL"]
    SUPABASE_KEY = secrets["supabase"]["SUPABASE_KEY"]
    
    CLOUDINARY_CLOUD = secrets["cloudinary"]["cloud_name"]
    CLOUDINARY_KEY = secrets["cloudinary"]["api_key"]
    CLOUDINARY_SECRET = secrets["cloudinary"]["api_secret"]

except Exception as e:
    print(f"⚠️ Advertencia: No se detectó secrets.toml ({e}). Usando configuración manual.")
    # RELLENA ESTO SOLO SI NO USAS EL ARCHIVO SECRETS.TOML
    # TELEGRAM_TOKEN = "TU_TOKEN_DEL_BOTFATHER"
    # SUPABASE_URL = "TU_URL_SUPABASE"
    # SUPABASE_KEY = "TU_KEY_SUPABASE"
    # CLOUDINARY_CLOUD = "..."
    # CLOUDINARY_KEY = "..."
    # CLOUDINARY_SECRET = "..."

# Iniciar Clientes
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
cloudinary.config(
    cloud_name = CLOUDINARY_CLOUD,
    api_key = CLOUDINARY_KEY,
    api_secret = CLOUDINARY_SECRET,
    secure = True
)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ==============================================================================
# 2. LÓGICA DEL BOT
# ==============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Se ejecuta al iniciar el chat o escanear un QR (/start ID)"""
    user = update.effective_user.first_name
    args = context.args # Aquí llegan los parámetros del QR
    context.user_data.clear() # Limpiamos la memoria de conversaciones anteriores

    if args:
        # --- MODO 1: ESCANEO QR ---
        activo_id = args[0]
        try:
            # Consultamos el nombre del activo para confirmar
            res = supabase.table("activos").select("nombre").eq("id", activo_id).execute()
            nombre_activo = res.data[0]['nombre'] if res.data else "Activo Escaneado"
        except:
            nombre_activo = "Equipo Identificado"
        
        # Guardamos en memoria que viene de QR
        context.user_data['origen'] = 'qr'
        context.user_data['activo_id'] = activo_id
        
        await update.message.reply_text(
            f"✅ Equipo: *{nombre_activo}*.\n\n"
            "📸 Por favor, envíame una **FOTO** del problema.",
            parse_mode='Markdown'
        )
    else:
        # --- MODO 2: REPORTE MANUAL ---
        context.user_data['origen'] = 'manual'
        
        await update.message.reply_text(
            f"👋 Hola {user}.\n\n"
            "📍 **¿En qué ÁREA o LUGAR estás?**\n"
            "(Ej: Cocina, Baños, Cuarto de Bombas...)"
        )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja las respuestas de texto del usuario"""
    texto = update.message.text
    origen = context.user_data.get('origen')

    # Caso A: El usuario escribe sin haber dado /start
    if not origen:
        await start(update, context)
        return

    # Caso B: Está en Modo Manual y nos acaba de decir el Área
    if origen == 'manual' and 'area_reportada' not in context.user_data:
        context.user_data['area_reportada'] = texto
        await update.message.reply_text(
            f"👍 Entendido: **{texto}**.\n\n"
            "📸 Ahora envíame una **FOTO** para ver qué pasa."
        )
        return

    # Caso C: Ya tenemos ubicación/ID y Foto -> Este texto es la DESCRIPCIÓN FINAL
    if 'foto_url' in context.user_data:
        descripcion = texto
        foto_url = context.user_data['foto_url']
        usuario_telegram = update.effective_user.first_name
        
        await update.message.reply_text("💾 Guardando reporte en el sistema...")

        # Preparar datos para Supabase
        nuevo_reporte = {
            "solicitante_id": f"{usuario_telegram} (Telegram)",
            "descripcion": descripcion,
            "foto_url": foto_url,
            "estado": "Pendiente",
            "prioridad_sugerida": "Media"
        }

        # Llenar campos según el origen
        if origen == 'qr':
            nuevo_reporte["activo_id"] = int(context.user_data['activo_id'])
            nuevo_reporte["area_reportada"] = "Escaneado por QR"
        else:
            nuevo_reporte["activo_id"] = None # Se va vacío
            nuevo_reporte["area_reportada"] = context.user_data['area_reportada']

        try:
            supabase.table("solicitudes").insert(nuevo_reporte).execute()
            
            await update.message.reply_text(
                "🚀 **¡Reporte Enviado con Éxito!**\n"
                "El supervisor ha sido notificado.\n\n"
                "Escribe /start para un nuevo reporte.",
                parse_mode='Markdown'
            )
            context.user_data.clear() # Reiniciar
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error al guardar: {e}")
            
    else:
        # Caso D: Escribió descripción pero falta la foto
        await update.message.reply_text("📸 Falta la foto. Por favor envíala antes de describir el problema.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe la foto y la sube a Cloudinary"""
    # Verificar que ya sepamos dónde está
    origen = context.user_data.get('origen')
    
    if not origen:
        await update.message.reply_text("⚠️ Primero inicia con /start o escanea un QR.")
        return
    
    if origen == 'manual' and 'area_reportada' not in context.user_data:
        await update.message.reply_text("📍 Primero escribe el nombre del ÁREA.")
        return

    # Procesar imagen
    file = await update.message.photo[-1].get_file()
    out = BytesIO()
    await file.download_to_memory(out)
    out.seek(0)
    
    msg_espera = await update.message.reply_text("⏳ Subiendo imagen a la nube...")
    
    try:
        # Subir a Cloudinary
        res = cloudinary.uploader.upload(out, folder="orion_reportes_telegram")
        context.user_data['foto_url'] = res.get('secure_url')
        
        # Borrar mensaje de espera
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_espera.message_id)
        
        await update.message.reply_text(
            "✅ Foto recibida.\n"
            "📝 **¿Qué está fallando?** (Escribe una breve descripción)"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error subiendo imagen: {e}")

if __name__ == '__main__':
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Comandos y Manejadores
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

    print("🤖 Bot ORIÓN (Modo Híbrido) escuchando...")
    application.run_polling()
