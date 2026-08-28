"""
Módulo de Seguridad para el Chatbot
Filtra palabras prohibidas en entrada y salida
"""
import random
import unicodedata


def _normalizar(texto: str) -> str:
    """Minúsculas y sin tildes/diacríticos, para que 'víctima' y 'victima' matcheen igual"""
    texto = texto.lower()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


# Lista limitada de palabras clave prohibidas
palabras_in = [
    "ilicito",
    "hacker",
    "datos personales",
    "dni",
    "multas"
]

palabras_out = list(palabras_in)

# Respuestas genéricas cuando se detecta contenido prohibido
responses = [
    "Lo siento, pero no puedo responder a tu pregunta.",
    "Por ahora no puedo responder a tu pregunta.",
    "Lo siento, no se peude brindar información de montos de multas o sanciones.",
    "Lo siento, no puedo generar una respuesta para tu pregunta.",
    "Lo siento, mi función no es responder ese tipo de consultas.",
    "Disculpa, esa consulta está fuera de mi ámbito de asistencia."
]


def get_random_response() -> str:
    """Obtiene una respuesta aleatoria de bloqueo"""
    return random.choice(responses)


def check_input(message: str) -> tuple[bool, str]:
    """
    Verifica si el mensaje del usuario contiene palabras prohibidas

    Args:
        message: Mensaje del usuario

    Returns:
        Tupla (is_blocked, palabra_detectada)
    """
    message_norm = _normalizar(message)

    for palabra in palabras_in:
        if _normalizar(palabra) in message_norm:
            return True, palabra

    return False, ""


def check_output(response: str) -> tuple[bool, str]:
    """
    Verifica si la respuesta del LLM contiene palabras prohibidas

    Args:
        response: Respuesta del LLM

    Returns:
        Tupla (is_blocked, palabra_detectada)
    """
    response_norm = _normalizar(response)

    for palabra in palabras_out:
        if _normalizar(palabra) in response_norm:
            return True, palabra

    return False, ""
