import os
# Fix for Windows symlink error in huggingface_hub
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"

from src.logger import logger
from src.config import load_config, project_path

def convert_to_markdown(input_path: str, output_dir: str = "parsed") -> str:
    from docling.document_converter import DocumentConverter
    from docling.datamodel.base_models import InputFormat

    logger.info(f"Starting parsing of {input_path}...")

    config = load_config()
    do_ocr = config.get("do_ocr", False)

    logger.info(f"OCR enabled from config: {do_ocr}")

    converter = DocumentConverter()

    # Modify options for PDF after initialization
    if InputFormat.PDF in converter.format_to_options:
        converter.format_to_options[InputFormat.PDF].pipeline_options.do_ocr = do_ocr

    result = converter.convert(input_path)
    md_content = result.document.export_to_markdown()

    abs_output_dir = project_path(output_dir) if not os.path.isabs(output_dir) else output_dir
    os.makedirs(abs_output_dir, exist_ok=True)
    filename = os.path.basename(input_path)
    name, _ = os.path.splitext(filename)
    output_path = os.path.join(abs_output_dir, f"{name}.md")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    logger.info(f"Saved parsed markdown to {output_path}")
    return output_path

def split_pdf(input_path: str, pages_per_file: int = 20, output_dir: str = "input") -> list[str]:
    from pypdf import PdfReader, PdfWriter

    if pages_per_file <= 0:
        raise ValueError("pages_per_file must be greater than 0.")

    logger.info(f"Splitting {input_path} every {pages_per_file} pages...")

    reader = PdfReader(input_path)
    total_pages = len(reader.pages)

    filename = os.path.basename(input_path)
    name, ext = os.path.splitext(filename)

    output_files = []

    abs_output_dir = project_path(output_dir) if not os.path.isabs(output_dir) else output_dir
    os.makedirs(abs_output_dir, exist_ok=True)

    for start in range(0, total_pages, pages_per_file):
        writer = PdfWriter()
        end = min(start + pages_per_file, total_pages)

        for page_idx in range(start, end):
            writer.add_page(reader.pages[page_idx])

        output_filename = f"{name}_part{start // pages_per_file + 1}{ext}"
        output_path = os.path.join(abs_output_dir, output_filename)

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
