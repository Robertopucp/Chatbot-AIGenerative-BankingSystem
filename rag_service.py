"""
Servicio RAG (Retrieval Augmented Generation) con LangChain + FAISS
Proporciona contexto relevante de las resoluciones de INDECOPI para el chatbot

- Embeddings vía API de OpenAI
- Búsqueda con umbral de similitud (RAG_SCORE_THRESHOLD)
- Búsqueda MMR (Maximal Marginal Relevance) para mayor diversidad
- Respuesta RAG directa con citación de fuentes (answer_question)
"""
from typing import List, Dict, Optional
from pathlib import Path

import numpy as np

from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_classic.text_splitter import RecursiveCharacterTextSplitter
from langchain_classic.schema import Document
from langchain_core.embeddings import Embeddings
from openai import OpenAI

from config import Config
from pdf_reader import PDFReader


class OPENAIEmbeddings(Embeddings):
    """
    Embeddings vía API de OPENAI
    endpoint compatible con OpenAI del LLM.

    Implementa la interfaz Embeddings de LangChain, por lo que se puede
    usar directamente con FAISS / Chroma.
    """

    def __init__(self, model: str = None, batch_size: int = 10):
        # OJO: el endpoint de OPENAI rechaza lotes > 10 inputs (batch size limit)
        self.model = model or Config.OPENAI_EMBEDDING_MODEL
        self.batch_size = batch_size
        self.client = OpenAI(
            api_key=Config.EMBBEDING_API_KEY
        )
        print(f"  Embeddings OPEN AI: {self.model} "
              f"(dim={Config.OPENAI_EMBEDDING_DIM}, batch={batch_size})")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Genera embeddings para una lista de textos (con batching)"""
        vectors: List[List[float]] = []

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            response = self.client.embeddings.create(model=self.model, input=batch)
            vectors.extend([item.embedding for item in response.data])

        return vectors

    def embed_query(self, text: str) -> List[float]:
        """Genera el embedding de una consulta"""
        return self.embed_documents([text])[0]


class RAGService:
    """
    Servicio de Retrieval Augmented Generation
    Usa FAISS como vector store y text-embedding-3-small para embeddings
    """

    def __init__(self, index_dir: str = None):
        
        """
        Inicializa el servicio RAG

        Args:
            index_dir: Directorio del índice FAISS (None = usa Config.FAISS_INDEX_DIR)
        """
        print("Inicializando servicio RAG...")

        # Asegurar que existen los directorios
        Config.ensure_directories()

        # Directorio del índice (permite índices separados por tema)
        self.index_dir = Path(index_dir) if index_dir else Config.FAISS_INDEX_DIR

        # Inicializar embeddings según configuración
        if Config.EMBEDDING_PROVIDER == "openai":
            print(f"  Proveedor de embeddings: OPEN AI API")
            self.embeddings = OPENAIEmbeddings()
        else:
            print(f"  Cargando modelo de embeddings: {Config.SENTENCE_TRANSFORMER_MODEL}")
            self.embeddings = HuggingFaceEmbeddings(
                model_name=Config.SENTENCE_TRANSFORMER_MODEL,
                model_kwargs={'device': 'cpu'},
                encode_kwargs={'normalize_embeddings': True}
            )

        # Inicializar lector de PDFs
        self.pdf_reader = PDFReader()

        # Vector store (se inicializa al cargar documentos)
        self.vector_store: Optional[FAISS] = None

        # Text splitter para dividir documentos en chunks
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=Config.CHUNK_SIZE,
            chunk_overlap=Config.CHUNK_OVERLAP,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )

        print("Servicio RAG inicializado\n")

    def load_documents_from_pdfs(self, pdfs_dir: str = None,
                                 file_filter: callable = None) -> int:
        """
        Carga y procesa los PDFs para crear el índice vectorial

        Args:
            pdfs_dir: Directorio con PDFs (usa Config.PDFS_DIR por defecto)
            file_filter: Función que recibe el nombre del archivo y devuelve
                         True si debe indexarse (permite indexar por subconjuntos
                         de resoluciones)

        Returns:
            Número de chunks indexados
        """
        pdfs_dir = pdfs_dir or str(Config.PDFS_DIR)

        print(f"Cargando documentos desde: {pdfs_dir}")

        # Leer PDFs (con filtro opcional)
        raw_documents = self.pdf_reader.read_pdf_folder(pdfs_dir, 
                                                        file_filter=file_filter)

        if not raw_documents:
            print("No se encontraron documentos para procesar")
            return 0

        # Convertir a documentos de LangChain
        langchain_docs = []
        
        for doc in raw_documents:
            langchain_docs.append(Document(
                page_content=doc["text"],
                metadata=doc["metadata"]
            ))

        # Dividir en chunks
        print(f"\nDividiendo {len(langchain_docs)} documentos en chunks...")
        chunks = self.text_splitter.split_documents(langchain_docs)
        print(f"  Total chunks generados: {len(chunks)}")

        # Crear índice FAISS
        print("\nCreando índice vectorial FAISS...")
        self.vector_store = FAISS.from_documents(chunks, self.embeddings)

        # Guardar índice para uso futuro
        self._save_index()

        print(f"Índice creado con {len(chunks)} chunks\n")
        return len(chunks)

    def _save_index(self):
        """Guarda el índice FAISS en disco"""
        if not self.vector_store:
            return

        try:
            # Asegurar que el directorio del índice existe
            self.index_dir.mkdir(parents=True, exist_ok=True)

            # Verificar que el directorio existe
            if not self.index_dir.exists():
                print(f"  ERROR: No se pudo crear el directorio {self.index_dir}")
                return

            index_path = str(self.index_dir)
            print(f"  Guardando índice en: {index_path}")

            # Guardar índice
            self.vector_store.save_local(index_path)
            print(f"  Índice guardado exitosamente")

        except Exception as e:
            print(f"  ERROR al guardar índice: {e}")
            print(f"  El índice se mantendrá solo en memoria (se perderá al cerrar)")

    def load_index(self) -> bool:
        """
        Carga el índice FAISS desde disco

        Returns:
            True si se cargó exitosamente
        """
        index_path = self.index_dir

        if not index_path.exists():
            print(f"No existe índice guardado en: {index_path}")
            return False

        try:
            print(f"Cargando índice desde: {index_path}")
            self.vector_store = FAISS.load_local(
                str(index_path),
                self.embeddings,
                allow_dangerous_deserialization=True
            )
            print("Índice cargado exitosamente")
            return True

        except Exception as e:
            print(f"Error al cargar índice: {e}")
            return False

    def search(self, query: str, k: int = None, threshold: float = None) -> List[Dict]:
        """
        Busca documentos relevantes para una consulta

        Args:
            query: Texto de búsqueda
            k: Número de resultados (usa Config.RAG_TOP_K por defecto)
            threshold: Umbral mínimo de similitud (0.0 a 1.0).
                       None = usa Config.RAG_SCORE_THRESHOLD.
                       0.0 = sin filtro.

        Returns:
            Lista de documentos con texto, score y metadata
        """
        if not self.vector_store:
            print("El índice no está inicializado. Carga los documentos primero.")
            return []

        k = k or Config.RAG_TOP_K

        if threshold is None:
            threshold = float(Config.RAG_SCORE_THRESHOLD)

        # Búsqueda con scores
        results = self.vector_store.similarity_search_with_score(query, k=k)

        # Formatear resultados
        formatted_results = []
        for doc, score in results:
            # FAISS retorna distancia (menor = mejor), convertimos a similitud
            similarity = 1 / (1 + score)

            # Filtro por umbral mínimo (descarta resultados de baja calidad)
            if similarity < threshold:
                continue

            formatted_results.append({
                "text": doc.page_content,
                "score": similarity,
                "metadata": doc.metadata
            })

        return formatted_results

    def search_mmr(self, query: str, k: int = None,
                   fetch_k: int = None, lambda_mult: float = None) -> List[Dict]:
        """
        Búsqueda MMR (Maximal Marginal Relevance): combina relevancia con
        diversidad para evitar resultados redundantes del mismo documento.

        Args:
            query: Texto de búsqueda
            k: Número de resultados finales
            fetch_k: Resultados candidatos a considerar (default k * 4)
            lambda_mult: 0.0 = solo diversidad, 1.0 = solo relevancia (default 0.7)

        Returns:
            Lista de documentos con texto, score y metadata
        """
        if not self.vector_store:
            print("El índice no está inicializado. Carga los documentos primero.")
            return []

        k = k or Config.RAG_TOP_K
        fetch_k = fetch_k or (k * 4)
        lambda_mult = lambda_mult if lambda_mult is not None else 0.7

        # 1. Candidatos iniciales: Top fetch_k por similitud (sin umbral)
        candidates = self.search(query, k=fetch_k, threshold=0.0)
        if not candidates:
            return []

        # 2. Vectorizar consulta y candidatos (coseno con vectores normalizados)
        query_vec = np.array(self.embeddings.embed_query(query), dtype=float)
        candidate_vecs = np.array(
            self.embeddings.embed_documents([c["text"] for c in candidates]),
            dtype=float
        )
        query_vec = query_vec / np.linalg.norm(query_vec)
        candidate_vecs = candidate_vecs / np.linalg.norm(
            candidate_vecs, axis=1, keepdims=True)

        # Similitud coseno de cada candidato con la consulta
        sim_query = candidate_vecs @ query_vec

        # 3. Selección greedy MMR:
        #    score = lambda * relevancia - (1 - lambda) * máxima similitud con ya elegidos
        selected_idx = []
        remaining = list(range(len(candidates)))

        while len(selected_idx) < k and remaining:
            best_idx, best_mmr = None, -1.0

            for i in remaining:
                relevancia = float(sim_query[i])

                if selected_idx:
                    sim_con_elegidos = candidate_vecs[i] @ candidate_vecs[selected_idx].T
                    redundancia = float(np.max(sim_con_elegidos))
                else:
                    redundancia = 0.0

                mmr = lambda_mult * relevancia - (1 - lambda_mult) * redundancia

                if mmr > best_mmr:
                    best_mmr, best_idx = mmr, i

            selected_idx.append(best_idx)
            remaining.remove(best_idx)

        # 4. Formatear resultados en el mismo formato que search()
        return [
            {**candidates[i], "score": round(float(sim_query[i]), 4)}
            for i in selected_idx
        ]

    def answer_question(self, question: str, k: int = None,
                        threshold: float = None, top_k_sources: int = 3) -> Dict:
        """
        Respuesta RAG directa: recupera contexto relevante y genera una
        respuesta con el LLM (Qwen) usando un prompt RAG estándar.

        Estructura del prompt:
            system → rol e instrucciones
            context → documentos recuperados del vector DB
            question → pregunta del usuario
            guidelines → citar fuentes, admitir desconocimiento

        Args:
            question: Pregunta del usuario
            k: Número de chunks de contexto a recuperar
            threshold: Umbral de similitud para el contexto
            top_k_sources: Cantidad de fuentes a citar en la respuesta

        Returns:
            Dict con: answer, sources (con citas) y used_context
        """
        k = k or Config.RAG_TOP_K

        # 1) Retrieval: recuperar contexto relevante
        context_chunks = self.search(question, k=k, threshold=threshold)

        if not context_chunks:
            return {
                "answer": "No encontré información relevante en los documentos para responder esta pregunta.",
                "sources": [],
                "used_context": ""
            }

        # 2) Augmented: formatear el contexto con sus fuentes
        context_text = "\n\n".join(
            f"[Contexto {i} - fuente: {c['metadata'].get('source', 'desconocida')}]\n{c['text']}"
            for i, c in enumerate(context_chunks, 1)
        )

        system_prompt = (
            "Eres un asistente a usuarios del sistema bancario peruano. Eres un asistente virtual del regulador que protege los derechos de los consumidores (INDECOPI). Responde ÚNICAMENTE con base en el "
            "contexto proporcionado. \n"
            "REGLAS:\n"
            "1. Cita la fuente de cada afirmación entre corchetes, ej: [fuente: nombre.pdf]\n"
            "2. Si la información no está en el contexto, responde que no la tienes disponible.\n"
            "3. Responde en español, de forma clara y concisa.\n"
            "4. No inventes información ni generes contenido que no esté directamente basado en el contexto proporcionado.\n"
            f"CONTEXTO:\n{context_text}\n\n"
            f"PREGUNTA: {question}"
        )

        # 3) Generation: llamar al LLM (mismo endpoint que los embeddings)
        client = OpenAI(api_key=Config.LLM_API_KEY, base_url=Config.LLM_BASE_URL)
        response = client.chat.completions.create(
            model=Config.LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            temperature=float(Config.LLM_TEMPERATURE),
            top_p=0.95,
            presence_penalty=1.5,
        )

        answer = response.choices[0].message.content

        # Fuentes para citación (top_k_sources con mayor score)
        sources = sorted(context_chunks, key=lambda c: c["score"], reverse=True)[:top_k_sources]
        sources = [
            {
                "source": c["metadata"].get("source", "desconocida"),
                "score": round(float(c["score"]), 4)
            }
            for c in sources
        ]

        return {
            "answer": answer,
            "sources": sources,
            "used_context": context_text
        }

    def get_context_for_query(self, query: str, k: int = None) -> str:
        """
        Obtiene el contexto relevante formateado para el LLM

        Args:
            query: Consulta del usuario
            k: Número de documentos a recuperar

        Returns:
            Contexto formateado como string
        """
        results = self.search(query, k)

        if not results:
            return "No se encontró información relevante en las resoluciones de INDECOPI."

        # Formatear contexto
        context_parts = []
        for i, result in enumerate(results, 1):
            source = result['metadata'].get('source', 'Desconocido')
            text = result['text']
            score = result['score']

            context_parts.append(
                f"[Documento {i} - Fuente: {source} - Relevancia: {score:.2f}]\n{text}"
            )

        return "\n\n---\n\n".join(context_parts)

    def get_stats(self) -> Dict:
        """Obtiene estadísticas del índice"""
        if not self.vector_store:
            return {
                "initialized": False,
                "document_count": 0
            }

        # FAISS no tiene un método directo para contar documentos
        # Usamos el índice interno
        try:
            doc_count = self.vector_store.index.ntotal
        except:
            doc_count = "Desconocido"

        return {
            "initialized": True,
            "document_count": doc_count,
            "embedding_provider": Config.EMBEDDING_PROVIDER,
            "embedding_model": (Config.OPENAI_EMBEDDING_MODEL
                                if Config.EMBEDDING_PROVIDER == "openai"
                                else Config.SENTENCE_TRANSFORMER_MODEL),
            "chunk_size": Config.CHUNK_SIZE,
            "chunk_overlap": Config.CHUNK_OVERLAP,
            "top_k": Config.RAG_TOP_K,
            "score_threshold": Config.RAG_SCORE_THRESHOLD
        }

    def is_ready(self) -> bool:
        """Verifica si el servicio está listo para consultas"""
        return self.vector_store is not None


def main():
    """Demo del servicio RAG"""
    print("=" * 70)
    print("DEMO - SERVICIO RAG CON LANGCHAIN + FAISS")
    print("=" * 70 + "\n")

    # Crear servicio
    rag = RAGService()

    # Intentar cargar índice existente
    if not rag.load_index():
        # Si no existe, crear desde PDFs
        print("\nCreando índice desde PDFs...\n")
        count = rag.load_documents_from_pdfs()

        if count == 0:
            print("No hay documentos para indexar. Agrega PDFs a la carpeta pdfs/")
            return

    # Mostrar estadísticas
    print("\n" + "=" * 70)
    print("ESTADÍSTICAS DEL ÍNDICE")
    print("=" * 70)
    stats = rag.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # Demo de búsqueda interactiva
    print("\n" + "=" * 70)
    print("BÚSQUEDA INTERACTIVA")
    print("=" * 70)
    print("Escribe 'salir' para terminar\n")

    while True:
        try:
            query = input("Tu consulta: ").strip()

            if not query:
                continue

            if query.lower() in ['salir', 'exit', 'quit']:
                break

            # Buscar
            print("\nBuscando...")
            results = rag.search(query, k=3)

            if not results:
                print("No se encontraron resultados\n")
                continue

            print(f"\nResultados encontrados: {len(results)}\n")

            for i, result in enumerate(results, 1):
                print(f"{i}. [Score: {result['score']:.4f}]")
                print(f"   Fuente: {result['metadata'].get('source', 'N/A')}")
                print(f"   Texto: {result['text'][:200]}...")
                print()

            # Mostrar contexto formateado
            print("-" * 40)
            print("CONTEXTO PARA LLM:")
            print("-" * 40)
            context = rag.get_context_for_query(query)
            print(context[:500] + "..." if len(context) > 500 else context)
            print()

        except KeyboardInterrupt:
            print("\n\nInterrumpido")
            break
        except Exception as e:
            print(f"Error: {e}\n")

    print("\nDemo finalizada")


if __name__ == "__main__":
    main()
