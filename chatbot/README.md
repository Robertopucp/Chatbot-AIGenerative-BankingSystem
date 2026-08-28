# Bot de Telegram - Chatbot RAG

Bot de Telegram que se conecta a la API FastAPI del sistema de chatbot RAG para ofrecer una interfaz conversacional natural.

## Características

- **100% Lenguaje Natural**: No usa comandos, solo conversación natural
- **Polling**: No requiere webhook ni URL pública
- **Integración Completa**: Usa todos los servicios del chatbot (RAG, ventas, inventario)
- **Gestión de Usuario**: Cada usuario de Telegram tiene su propio historial de conversación

## Requisitos Previos

1. **Servidor FastAPI corriendo**: El bot necesita que el servidor principal esté activo
   ```bash
   # En la carpeta principal del proyecto
   python main.py
   ```

2. **Token de Telegram Bot**:
   - Habla con [@BotFather](https://t.me/botfather) en Telegram
   - Crea un nuevo bot con `/newbot`
   - Copia el token que te proporciona
   - Agrégalo al archivo `.env` como `TOKEN_TELEGRAM_BOT`

## Instalación

1. Instala las dependencias del bot:
   ```bash
   cd chatbot
   pip install -r requirements.txt
   ```

2. Asegúrate de que el archivo `.env` en la raíz del proyecto tenga configurado:
   ```env
   TOKEN_TELEGRAM_BOT=tu_token_aqui
   ```

## Uso

### Iniciar el Bot

```bash
# Desde la carpeta chatbot/
python bot.py
```

O desde la raíz del proyecto:
```bash
python chatbot/bot.py
```

### Interactuar con el Bot

1. Busca tu bot en Telegram usando el nombre que le diste
2. Simplemente escribe mensajes naturales, por ejemplo:
   - "Hola, ¿qué productos tienen?"
   - "Quiero comprar 2 laptops HP"
   - "¿Cuánto stock hay de notebooks?"
   - "Muéstrame información sobre productos gaming"

3. El bot responderá usando el mismo sistema inteligente que la API web

### Detener el Bot

Presiona `Ctrl+C` en la terminal donde está corriendo el bot.

## Arquitectura

```
Usuario Telegram
    ↓
Bot (polling)
    ↓
API FastAPI (localhost:8000)
    ↓
Chatbot Service + RAG + Database
```

## Características Técnicas

### Sin Comandos
Este bot está diseñado para funcionar 100% con lenguaje natural. No requiere comandos como `/start` o `/help`.

### Gestión de Usuarios
- Cada usuario de Telegram se identifica como `telegram_{user_id}`
- El historial de conversación se mantiene separado por usuario
- Los usuarios pueden tener conversaciones independientes

### Manejo de Errores
- Si la API no está disponible, el bot informa al usuario
- Los errores se registran en logs para debugging
- El bot nunca se cae por errores de la API

## Troubleshooting

### El bot no responde
1. Verifica que el servidor FastAPI esté corriendo (`python main.py`)
2. Verifica que el token en `.env` sea correcto
3. Revisa los logs del bot para ver errores

### Error de conexión con la API
```
⚠️ No se pudo conectar con la API
```
- Asegúrate de que el servidor FastAPI esté corriendo en `http://localhost:8000`
- Verifica que no haya firewall bloqueando la conexión
- Prueba acceder a `http://localhost:8000/health` en tu navegador

### El bot se desconecta
- Esto es normal si pierdes conexión a internet
- El bot se reconectará automáticamente
- Si persiste, reinicia el bot con `Ctrl+C` y `python bot.py`

## Configuración Avanzada

### Cambiar la URL de la API

Por defecto, el bot se conecta a `http://localhost:8000`. Para cambiar esto, agrega en `.env`:

```env
API_URL=http://tu-servidor:puerto
```

### Logs

Los logs del bot incluyen:
- Mensajes recibidos y enviados
- Errores de conexión
- Estado de la API

Puedes ajustar el nivel de logging en `bot.py` cambiando:
```python
logging.basicConfig(level=logging.INFO)  # Cambia a DEBUG para más detalles
```

## Desarrollo

### Estructura del Código

```python
# bot.py - Archivo principal

ChatbotAPI          # Cliente para comunicarse con FastAPI
├── send_message()  # Envía mensaje y obtiene respuesta
└── check_health()  # Verifica estado de la API

handle_message()    # Procesa mensajes del usuario
error_handler()     # Maneja errores
startup()           # Hook de inicialización
shutdown()          # Hook de cierre
main()              # Función principal
```

### Agregar Funcionalidades

Para agregar nuevas funcionalidades, puedes:

1. **Agregar respuestas especiales**: Modifica `handle_message()` para detectar palabras clave
2. **Agregar comandos**: Aunque no es el diseño actual, puedes agregar `CommandHandler` si lo necesitas
3. **Personalizar formato**: Modifica cómo se formatean las respuestas en `handle_message()`

## Ejemplos de Uso

### Consulta de Productos
```
Usuario: "¿Qué laptops tienen disponibles?"
Bot: "Tenemos varias laptops disponibles: HP ProBook, Dell Latitude, Lenovo ThinkPad..."
```

### Registro de Venta
```
Usuario: "Quiero comprar 2 HP ProBook para Juan Pérez, pago en efectivo"
Bot: "✅ Venta registrada exitosamente..."
```

### Consulta de Inventario
```
Usuario: "¿Cuántas HP ProBook quedan?"
Bot: "Actualmente hay 45 unidades de HP ProBook en inventario."
```

## Seguridad

- El token del bot NUNCA debe compartirse públicamente
- Mantén el archivo `.env` fuera de control de versiones
- Cada usuario tiene acceso solo a su propia información

## Soporte

Para problemas o preguntas:
1. Revisa este README
2. Revisa los logs del bot
3. Verifica que la API principal esté funcionando correctamente
