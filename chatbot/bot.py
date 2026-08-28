"""
Bot de Telegram para Chatbot RAG
Utiliza polling para recibir mensajes y se conecta a la API FastAPI
"""
import os
import sys
import logging
import asyncio
from pathlib import Path

# Add parent directory to path to import from main project
sys.path.append(str(Path(__file__).parent.parent))

import requests
from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    filters,
    ContextTypes
)
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TOKEN = os.getenv('TOKEN_TELEGRAM_BOT')
API_URL = os.getenv('API_URL', 'http://localhost:8000')

if not TOKEN:
    raise ValueError(
        "TOKEN_TELEGRAM_BOT no está configurado en el archivo .env\n"
        "Obtén tu token desde @BotFather en Telegram"
    )


class ChatbotAPI:
    """Cliente para interactuar con la API FastAPI del chatbot"""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})

    def send_message(self, user_id: str, message: str) -> dict:
        """Envía un mensaje al chatbot y obtiene la respuesta"""
        try:
            response = self.session.post(
                f'{self.base_url}/chat',
                json={
                    'user_id': user_id,
                    'message': message
                },
                timeout=30
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Error al conectar con la API: {e}")
            return {
                'to_user': '❌ Lo siento, no puedo conectarme al servidor en este momento. Por favor, intenta más tarde.',
                'reasoning': str(e),
                'action': None
            }

    def check_health(self) -> bool:
        """Verifica que la API esté disponible"""
        try:
            response = self.session.get(f'{self.base_url}/health', timeout=5)
            return response.status_code == 200
        except:
            return False


# Initialize API client
api_client = ChatbotAPI(API_URL)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Maneja todos los mensajes de texto enviados al bot.
    No usa comandos, solo lenguaje natural.
    """
    # Ignore messages without text
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    user_id = f"telegram_{user.id}"
    message_text = update.message.text

    logger.info(f"Mensaje de {user.first_name} ({user_id}): {message_text}")

    # Show typing indicator
    await update.message.chat.send_action("typing")

    try:
        # Send message to chatbot API
        response = api_client.send_message(user_id, message_text)

        # Format response
        reply_text = response.get('to_user', 'Lo siento, no obtuve respuesta del servidor.')

        # Add action info if available
        action = response.get('action') or {}
        command = action.get('command')
        if command and command not in ('none', 'chat'):
            reply_text += f"\n\n⚡ <i>Acción ejecutada: {command}</i>"

        # Send response to user
        await update.message.reply_text(
            reply_text,
            parse_mode='HTML'
        )

        logger.info(f"Respuesta enviada a {user.first_name}")

    except Exception as e:
        logger.error(f"Error al procesar mensaje: {e}")
        await update.message.reply_text(
            "❌ Ocurrió un error al procesar tu mensaje. Por favor, intenta nuevamente.",
            parse_mode='HTML'
        )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja errores durante la ejecución del bot"""
    logger.error(f"Update {update} causó error: {context.error}")

    if update and update.message:
        await update.message.reply_text(
            "❌ Ocurrió un error inesperado. Por favor, intenta nuevamente más tarde."
        )


async def startup(application: Application):
    """Se ejecuta al iniciar el bot"""
    logger.info("=" * 60)
    logger.info("BOT DE TELEGRAM - CHATBOT RAG")
    logger.info("=" * 60)
    logger.info(f"API URL: {API_URL}")

    # Check API connection
    if api_client.check_health():
        logger.info("✅ Conexión con la API exitosa")
    else:
        logger.warning("⚠️ No se pudo conectar con la API")
        logger.warning("Asegúrate de que el servidor FastAPI esté corriendo")

    logger.info("\n🤖 Bot iniciado y esperando mensajes...")
    logger.info("Presiona Ctrl+C para detener el bot\n")


async def shutdown(application: Application):
    """Se ejecuta al detener el bot"""
    logger.info("\n👋 Deteniendo bot...")


def main():
    """Función principal para iniciar el bot"""

    # Validate configuration
    if not TOKEN:
        print("❌ Error: TOKEN_TELEGRAM_BOT no configurado en .env")
        return

    try:
        # Create application
        application = (
            Application.builder()
            .token(TOKEN)
            .build()
        )

        # Register handlers
        # Handle ALL text messages (no commands, pure natural language)
        application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                handle_message
            )
        )

        # Register error handler
        application.add_error_handler(error_handler)

        # Register startup/shutdown hooks
        application.post_init = startup
        application.post_shutdown = shutdown

        # Start bot with polling
        logger.info("Iniciando bot con polling...")
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )

    except KeyboardInterrupt:
        logger.info("\n👋 Bot detenido por el usuario")

    except Exception as e:
        logger.error(f"❌ Error fatal: {e}")
        raise


if __name__ == '__main__':
    main()
