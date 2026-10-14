import os
import csv
import re

CONTENT_DIR = os.path.join("content", "md") if os.path.exists(os.path.join("content", "md")) else "content"
OUTPUT_CSV = "master_content.csv"

def extract_frontmatter_and_body(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    title = ""
    description = ""
    slug = ""
    draft = "false"
    body = content

    # Szukamy nagłówków YAML (---) lub TOML (+++) na samym początku pliku
    match = re.match(r"^(---|\+\+\+)\s*\n(.*?)\n\1\s*\n(.*)", content, re.DOTALL)
    
    if match:
        frontmatter_text = match.group(2)
        body = match.group(3).strip()

        for line in frontmatter_text.splitlines():
            if ":" in line or "=" in line:
                parts = re.split(r'[:=]', line, 1)
                if len(parts) == 2:
                    key = parts[0].strip().lower()
                    val = parts[1].strip().strip('"').strip("'")
                    if key == "title":
                        title = val
                    elif key == "description":
                        description = val
                    elif key == "slug":
                        slug = val
                    elif key == "draft":
                        draft = val

    return title, description, slug, draft, body

def export_to_csv():
    if not os.path.exists(CONTENT_DIR):
        print(f"BŁĄD: Katalog '{CONTENT_DIR}' nie istnieje!")
        return

    records = []

    for root, _, files in os.walk(CONTENT_DIR):
        for file in files:
            if file.endswith(".md"):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, start=CONTENT_DIR)
                
                title, description, slug, draft, body = extract_frontmatter_and_body(full_path)
                
                # Jeśli slug nie jest zdefiniowany w nagłówku, generujemy go automatycznie z ścieżki/nazwy
                if not slug:
                    file_name = os.path.basename(rel_path)
                    slug = os.path.splitext(file_name)[0].replace("_index", "").replace("index", "").strip()
                    # Jeśli plik był w podfolderze (np. uslugi/cnc.md), uwzględnij go w slug lub weź samą nazwę
                    if not slug and rel_path != file_name:
                        slug = os.path.dirname(rel_path).replace(os.path.sep, "-")

                records.append({
                    "file_path": rel_path,
                    "slug": slug,
                    "title": title,
                    "description": description,
                    "draft": draft,
                    "body": body
                })

    records.sort(key=lambda x: x["file_path"])

    fieldnames = ["file_path", "slug", "title", "description", "draft", "body"]
    
    with open(OUTPUT_CSV, "w", encoding="utf-8-sig", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(records)

    print(f"SUKCES: Pomyślnie wygenerowano plik '{OUTPUT_CSV}' dla {len(records)} plików.")

if __name__ == "__main__":
    export_to_csv()
