import httpx
import hashlib
import fitz  # PyMuPDF
from typing import Tuple, Optional
from utils.logging import get_logger

logger = get_logger("pdf_parser")

class PDFParser:
    """
    Utility class for downloading PDFs, computing their SHA256 hashes,
    and extracting text using PyMuPDF (fitz).
    """

    @staticmethod
    def compute_sha256(data: bytes) -> str:
        """Computes the SHA256 hash of raw bytes."""
        return hashlib.sha256(data).hexdigest()

    @classmethod
    def download_and_extract(cls, pdf_url: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Downloads a PDF from the given URL.
        Returns a tuple: (extracted_text, sha256_hash).
        If download or parsing fails, returns (None, None).
        """
        logger.info(f"Downloading PDF from: {pdf_url}")
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        try:
            # Download PDF using httpx
            with httpx.Client(headers=headers, follow_redirects=True, timeout=30.0, verify=False) as client:
                response = client.get(pdf_url)
                if response.status_code != 200:
                    logger.error(f"Failed to download PDF. Status: {response.status_code}")
                    return None, None
                
                pdf_bytes = response.content
                
            # Compute hash of the PDF file
            pdf_hash = cls.compute_sha256(pdf_bytes)
            logger.info(f"PDF download successful. Hash: {pdf_hash}")
            
            # Extract text using PyMuPDF (fitz)
            text_parts = []
            with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
                logger.info(f"PDF pages count: {len(doc)}")
                for i, page in enumerate(doc):
                    page_text = page.get_text()
                    text_parts.append(page_text)
                    
            extracted_text = "\n".join(text_parts).strip()
            logger.info(f"Extracted {len(extracted_text)} characters of text from PDF.")
            
            return extracted_text, pdf_hash
            
        except Exception as e:
            logger.error(f"Error during PDF processing for {pdf_url}: {e}")
            return None, None
