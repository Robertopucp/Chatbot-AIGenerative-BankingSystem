"""
FastAPI Application - Chatbot RAG INDECOPI

Endpoints:
- POST /chat - Enviar mensaje al chatbot
- POST /search - Búsqueda RAG directa
"""
from datetime import datetime
from typing import List

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from config import Config
from models import (
    ChatRequest, SearchRequest,
    ChatResponse, SearchResponse, SearchResult,
    HealthResponse
)
from rag_service import RAGService
from llm_service import ChatbotService

# ===== INICIALIZACIÓN =====

# Asegurar que existen los directorios necesarios
Config.ensure_directories()

# Inicializar servicio RAG
print("\n" + "=" * 60)
print("INICIALIZANDO SERVICIOS")
print("=" * 60 + "\n")

rag_service = RAGService()

# Intentar cargar índice existente o crear nuevo
if not rag_service.load_index():
    print("Creando índice desde PDFs...")
    count = rag_service.load_documents_from_pdfs()
    if count == 0:
        print("ADVERTENCIA: No hay PDFs para indexar")
        print(f"Agrega PDFs a: {Config.PDFS_DIR}\n")

# Inicializar servicio de chatbot
chatbot_service = None
try:
    chatbot_service = ChatbotService(rag_service)
except ValueError as e:
    print(f"ADVERTENCIA: {e}")
    print("El endpoint /chat no estará disponible\n")

# Configurar rate limiter
limiter = Limiter(key_func=get_remote_address)

# Crear aplicación FastAPI
app = FastAPI(
    title="Chatbot RAG - INDECOPI",
    description="""
    Asistente virtual con RAG (Retrieval Augmented Generation) sobre
    resoluciones de INDECOPI, para informar a usuarios del sistema
    bancario peruano sobre sus derechos de protección al consumidor.

    ## Características
    - **RAG**: Búsqueda semántica en resoluciones de INDECOPI (PDFs)
    - **Chatbot**: Conversación natural con Qwen (Hugging Face)
    """,
    version="1.0.0",
    contact={
        "name": "Diplomado IA",
        "url": "https://github.com/diplomado-ia"
    }
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configurar rate limiter en la aplicación
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ===== ENDPOINTS PRINCIPALES =====

@app.get("/", response_class=HTMLResponse, tags=["General"])
@limiter.limit("100/minute")
def root(request: Request):
    """Sirve la interfaz web de prueba"""
    try:
        html_file = Config.BASE_DIR / "index.html"
        if html_file.exists():
            return FileResponse(html_file)
        else:
            return HTMLResponse(content="""
                <html>
                    <body>
                        <h1>Chatbot RAG API</h1>
                        <p>Interfaz web no encontrada. Accede a <a href="/docs">/docs</a> para ver la documentación de la API.</p>
                    </body>
                </html>
            """)
    except:
        return HTMLResponse(content="""
            <html>
                <body>
                    <h1>Chatbot RAG API</h1>
                    <p>Accede a <a href="/docs">/docs</a> para ver la documentación de la API.</p>
                </body>
            </html>
        """)


@app.get("/api", tags=["General"])
@limiter.limit("100/minute")
def api_info(request: Request):
    """Endpoint con información de la API en JSON"""
    return {
        "title": "Chatbot RAG - INDECOPI",
        "version": "1.0.0",
        "description": "Asistente con RAG sobre resoluciones de INDECOPI",
        "endpoints": {
            "chat": "POST /chat",
            "search": "POST /search",
            "health": "GET /health",
            "docs": "GET /docs"
        },
        "rag_ready": rag_service.is_ready(),
        "chatbot_ready": chatbot_service is not None
    }


@app.get("/health", response_model=HealthResponse, tags=["General"])
@limiter.limit("100/minute")
def health_check(request: Request):
    """Verifica el estado del servicio"""
    return HealthResponse(
        status="healthy",
        service="chatbot-rag-api",
        rag_ready=rag_service.is_ready(),
        timestamp=datetime.now().isoformat()
    )


# ===== ENDPOINTS DE CHAT =====

@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
@limiter.limit("20/minute")
def chat(request: Request, data: ChatRequest):
    """
    Envía un mensaje al chatbot

    El chatbot responde preguntas sobre derechos del consumidor y
    resoluciones de INDECOPI usando el contexto recuperado por RAG.
    """
    if not chatbot_service:
        raise HTTPException(
            status_code=503,
            detail="Servicio de chatbot no disponible. Configura HF_API_KEY en .env"
        )

    try:
        response = chatbot_service.handle_chat(data.user_id, data.message)
        return ChatResponse(**response)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al procesar mensaje: {str(e)}"
        )


@app.delete("/chat/{user_id}", tags=["Chat"])
@limiter.limit("10/minute")
def clear_chat_history(request: Request, user_id: str):
    """Limpia la memoria de conversación de un usuario"""
    if chatbot_service:
        chatbot_service.clear_memory(user_id)

    return {"message": f"Historial de {user_id} eliminado"}


# ===== ENDPOINTS DE BÚSQUEDA RAG =====

@app.post("/search", response_model=SearchResponse, tags=["RAG"])
@limiter.limit("30/minute")
def search_documents(request: Request, data: SearchRequest):
    """
    Búsqueda semántica en las resoluciones de INDECOPI

    Utiliza FAISS para encontrar los documentos más relevantes
    basándose en similitud de embeddings.
    """
    if not rag_service.is_ready():
        raise HTTPException(
            status_code=503,
            detail="Servicio RAG no disponible. Indexa los PDFs primero."
        )

    results = rag_service.search(data.query, k=data.top_k)

    return SearchResponse(
        query=data.query,
        results=[SearchResult(**r) for r in results],
        total=len(results)
    )


@app.post("/rag/reindex", tags=["RAG"])
@limiter.limit("5/minute")
def reindex_documents(request: Request):
    """Reindexa todos los PDFs"""
    count = rag_service.load_documents_from_pdfs()

    return {
        "message": f"Reindexación completada",
        "chunks_indexed": count,
        "pdfs_dir": str(Config.PDFS_DIR)
    }


@app.get("/rag/stats", tags=["RAG"])
@limiter.limit("60/minute")
def get_rag_stats(request: Request):
    """Obtiene estadísticas del índice RAG"""
    return rag_service.get_stats()


# ===== MAIN =====

if __name__ == "__main__":
    import uvicorn

    print("\n" + "=" * 60)
    print("INICIANDO SERVIDOR")
    print("=" * 60)
    Config.print_config()

    uvicorn.run(
        app,
        host=Config.SERVER_HOST,
        port=Config.SERVER_PORT
    )
