"""
Lector de PDFs para el sistema RAG
Extrae texto de archivos PDF de catálogos de productos
Adaptado del Taller Sesión 6
"""
from pathlib import Path
from typing import List, Dict
import re


class PDFReader:
    """Lee y extrae texto de archivos PDF"""

    def __init__(self):
        """Inicializa el lector de PDF"""
        try:
            from pypdf import PdfReader
            self.PdfReader = PdfReader
        except ImportError:
            raise ImportError(
                "pypdf no está instalado. Instálalo con: pip install pypdf"
            )

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """
        Extrae texto de un archivo PDF

        Args:
            pdf_path: Ruta al archivo PDF

        Returns:
            Texto extraído del PDF
        """
        try:
            reader = self.PdfReader(pdf_path)
            text = ""

            for page_num, page in enumerate(reader.pages, 1):
                page_text = page.extract_text()
                if page_text:
                    # Agregar marcador de página para mejor contexto
                    text += f"\n[Página {page_num}]\n{page_text}\n"

            # Limpiar texto
            text = self.clean_text(text)
            return text

        except Exception as e:
            print(f"Error al leer {pdf_path}: {e}")
            return ""

    def clean_text(self, text: str) -> str:
        """
        Limpia el texto extraído del PDF

        Args:
            text: Texto a limpiar

        Returns:
            Texto limpio
        """
        # Eliminar múltiples espacios
        text = re.sub(r'[ \t]+', ' ', text)

        # Eliminar múltiples saltos de línea (mantener máximo 2)
        text = re.sub(r'\n{3,}', '\n\n', text)

        # Eliminar espacios al inicio y final de líneas
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)

        # Eliminar espacios al inicio y final
        text = text.lower().strip()
        text = re.sub(r'[^\w\s]+', ' ', text)
        return text

    def read_pdf_folder(self, folder_path: str, recursive: bool = False,
                        file_filter: callable = None) -> List[Dict]:
        """
        Lee todos los PDFs de una carpeta

        Args:
            folder_path: Ruta a la carpeta con PDFs
            recursive: Si True, busca en subcarpetas también
            file_filter: Función que recibe el nombre del archivo y devuelve
                         True si debe procesarse (None = procesar todos)

        Returns:
            Lista de diccionarios con texto y metadata de cada PDF
        """
        folder = Path(folder_path)

        if not folder.exists():
            raise FileNotFoundError(f"La carpeta {folder_path} no existe")

        # Buscar archivos PDF
        if recursive:
            pdf_files = list(folder.rglob("*.pdf"))
        else:
            pdf_files = list(folder.glob("*.pdf"))

        # Aplicar filtro opcional (indexar solo ciertos archivos)
        if file_filter:
            pdf_files = [f for f in pdf_files if file_filter(f.name)]

        if not pdf_files:
            print(f"No se encontraron archivos PDF en {folder_path}")
            return []

        print(f"Encontrados {len(pdf_files)} archivos PDF")

        documents = []

        for pdf_file in pdf_files:
            print(f"  Leyendo: {pdf_file.name}...", end=" ")

            text = self.extract_text_from_pdf(str(pdf_file))

            if text:
                documents.append({
                    "text": text,
                    "metadata": {
                        "source": pdf_file.name,
                        "filepath": str(pdf_file),
                        "size_bytes": pdf_file.stat().st_size,
                        "type": "pdf",
                        "category": self._detect_category(pdf_file.name)
                    }
                })
                print(f"OK ({len(text):,} caracteres)")
            else:
                print("Sin texto extraíble")

        print(f"\nTotal documentos procesados: {len(documents)}")
        return documents

    def _detect_category(self, filename: str) -> str:
        """
        Detecta la categoría del documento basándose en el nombre

        Args:
            filename: Nombre del archivo

        Returns:
            Categoría detectada
        """
        filename_lower = filename.lower()

        if "catálogo" in filename_lower or "catalogo" in filename_lower:
            return "catalogo_productos"
        elif "precio" in filename_lower:
            return "lista_precios"
        elif "manual" in filename_lower:
            return "manual"
        elif "guia" in filename_lower or "guía" in filename_lower:
            return "guia"
        elif "anatom" in filename_lower:
            return "anatomia_humana"
        else:
            return "documento_general"

    def get_pdf_info(self, pdf_path: str) -> Dict:
        """
        Obtiene información detallada de un PDF

        Args:
            pdf_path: Ruta al PDF

        Returns:
            Diccionario con información del PDF
        """
        try:
            reader = self.PdfReader(pdf_path)

            info = {
                "filepath": pdf_path,
                "num_pages": len(reader.pages),
                "metadata": {}
            }

            # Extraer metadata del PDF si existe
            if reader.metadata:
                info["metadata"] = {
                    "title": reader.metadata.title if reader.metadata.title else None,
                    "author": reader.metadata.author if reader.metadata.author else None,
                    "subject": reader.metadata.subject if reader.metadata.subject else None,
                    "creator": reader.metadata.creator if reader.metadata.creator else None,
                }

            return info

        except Exception as e:
            return {"error": str(e), "filepath": pdf_path}


def main():
    """Función de prueba"""
    from config import Config

    print("=" * 70)
    print("LECTOR DE PDFs - TALLER SESIÓN 7")
    print("=" * 70 + "\n")

    # Crear lector
    reader = PDFReader()

    # Verificar carpeta de PDFs
    pdfs_dir = Config.PDFS_DIR
    print(f"Buscando PDFs en: {pdfs_dir}\n")

    try:
        documents = reader.read_pdf_folder(str(pdfs_dir), recursive=False)

        if documents:
            print("\n" + "=" * 70)
            print("DOCUMENTOS LEÍDOS")
            print("=" * 70 + "\n")

            for i, doc in enumerate(documents, 1):
                print(f"{i}. {doc['metadata']['source']}")
                print(f"   Categoría: {doc['metadata']['category']}")
                print(f"   Tamaño: {doc['metadata']['size_bytes']:,} bytes")
                print(f"   Caracteres: {len(doc['text']):,}")

                # Vista previa (primeros 200 caracteres)
                preview = doc['text'][:200].replace('\n', ' ')
                print(f"   Vista previa: {preview}...")
                print()

    except FileNotFoundError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Error inesperado: {e}")


if __name__ == "__main__":
    main()
