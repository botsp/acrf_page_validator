"""
XML Parser Module for Define.xml
Extracts variables, dataset names, and ACRF page numbers
"""

from lxml import etree
import re
from typing import Dict, List


def extract_dataset_name(oid: str) -> str:
    """Extract dataset name from OID (e.g. IT.VS.VSDTC → VS)"""
    if not oid:
        return ""
    # Pattern: IT.{DATASET}.{VARIABLE}
    parts = oid.split('.')
    if len(parts) >= 3 and parts[0] == 'IT':
        return parts[1]
    return ""


def parse_define_xml(xml_content: bytes) -> Dict:
    """
    Parse Define.xml and extract variable + dataset + ACRF pages
    """
    try:
        parser = etree.XMLParser(remove_blank_text=True, resolve_entities=False)
        root = etree.fromstring(xml_content, parser=parser)
        
        results = []
        seen_variables = set()
        
        # Find all ItemDef
        item_defs = root.xpath("//*[local-name()='ItemDef']")
        
        for item in item_defs:
            var_name = item.get('Name')
            oid = item.get('OID', '')
            
            if not var_name or var_name in seen_variables:
                continue
                
            seen_variables.add(var_name)
            
            dataset_name = extract_dataset_name(oid)
            
            # Extract PageRefs
            page_refs = item.xpath(".//*[local-name()='PDFPageRef']/@PageRefs")
            
            pages = []
            page_str = ""
            
            if page_refs:
                page_str = page_refs[0].strip()
                pages = [p.strip() for p in re.split(r'\s+', page_str) if p.strip()]
            
            if pages:  # Only keep variables with ACRF pages
                results.append({
                    "Dataset": dataset_name,
                    "Variable": var_name,
                    "OID": oid,
                    "Pages": pages,
                    "PageString": page_str,
                    "PageCount": len(pages)
                })
        
        summary = {
            "total_variables": len(results),
            "variables_with_pages": len(results),
            "total_page_references": sum(v["PageCount"] for v in results),
            "unique_datasets": len(set(v["Dataset"] for v in results if v["Dataset"]))
        }
        
        return {
            "variables": results,
            "summary": summary,
            "status": "success"
        }
        
    except Exception as e:
        return {
            "variables": [],
            "summary": {},
            "status": "error",
            "error_message": str(e)
        }


def format_pages(pages: List[str]) -> str:
    if not pages:
        return ""
    return " ".join(pages)


if __name__ == "__main__":
    print("✅ XML Parser Module Loaded Successfully")