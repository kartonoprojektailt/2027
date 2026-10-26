import os
import subprocess
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

# Konfigūracija
SPREADSHEET_ID = "1q2qOk7SwMZYn3uz46MjlU4_1bZ47nFLdWEIjIMpHHn4"
CREDENTIALS_FILE = "credentials.json"

# Nustatymai prisijungimui prie Google Sheets API per Service Account
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly"
]

print("Jungiamasi prie Google Sheets per API...")
try:
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    
    # Atidarome lentelę pagal ID
    sheet = client.open_by_key(SPREADSHEET_ID).sheet1  # Paima pirmą lapą (sheet)
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    print(f"Sėkmingai parsiųsta {len(df)} eilučių iš Master Sheet.")
except Exception as e:
    print(f"Klaida jungiantis prie Google Sheets: {e}")
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

# Pereiname per kiekvieną eilutę arklyje
for index, row in df.iterrows():
    file_path = sanitize_text(str(row.get('file_path', '')))
    if not file_path or file_path.lower() == 'nan':
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

    # Sugeneruojame puslapio Markdown failą
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
    print(f"Atnaujintas puslapis: {file_path}")

# Automatinis Git sinchronizavimas su GitHub ir Cloudflare
print("Vykdomas Git sinchronizavimas...")
try:
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "commit", "-m", "Auto-update: pages sync from Master Google Sheet via API"], check=True)
    subprocess.run(["git", "push", "origin", "main"], check=True)
    print("Valio! Pakeitimai iškeliavo į GitHub ir Cloudflare.")
except subprocess.CalledProcessError as e:
    print(f"Klaida vykdant Git: {e}")
