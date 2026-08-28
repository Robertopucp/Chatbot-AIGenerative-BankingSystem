"""
Lector de PDFs para el sistema RAG
Extrae texto de las resoluciones de INDECOPI
"""
from pathlib import Path
from typing import List, Dict
import re


# Patrones para redactar datos sensibles de las resoluciones antes de
# indexarlas: nombres de personas y lugar de los hechos denunciados.
# DNI, montos de dinero y fechas se resuelven aparte, con un solo paso
# que elimina todos los dígitos del texto (ver _redact_sensitive_data).
# Es una limpieza best-effort a nivel de texto (no reemplaza el filtro
# de security.py, que sigue siendo la última barrera sobre lo que ve el
# usuario en el chat).
_PLACEHOLDER = "[DATO PROTEGIDO]"

# Nombres de personas: texto en mayúscula inicial (o todo en mayúsculas,
# formato común en resoluciones peruanas) después de una etiqueta típica
# (denunciante, Sr./Sra., "nombres y apellidos", etc.). La etiqueta es
# insensible a mayúsculas/minúsculas vía (?i:...), pero el grupo
# capturado no, para no confundir palabras comunes con nombres propios.
_NAME_LABEL_PATTERN = re.compile(
    r'(?i:denunciante|denunciad[oa]|demandante|demandad[oa]|recurrente|'
    r'apelante|infractor|sr\.|sra\.|srta\.|señor|señora|don|doña|'
    r'nombres?\s+y\s+apellidos)\s*:?\s+'
    r'(?P<nombre>[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ]*'
    r'(?:\s+[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ]*){1,4})'
)

# Lugar de los hechos: texto tras frases típicas de ubicación
_PLACE_PATTERN = re.compile(
    r'(?:en la ciudad de|en el distrito de|en la provincia de|'
    r'en el departamento de|domiciliad[oa] en|domicilio en|'
    r'lugar de los hechos)\s*:?\s+'
    r'(?P<lugar>[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ.\s]{2,60}?)(?=[.,;\n]|$)',
    re.IGNORECASE
)


def _redact_named_group(match: re.Match) -> str:
    """Conserva la etiqueta (ej. 'denunciante:') y redacta solo el grupo capturado"""
    start, end = match.span()
    group_start, group_end = match.span(1)
    return match.string[start:group_start] + _PLACEHOLDER + match.string[group_end:end]


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

    def _redact_sensitive_data(self, text: str) -> str:
        """
        Redacta de las resoluciones los datos sensibles antes de indexarlas:
        nombres de personas y lugar de los hechos (por etiqueta), y todos
        los dígitos del texto (cubre DNI, montos de dinero y fechas de
        una sola vez). Se aplica sobre el texto original (con mayúsculas
        y puntuación intactas) porque los patrones de nombres y lugar
        dependen de ese formato.

        Args:
            text: Texto original extraído del PDF

        Returns:
            Texto sin nombres, lugares ni dígitos
        """
        text = _NAME_LABEL_PATTERN.sub(_redact_named_group, text)
        text = _PLACE_PATTERN.sub(_redact_named_group, text)
        # Quitar todo dígito: cubre DNI, montos de dinero y fechas de un
        # solo golpe (también borra números de resolución/expediente).
        text = re.sub(r'\d+', ' ', text)
        return text

    def clean_text(self, text: str) -> str:
        """
        Redacta datos sensibles y limpia el texto extraído del PDF

        Args:
            text: Texto a limpiar

        Returns:
            Texto limpio, sin datos sensibles
        """
        # Redactar datos sensibles primero (necesita mayúsculas/puntuación)
        text = self._redact_sensitive_data(text)

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
    print("LECTOR DE PDFs - RESOLUCIONES INDECOPI")
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
