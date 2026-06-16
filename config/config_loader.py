from pathlib import Path
import csv

def _normalize_row(row):
    normalized = {}
    for key, value in row.items():
        if key is None:
            continue
        clean_key = key.lstrip("\ufeff").strip().lower()
        normalized[clean_key] = value
    return normalized

def load_config():
    config_dir = Path(__file__).parent.parent / "config"
    
    standard_terms = {"dataset": set(), "variable": set()}

    suffix_prefix_patterns = {"dataset": set(), "variable": set()}
    
    blacklist = set()
    
    # 1. load standard_term.csv
    term_file = config_dir / "standard_term.csv"
    if term_file.exists():
        with open(term_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row = _normalize_row(row)
                cat = row.get("category", "").strip().lower()
                term = row.get("term", "").strip().upper()
                if not term:
                    continue
                if cat in ["dataset", "variable"]:
                    standard_terms[cat].add(term)
    else:
        print(f"⚠️ Warning: {term_file} not found.")

    # 2. load standard_term_suffix_prefix.csv
    pattern_file = config_dir / "standard_term_suffix_prefix.csv"
    if pattern_file.exists():
        with open(pattern_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row = _normalize_row(row)
                cat = row.get("category", "").strip().lower()
                term = row.get("term", "").strip().upper()
                if not term:
                    continue
                if cat in ["dataset", "variable"]:
                    suffix_prefix_patterns[cat].add(term)
    else:
        print(f"⚠️ Warning: {pattern_file} not found.")

    # 3. load blacklist
    bl_file = config_dir / "blacklist.txt"
    if bl_file.exists():
        with open(bl_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip().upper()
                if line and not line.startswith("#"):
                    blacklist.add(line)

    return {
        "standard_terms": standard_terms,
        "suffix_prefix_patterns": suffix_prefix_patterns,
        "blacklist": blacklist
    }


# global load
CONFIG = load_config()