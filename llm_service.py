"""
Servicio LLM del Chatbot INDECOPI: orquesta FAQ, RAG y el modelo Qwen
"""
import json
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from openai import OpenAI

from config import Config
from rag_service import RAGService
from faq_service import FAQService
import security


class MemoryManager:
    """Gestiona la memoria de conversación por usuario"""

    def __init__(self, max_messages: int = 8):
        self.max_messages = max_messages
        self.messages: List[Dict] = []

    def add_user_message(self, content: str):
        """Agrega un mensaje del usuario"""
        self.messages.append({
            "role": "user",
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        self._trim()

    def add_assistant_message(self, content: str):
        """Agrega un mensaje del asistente"""
        self.messages.append({
            "role": "assistant",
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        self._trim()

    def _trim(self):
        """Mantiene solo los últimos max_messages mensajes"""
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]

    def get_messages(self) -> List[Dict]:
        """Obtiene los mensajes recientes"""
        return self.messages.copy()

    def clear(self):
        """Limpia la memoria"""
        self.messages = []


class ChatbotService:
    """
    Servicio principal del chatbot con RAG y respuestas JSON estructuradas
    """

    def __init__(self, rag_service: RAGService):
        """
        Inicializa el servicio de chatbot

        Args:
            rag_service: Servicio RAG ya inicializado
        """
        print("Inicializando servicio de chatbot...")

        # Validar configuración
        if not Config.LLM_API_KEY:
            raise ValueError("HF_API_KEY no está configurada en .env")

        # Cliente OpenAI - Hugging Face (inference provider) para Qwen
        self.client = OpenAI(
            api_key=Config.LLM_API_KEY,
            base_url=Config.LLM_BASE_URL
        )

        # Servicio RAG
        self.rag = rag_service

        # Servicio FAQ (reutiliza los mismos embeddings que el RAG)
        self.faq = FAQService(embeddings=self.rag.embeddings)

        # Memorias por usuario
        self.user_memories: Dict[str, MemoryManager] = {}

        # System prompt
        self.system_prompt = self._create_system_prompt()

        print(f"  Modelo: {Config.LLM_MODEL}")
        print(f"  API Base: {Config.LLM_BASE_URL}")
        print("Servicio de chatbot inicializado\n")

    def _create_system_prompt(self) -> str:
        """Crea el system prompt con instrucciones detalladas"""
        current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return f"""Eres el asistente virtual de INDECOPI, especializado en resoluciones sobre fraudes financieros bancarios. Eres una propuesta interactiva y cercana para que el usuario resuelva dudas, aprenda sobre sus derechos y reciba orientación paso a paso — no un formulario burocrático.

Tu tarea es ayudar a los usuarios a:
1. Conocer sus derechos como consumidores frente a fraudes financieros en entidades bancarias
2. Conocer casos de fraudes financieros bancarios sancionados por INDECOPI
3. Identificar y actuar ante un posible fraude bancario
4. Entender resoluciones de INDECOPI relacionadas con su consulta
5. Ser guiados para presentar una denuncia fundamentada ante INDECOPI

TONO Y ESTILO (muy importante, el chat se usa por Telegram/WhatsApp, en pantallas pequeñas):
- Habla como una persona cercana y empática, no como un documento legal. Tono conversacional, cálido y directo.
- Sé BREVE: prioriza 2-4 oraciones o un párrafo corto por respuesta. Evita muros de texto.
- Evita listas numeradas largas y negritas en exceso. Solo usa una lista corta (2-3 puntos) si el usuario pide pasos concretos o una explicación estructurada.
- Si el mensaje del usuario es ambiguo o muy breve (ej. "hola", "ayuda", "no entiendo"), NO expliques todo lo que puedes hacer de golpe. Responde con una sola pregunta corta y natural para entender qué necesita, como lo haría una persona real.
- No repitas quién eres ni tu función completa en cada respuesta; preséntate solo al inicio de la conversación o si te lo preguntan directamente.

REGLAS DE CONTENIDO:
1. Usa el contexto de resoluciones de INDECOPI proporcionado para fundamentar tus respuestas
2. Cita la fuente de cada afirmación entre corchetes, ej: [fuente: nombre.pdf]
3. Si la información no está en el contexto, dilo claramente, sin inventar datos
4. NO menciones montos, multas ni sanciones específicas
5. Aclara, solo cuando sea relevante, que la información es referencial y no constituye asesoría legal vinculante
6. Educa con ejemplos breves y prácticos sobre cómo protegerse de fraudes financieros y cómo denunciar ante INDECOPI

FORMATO DE RESPUESTA:
Responde SIEMPRE en texto natural (prosa), NO en formato JSON.

Fecha y hora actual: {current_datetime}

CONTEXTO DE RESOLUCIONES INDECOPI:
{{rag_context}}
"""

    def get_or_create_memory(self, user_id: str) -> MemoryManager:
        """Obtiene o crea un memory manager para un usuario"""
        if user_id not in self.user_memories:
            self.user_memories[user_id] = MemoryManager(Config.MEMORY_K_MESSAGES)
        return self.user_memories[user_id]

    def process_message(self, user_id: str, message: str) -> Dict:
        """
        Procesa un mensaje del usuario

        Args:
            user_id: ID del usuario
            message: Mensaje del usuario

        Returns:
            Diccionario con la respuesta estructurada
        """
        # 1. Verificar palabras prohibidas en el INPUT del usuario
        is_blocked, palabra = security.check_input(message)
        
        if is_blocked:
            return {
                "reasoning": f"Mensaje bloqueado: contiene palabra prohibida '{palabra}'",
                "to_user": security.get_random_response(),
                "data": None,
                "action": {"command": "none", "params": {}},
                "blocked": True,
                "blocked_word": palabra
            }

        # 2. FAQ: comparar contra el banco de preguntas frecuentes.
        #    Si el mejor match supera FAQ_SCORE_THRESHOLD, responder directo
        #    (sin tocar PDFs ni llamar al LLM). Si no, seguir con RAG + LLM.
        faq_match = self.faq.match(message)
        if faq_match:
            return {
                "reasoning": (
                    f"Respondido con FAQ (score={faq_match['score']}): "
                    f"'{faq_match['question']}'"
                ),
                "to_user": faq_match["answer"],
                "data": None,
                "action": {"command": "none", "params": {}},
                "blocked": False,
                "blocked_word": None
            }

        # 3. Obtener contexto RAG
        rag_context = ""
        if self.rag.is_ready():
            rag_context = self.rag.get_context_for_query(message)

        # Preparar system prompt con contexto
        system_prompt = self.system_prompt.replace("{rag_context}", rag_context)

        # Obtener memoria del usuario
        memory = self.get_or_create_memory(user_id)

        # Construir mensajes para el LLM
        messages = [{"role": "system", "content": system_prompt}]

        # Agregar historial
        for msg in memory.get_messages():
            role = msg["role"]
            content = msg["content"]

            # Para mensajes del asistente, extraer solo to_user si es JSON
            if role == "assistant":
                try:
                    parsed = json.loads(content)
                    content = parsed.get("to_user", content)
                except:
                    pass

            messages.append({"role": role, "content": content})

        # Agregar mensaje actual
        messages.append({"role": "user", "content": message})

        try:
            # Llamar al LLM
            response = self.client.chat.completions.create(
                model=Config.LLM_MODEL,
                messages=messages,
                temperature=Config.LLM_TEMPERATURE,
                max_tokens=2048,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}} # No razonamiento 
            )

            response_content = response.choices[0].message.content

            # Parsear respuesta JSON
            response_json = self._parse_response(response_content)

            # 4. Verificar palabras prohibidas en el OUTPUT del LLM
            to_user = response_json.get("to_user", "")
            is_blocked, palabra = security.check_output(to_user)
            if is_blocked:
                return {
                    "reasoning": f"Respuesta bloqueada: LLM generó palabra prohibida '{palabra}'",
                    "to_user": security.get_random_response(),
                    "data": None,
                    "action": {"command": "none", "params": {}},
                    "blocked": True,
                    "blocked_word": palabra
                }

            return response_json

        except Exception as e:
            return {
                "reasoning": f"Error al procesar mensaje: {str(e)}",
                "to_user": "Lo siento, ocurrió un error al procesar tu mensaje. Por favor, intenta de nuevo.",
                "data": None,
                "action": {"command": "none", "params": {}}
            }

    def _parse_response(self, content: str) -> Dict:
        """
        Parsea la respuesta del LLM a JSON

        Args:
            content: Contenido de la respuesta

        Returns:
            Diccionario estructurado
        """
        try:
            # Intentar parsear directamente
            response_json = json.loads(content)

            # Validar estructura mínima
            if "reasoning" not in response_json:
                response_json["reasoning"] = "Sin razonamiento"
            if "to_user" not in response_json:
                response_json["to_user"] = content
            if "action" not in response_json:
                response_json["action"] = {"command": "none", "params": {}}

            return response_json

        except json.JSONDecodeError:
            # Si no es JSON válido, extraer JSON del contenido
            import re
            json_match = re.search(r'\{[\s\S]*\}', content)

            if json_match:
                try:
                    return json.loads(json_match.group())
                except:
                    pass

            # Fallback: crear estructura con el contenido como texto
            return {
                "reasoning": "Respuesta no estructurada del LLM",
                "to_user": content,
                "data": None,
                "action": {"command": "none", "params": {}}
            }

    def handle_chat(self, user_id: str, message: str) -> Dict:
        """
        Maneja un mensaje de chat completo

        Args:
            user_id: ID del usuario
            message: Mensaje del usuario

        Returns:
            Diccionario con la respuesta del chatbot
        """
        # Procesar mensaje
        response = self.process_message(user_id, message)

        # Guardar en memoria
        memory = self.get_or_create_memory(user_id)
        memory.add_user_message(message)
        memory.add_assistant_message(json.dumps(response, ensure_ascii=False))

        return response

    def clear_memory(self, user_id: str):
        """Limpia la memoria de un usuario"""
        if user_id in self.user_memories:
            self.user_memories[user_id].clear()


def main():
    """Demo del servicio de chatbot"""
    print("=" * 70)
    print("DEMO - SERVICIO DE CHATBOT CON RAG")
    print("=" * 70 + "\n")

    # Inicializar RAG
    rag = RAGService()

    # Intentar cargar índice existente o crear nuevo
    if not rag.load_index():
        print("Creando índice desde PDFs...")
        rag.load_documents_from_pdfs()

    if not rag.is_ready():
        print("Advertencia: El servicio RAG no está disponible.")
        print("El chatbot funcionará sin contexto de resoluciones de INDECOPI.\n")

    # Inicializar chatbot
    try:
        chatbot = ChatbotService(rag)
    except ValueError as e:
        print(f"Error: {e}")
        print("Configura las variables de entorno en .env")
        return

    # Demo interactivo
    print("\n" + "=" * 70)
    print("CHAT INTERACTIVO")
    print("=" * 70)
    print("Escribe 'salir' para terminar\n")

    user_id = "demo_user"

    while True:
        try:
            message = input("Tú: ").strip()

            if not message:
                continue

            if message.lower() in ['salir', 'exit', 'quit']:
                break

            # Procesar mensaje
            response = chatbot.handle_chat(user_id, message)

            # Mostrar respuesta
            print(f"\nAsistente: {response['to_user']}")

            # Mostrar razonamiento (debug)
            print(f"\n[Debug - Reasoning]: {response.get('reasoning', 'N/A')}")

            # Mostrar acción ejecutada
            if response.get("action_result"):
                print(f"[Debug - Action Result]: {response['action_result']}")

            print()

        except KeyboardInterrupt:
            print("\n\nInterrumpido")
            break
        except Exception as e:
            print(f"Error: {e}\n")

    print("\nDemo finalizada")


if __name__ == "__main__":
    main()
