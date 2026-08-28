"""
Configuración del Taller Sesión 7
Sistema RAG + Chatbot Autónomo con registro de ventas
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()


class Config:
    """Configuración centralizada del proyecto"""

    # ===== RUTAS =====
    BASE_DIR = Path(__file__).parent
    PDFS_DIR = BASE_DIR / "pdfs" / "Resoluciones_INDECOPI"
    DATA_DIR = BASE_DIR / "data"
    # VENTAS_CSV = DATA_DIR / "ventas.csv"
    # INVENTARIO_JSON = DATA_DIR / "inventario.json"

    # ===== LLM - Qwen de Alibaba =====
    # Usa la API compatible con OpenAI
    LLM_API_KEY = os.getenv("HF_API_KEY", "")
    EMBBEDING_API_KEY = os.getenv("OPENAI_API_KEY", "")
    LLM_BASE_URL = os.getenv("HF_BASE_URL", "https://router.huggingface.co/v1")
    LLM_MODEL = os.getenv("LLM_MODEL", "Qwen/Qwen3.5-9B")
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))

    # ===== EMBEDDINGS =====
    # Proveedor de embeddings:
    #   "openai"                = API text-embedding-3 (endpoint de OpenAI)
    #   "sentence-transformers" = modelo local y gratuito
    
    EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "openai")


    # Embeddings vía API de OPENAI (text-embedding-3-small)
    OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    OPENAI_EMBEDDING_DIM = int(os.getenv("OPENAI_EMBEDDING_DIM", "1536"))

    # Para Sentence Transformers (local, gratuito)
    SENTENCE_TRANSFORMER_MODEL = os.getenv(
        "SENTENCE_TRANSFORMER_MODEL",
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )

    # ===== RAG =====
    # Configuración de chunks para procesamiento de PDFs
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))

    # Número de documentos a recuperar en búsqueda
    RAG_TOP_K = int(os.getenv("RAG_TOP_K", "3"))

    # Umbral mínimo de similitud
    RAG_SCORE_THRESHOLD = float(os.getenv("RAG_SCORE_THRESHOLD", "0.5"))

    # Directorio para el índice FAISS
    FAISS_INDEX_DIR = DATA_DIR / "faiss_index"

    # ===== FAQ =====
    # Umbral mínimo de similitud coseno contra el banco de preguntas
    # frecuentes. Si el mejor match la supera, se responde directo con la
    # respuesta de la FAQ (sin usar RAG/LLM). Ver faq_service.py.
    FAQ_SCORE_THRESHOLD = float(os.getenv("FAQ_SCORE_THRESHOLD", "0.5"))

    # ===== SERVIDOR =====
    SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
    SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))

    # ===== MEMORIA =====
    MEMORY_K_MESSAGES = int(os.getenv("MEMORY_K_MESSAGES", "7"))

    @classmethod
    def validate(cls) -> bool:
        """Valida que la configuración sea correcta"""
        errors = []

        if not cls.LLM_API_KEY:
            errors.append("ALIBABA_API_KEY no está configurada")

        if not cls.PDFS_DIR.exists():
            errors.append(f"Directorio de PDFs no existe: {cls.PDFS_DIR}")

        if errors:
            print("Errores de configuración:")
            for error in errors:
                print(f"  - {error}")
            return False

        return True

    @classmethod
    def print_config(cls):
        """Imprime la configuración actual"""
        print("\n" + "=" * 60)
        print("CONFIGURACIÓN CHAT-BOT PROJECT")
        print("=" * 60)
        print(f"LLM Model: {cls.LLM_MODEL}")
        print(f"LLM Base URL: {cls.LLM_BASE_URL}")
        api_preview = cls.LLM_API_KEY[:10] + "..." if cls.LLM_API_KEY else "NO CONFIGURADA"
        print(f"LLM API Key: {api_preview}")
        
        print("\n" + "=" * 60)
        print(f"\nEmbedding Provider: {cls.EMBEDDING_PROVIDER}")

        if cls.EMBEDDING_PROVIDER == "openai":
            print(f"Embedding Model: {cls.OPENAI_EMBEDDING_MODEL}")
            print(f"Embedding Dim: {cls.OPENAI_EMBEDDING_DIM}")
            api_embedding = cls.EMBBEDING_API_KEY[:10] + "..." if cls.EMBBEDING_API_KEY else "NO CONFIGURADA"
            print(f"Embedding API Key: {api_embedding}")
        else:
            print(f"Embedding Model: {cls.SENTENCE_TRANSFORMER_MODEL}")
        print(f"\nRAG Top K: {cls.RAG_TOP_K}")
        print(f"Chunk Size: {cls.CHUNK_SIZE}")
        print(f"Chunk Overlap: {cls.CHUNK_OVERLAP}")
        print(f"\nPDFs Directory: {cls.PDFS_DIR}")
        print(f"Data Directory: {cls.DATA_DIR}")
        print("=" * 60 + "\n")

    @classmethod
    def ensure_directories(cls):
        """Asegura que los directorios necesarios existan"""
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.FAISS_INDEX_DIR.mkdir(parents=True, exist_ok=True)
        if not cls.PDFS_DIR.exists():
            cls.PDFS_DIR.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    Config.print_config()
    print("Validando configuración...")
    if Config.validate():
        print("Configuración válida")
    else:
        print("Hay errores en la configuración")
