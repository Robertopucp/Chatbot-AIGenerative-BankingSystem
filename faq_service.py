"""
Servicio de FAQ (Preguntas Frecuentes) para el Chatbot INDECOPI

Compara la consulta del usuario contra un banco fijo de preguntas
frecuentes usando similitud coseno de embeddings. Si el score del mejor
match supera FAQ_SCORE_THRESHOLD, se responde directamente con la
respuesta de esa FAQ (sin tocar los PDFs ni llamar al LLM). Si no supera
el umbral, el flujo continúa hacia RAG + LLM (ver llm_service.py).
"""
from typing import List, Dict, Optional

import numpy as np
from langchain_core.embeddings import Embeddings

from config import Config


# Banco de preguntas frecuentes: pregunta "canónica" + respuesta fija.
FAQ_ITEMS: List[Dict[str, str]] = [
    {
        "question": "Cuáles son las funciones principales de INDECOPI",
        "answer": (
            "Es el organismo peruano que defiende la libre y leal competencia en el "
            "mercado, protege los derechos de los consumidores, administra el sistema "
            "de propiedad intelectual (marcas, patentes, derechos de autor), corrige "
            "distorsiones del mercado (dumping, subsidios), supervisa aspectos del "
            "comercio exterior, y protege el crédito. En resumen: regula que el mercado "
            "funcione de forma justa y competitiva, y defiende al consumidor."
        ),
    },
    {
        "question": "Qué denuncias de usuario o consumidor atiende INDECOPI",
        "answer": (
            "Reclamos y denuncias sobre productos y servicios defectuosos, publicidad "
            "engañosa, incumplimiento de garantías, cobros indebidos, negativa a "
            "atender reclamos, y casos sectoriales específicos: telecomunicaciones, "
            "electricidad y combustibles, transporte, agua y saneamiento, salud, "
            "banca/seguros/pensiones, y educación. También atiende temas de "
            "competencia desleal y de propiedad intelectual (marcas, derechos de autor)."
        ),
    },
    {
        "question": "Dónde queda la sede central de INDECOPI",
        "answer": "Calle De la Prosa 104, San Borja, Lima.",
    },
    {
        "question": "Cuál es el número telefónico de INDECOPI",
        "answer": "Lima: (511) 224-7777. Provincias (línea gratuita): 0-800-4-4040.",
    },
    {
        "question": "Cuál es el horario de atención de INDECOPI",
        "answer": "Lunes a viernes, de 8:30 a.m. a 4:30 p.m.",
    },
    {
        "question": "Cómo presento una denuncia ante INDECOPI",
        "answer": (
            "Primero, reclama directamente con el proveedor/empresa (tiene 30 días "
            "para responder; guarda boletas y comunicaciones). Si no resuelve, "
            "presenta el reclamo ante INDECOPI a través de su plataforma virtual "
            "(indicando el sector y adjuntando tus documentos), o de forma presencial "
            "en sus oficinas o en un Centro MAC. INDECOPI notifica al proveedor y "
            "convoca a una etapa de mediación/conciliación. Si no hay acuerdo, puedes "
            "presentar una denuncia formal ante el Órgano Resolutivo de Procedimientos "
            "Sumarísimos o la Comisión de Protección al Consumidor (esto tiene una "
            "tasa, alrededor de S/ 36)."
        ),
    },
]


class FAQService:
    """
    Búsqueda por similitud de embeddings sobre un set fijo de FAQ.
    Reutiliza el mismo objeto Embeddings que RAGService para no duplicar
    configuración de proveedor/API key.
    """

    def __init__(self, embeddings: Embeddings, threshold: float = None):
        self.embeddings = embeddings
        self.threshold = threshold if threshold is not None else Config.FAQ_SCORE_THRESHOLD
        self.items = FAQ_ITEMS

        print(f"Inicializando servicio FAQ ({len(self.items)} preguntas, umbral={self.threshold})...")
        vectors = np.array(
            self.embeddings.embed_documents([item["question"] for item in self.items]),
            dtype=float
        )
        self._question_vecs = self._normalize(vectors)
        print("Servicio FAQ inicializado\n")

    @staticmethod
    def _normalize(vecs: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vecs / norms

    def match(self, query: str) -> Optional[Dict]:
        """
        Compara la consulta contra todas las preguntas de la FAQ.

        Returns:
            Dict {question, answer, score} con el mejor match si su score
            de similitud coseno supera el umbral, o None si ninguno lo supera.
        """
        if not self.items:
            return None

        query_vec = np.array(self.embeddings.embed_query(query), dtype=float)
        norm = np.linalg.norm(query_vec)
        if norm > 0:
            query_vec = query_vec / norm

        sims = self._question_vecs @ query_vec
        best_idx = int(np.argmax(sims))
        best_score = float(sims[best_idx])

        if best_score < self.threshold:
            return None

        item = self.items[best_idx]
        return {
            "question": item["question"],
            "answer": item["answer"],
            "score": round(best_score, 4),
        }
