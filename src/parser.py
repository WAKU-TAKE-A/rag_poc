import os
import json
# Fix for Windows symlink error in huggingface_hub
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"

from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import InputFormat
from pypdf import PdfReader, PdfWriter
from src.logger import logger

def convert_to_markdown(input_path: str, output_dir: str = "parsed") -> str:
    logger.info(f"Starting parsing of {input_path}...")
    
    # Load config for OCR
    do_ocr = False
    config_path = "config.json"
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                do_ocr = config.get("do_ocr", False)
        except Exception:
            pass
            
    logger.info(f"OCR enabled from config: {do_ocr}")
    
    converter = DocumentConverter()
    
    # Modify options for PDF after initialization
    if InputFormat.PDF in converter.format_to_options:
        converter.format_to_options[InputFormat.PDF].pipeline_options.do_ocr = do_ocr
        
    result = converter.convert(input_path)
    md_content = result.document.export_to_markdown()
    
    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.basename(input_path)
    name, _ = os.path.splitext(filename)
    output_path = os.path.join(output_dir, f"{name}.md")
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md_content)
        
    logger.info(f"Saved parsed markdown to {output_path}")
    return output_path

def split_pdf(input_path: str, pages_per_file: int = 20, output_dir: str = "input") -> list[str]:
    if pages_per_file <= 0:
        raise ValueError("pages_per_file must be greater than 0.")

    logger.info(f"Splitting {input_path} every {pages_per_file} pages...")
    
    reader = PdfReader(input_path)
    total_pages = len(reader.pages)
    
    filename = os.path.basename(input_path)
    name, ext = os.path.splitext(filename)
    
    output_files = []
    
    for start in range(0, total_pages, pages_per_file):
        writer = PdfWriter()
        end = min(start + pages_per_file, total_pages)
        
        for page_idx in range(start, end):
            writer.add_page(reader.pages[page_idx])
            
        output_filename = f"{name}_part{start // pages_per_file + 1}{ext}"
        output_path = os.path.join(output_dir, output_filename)
        
        with open(output_path, "wb") as f:
            writer.write(f)
            
        logger.info(f"Saved {output_path} (Pages {start+1} to {end})")
        output_files.append(output_path)
        
    # Rename original file to avoid re-processing by sync
    org_path = input_path + ".org"
    try:
        os.rename(input_path, org_path)
        logger.info(f"Renamed original file {input_path} to {org_path}")
    except Exception as e:
        logger.warning(f"Failed to rename original file {input_path}: {e}")
        
    return output_files
