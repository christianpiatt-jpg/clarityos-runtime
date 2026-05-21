import docx

def extract_docx_text(path):
    try:
        doc = docx.Document(path)
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception as e:
        print(f"Could not read DOCX {path}: {e}")
        return None
