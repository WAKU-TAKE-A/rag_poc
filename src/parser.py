from docling.document_converter import DocumentConverter
import os

def convert_to_markdown(input_path: str, output_dir: str = "parsed") -> str:
    print(f"Starting parsing of {input_path}...")
    converter = DocumentConverter()
    result = converter.convert(input_path)
    md_content = result.document.export_to_markdown()
    
    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.basename(input_path)
    name, _ = os.path.splitext(filename)
    output_path = os.path.join(output_dir, f"{name}.md")
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md_content)
        
    print(f"Saved parsed markdown to {output_path}")
    return output_path
