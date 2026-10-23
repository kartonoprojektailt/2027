import os
import subprocess
import pandas as pd

# Nuoroda į tavo Master_content_kp Google Sheets CSV eksportą
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/1Xvj6TLV8oGz5YCQlWg4wC1Dchz1AUaHEIYJbbonOM/export?format=csv"

print("Parsisiunčiami visi puslapiai iš Master_content_kp Google Sheets...")
try:
    df = pd.read_csv(SHEET_CSV_URL)
except Exception as e:
    print(f"Klaida siunčiantis duomenis iš lentelės: {e}")
    exit(1)

def sanitize_text(text):
    if not isinstance(text, str):
        return ""
    return text.strip()

def parse_specs_to_markdown_table(cell_text):
    """Automatiškai paverčia techninių specifikacijų tekstą į tvarkingą Markdown lentelę"""
    if not isinstance(cell_text, str) or not cell_text.strip():
        return ""
    
    markdown_table = "| Parametras | Techninė specifikacija / Aprašymas |\n| :--- | :--- |\n"
    lines = cell_text.strip().split('\n')
    for line in lines:
        if ':' in line:
            key, val = line.split(':', 1)
            markdown_table += f"| **{key.strip()}** | {val.strip()} |\n"
    return markdown_table

# Prabėgame per kiekvieną eilutę (kiekvienas puslapis - atskira eilutė)
for index, row in df.iterrows():
    file_path = sanitize_text(str(row.get('file_path', '')))
    if not file_path or file_path == 'nan':
        continue
        
    title = sanitize_text(str(row.get('page_title', 'Kartoninės pakuotės')))
    description = sanitize_text(str(row.get('description', '')))
    
    h1_text = sanitize_text(str(row.get('intro_heading_h1', '')))
    intro_desc = sanitize_text(str(row.get('intro_text', '')))
    
    specs_heading = sanitize_text(str(row.get('specs_heading_h2', 'Gamybos galimybės ir techninė specifikacija')))
    specs_data_raw = sanitize_text(str(row.get('specs_table_data', '')))
    specs_table = parse_specs_to_markdown_table(specs_data_raw)
    
    categories_heading = sanitize_text(str(row.get('categories_heading_h2', 'Pagrindinės gamybos ir paslaugų kryptys')))
    categories_text = sanitize_text(str(row.get('categories_content', '')))
    
    human_text = sanitize_text(str(row.get('human_text', '')))
    cta_text = sanitize_text(str(row.get('cta_and_contacts', '')))

    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    # Sugeneruojame puslapio Markdown failą pagal nustatytą struktūrą
    markdown_content = f"""---
title: "{title}"
description: "{description}"
draft: false
---

# {h1_text}

{intro_desc}

---

{{{{< gallery >}}}}
{{{{< /gallery >}}}}

---

## {specs_heading}
{specs_table}

---

## {categories_heading}
{categories_text}

---

## Apie mus ir mūsų pasiekimai
{human_text}

---

## Užsakymo ir gamybos eiga bei kontaktai
{cta_text}
"""

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
    print(f"Sėkmingai atnaujintas puslapis: {file_path}")

# Automatinis Git sinchronizavimas su GitHub ir Cloudflare
print("Vykdomas Git sinchronizavimas...")
try:
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "commit", "-m", "Auto-update: all pages sync from Master_content_kp"], check=True)
    subprocess.run(["git", "push", "origin", "main"], check=True)
    print("Valio! Visi svetainės puslapiai sėkmingai atnaujinti ir iškeliavo į GitHub/Cloudflare.")
except subprocess.CalledProcessError as e:
    print(f"Klaida vykdant Git: {e}")
