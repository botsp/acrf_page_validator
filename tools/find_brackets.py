import json
import re
import sys
from pathlib import Path
# Ensure repo root is on sys.path
repo_root = str(Path(__file__).resolve().parents[1])
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from modules.pymupdf_parser import extract_variables_from_pdf

PDF_PATH = r"C:\dev\acrf_page_validator\config\acrf.pdf"

b = open(PDF_PATH, "rb").read()
r = extract_variables_from_pdf(b)

bad = []
for v in r.get('variables', []):
    for s in v.get('RawTexts', []):
        if s.strip().startswith('(') or re.search(r"\(\s*[A-Za-z0-9]{1,4}\s*(?:$|\))", s) or re.search(r"\(\s*[A-Za-z]{1,3}\s+[A-Z]", s):
            bad.append({'Variable': v.get('Variable'), 'Pages': v.get('PageString'), 'Raw': s})
            break

out = {'count': len(bad), 'examples': bad[:80]}
print(json.dumps(out, ensure_ascii=False, indent=2))
