"""
Modelos Pydantic para Requests y Responses de la API
Taller Sesión 7 - Sistema RAG + Chatbot Autónomo
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# ===== REQUEST MODELS =====

class CreateUserRequest(BaseModel):
    """Request para crear un usuario"""
    user_id: str = Field(..., description="ID único del usuario")
    name: str = Field(..., description="Nombre del usuario")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user123",
                "name": "Juan Pérez"
            }
        }


class ChatRequest(BaseModel):
    """Request para enviar un mensaje al chatbot"""
    user_id: str = Field(..., description="ID del usuario")
    message: str = Field(..., description="Mensaje del usuario")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user123",
                "message": "¿Qué productos tienen disponibles?"
            }
        }


class SearchRequest(BaseModel):
    """Request para búsqueda RAG"""
    query: str = Field(..., description="Consulta de búsqueda")
    top_k: int = Field(default=3, description="Número de resultados")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "laptops con buena memoria",
                "top_k": 3
            }
        }


class SaleRequest(BaseModel):
    """Request para registrar una venta manualmente"""
    cliente: str = Field(..., description="Nombre del cliente")
    productos: List[str] = Field(..., description="Lista de productos")
    cantidades: List[int] = Field(..., description="Cantidades de cada producto")
    precios_unitarios: List[float] = Field(..., description="Precios unitarios")
    metodo_pago: str = Field(default="efectivo", description="Método de pago")

    class Config:
        json_schema_extra = {
            "example": {
                "cliente": "María García",
                "productos": ["Laptop HP", "Mouse Logitech"],
                "cantidades": [1, 2],
                "precios_unitarios": [15000.0, 350.0],
                "metodo_pago": "tarjeta"
            }
        }


class InventoryUpdateRequest(BaseModel):
    """Request para actualizar inventario"""
    producto: str = Field(..., description="Nombre del producto")
    stock: int = Field(..., description="Nueva cantidad en stock")

    class Config:
        json_schema_extra = {
            "example": {
                "producto": "Laptop HP",
                "stock": 15
            }
        }


# ===== RESPONSE MODELS =====

class UserResponse(BaseModel):
    """Response de información de usuario"""
    user_id: str
    name: str
    created_at: str


class ActionParams(BaseModel):
    """Parámetros de una acción"""
    cliente: Optional[str] = None
    productos: Optional[List[str]] = None
    cantidades: Optional[List[int]] = None
    total: Optional[float] = None
    filtro: Optional[str] = None
    producto: Optional[str] = None


class Action(BaseModel):
    """Acción a ejecutar"""
    command: str = Field(default="none", description="Comando de la acción")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict)


class OrderData(BaseModel):
    """Datos de una orden/venta"""
    cliente: Optional[str] = None
    productos: Optional[List[str]] = None
    cantidades: Optional[List[int]] = None
    precios_unitarios: Optional[List[float]] = None
    metodo_pago: Optional[str] = None


class ActionResult(BaseModel):
    """Resultado de una acción ejecutada"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    """Response del chatbot"""
    reasoning: str = Field(..., description="Razonamiento interno del LLM")
    to_user: str = Field(..., description="Respuesta para mostrar al usuario")
    data: Optional[OrderData] = Field(default=None, description="Datos de la orden si aplica")
    action: Optional[Action] = Field(default=None, description="Acción ejecutada")
    action_result: Optional[ActionResult] = Field(default=None, description="Resultado de la acción")
    blocked: Optional[bool] = Field(default=False, description="Si el mensaje fue bloqueado por seguridad")
    blocked_word: Optional[str] = Field(default=None, description="Palabra que causó el bloqueo")

    class Config:
        json_schema_extra = {
            "example": {
                "reasoning": "El usuario pregunta por laptops. Buscaré en el catálogo.",
                "to_user": "Tenemos varias laptops disponibles. La HP Pavilion tiene 16GB RAM...",
                "data": None,
                "action": {"command": "none", "params": {}},
                "action_result": None,
                "blocked": False,
                "blocked_word": None
            }
        }


class SearchResult(BaseModel):
    """Resultado de búsqueda RAG"""
    text: str
    score: float
    metadata: Dict[str, Any]


class SearchResponse(BaseModel):
    """Response de búsqueda RAG"""
    query: str
    results: List[SearchResult]
    total: int


class SaleResponse(BaseModel):
    """Response de registro de venta"""
    success: bool
    venta_id: Optional[str] = None
    total: Optional[float] = None
    message: str


class SaleRecord(BaseModel):
    """Registro de una venta"""
    venta_id: str
    fecha: str
    cliente: str
    productos: List[str]
    cantidades: List[int]
    total: float
    metodo_pago: str
    status: str


class SalesListResponse(BaseModel):
    """Response de lista de ventas"""
    total_ventas: int
    monto_total: float
    ventas: List[SaleRecord]


class InventoryItem(BaseModel):
    """Item de inventario"""
    producto: str
    stock: int


class InventoryResponse(BaseModel):
    """Response de inventario"""
    total_productos: int
    items: List[InventoryItem]


class MessageRecord(BaseModel):
    """Registro de un mensaje"""
    role: str
    content: str
    timestamp: str


class ChatHistoryResponse(BaseModel):
    """Response del historial de chat"""
    user_id: str
    total_messages: int
    messages: List[MessageRecord]


class HealthResponse(BaseModel):
    """Response de health check"""
    status: str
    service: str
    rag_ready: bool
    timestamp: str


class StatsResponse(BaseModel):
    """Response de estadísticas del sistema"""
    ventas: Dict[str, Any]
    inventario: Dict[str, Any]
    rag: Dict[str, Any]
    usuarios: int


class ErrorResponse(BaseModel):
    """Response de error"""
    detail: str
    error_type: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "detail": "Usuario no encontrado",
                "error_type": "NotFound"
            }
        }
