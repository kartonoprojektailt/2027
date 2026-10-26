import os
import subprocess
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

SPREADSHEET_ID = "1q2qOk7SwMZYn3uz46MjlU4_1bZ47nFLdWEIjIMpHHn4"
CREDENTIALS_FILE = "credentials.json"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly"
]

print("Jungiamasi prie Google Sheets per API...")
try:
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    
    # Nuskaitome pagrindines zakładkes
    df_prod = pd.DataFrame(spreadsheet.worksheet("product_service").get_all_records())
    df_static = pd.DataFrame(spreadsheet.worksheet("static_pages").get_all_records())
    
    dfs_to_concat = [df_prod, df_static]
    
    # Bandome įtraukti trečiąją zakładkę 'sandelyje'
    try:
        df_sandelyje = pd.DataFrame(spreadsheet.worksheet("sandelyje").get_all_records())
        df_sandelyje['source_tab'] = 'sandelyje'
        dfs_to_concat.append(df_sandelyje)
        print("Zakładka 'sandelyje' sėkmingai aptikta ir įtraukta.")
    except Exception:
        print("Pastaba: zakładka 'sandelyje' dar nesukurta Google Sheets (bus praleista kol kas).")

    df = pd.concat(dfs_to_concat, ignore_index=True)
    print(f"Iš viso parsiųsta {len(df)} eilučių iš visų aktyvių tab'ų.")
except Exception as e:
    print(f"Klaida jungiantis prie Google Sheets: {e}")
    exit(1)

def sanitize_text(text):
    if not isinstance(text, str):
        return ""
    return text.strip()

for index, row in df.iterrows():
    slug = sanitize_text(str(row.get('slug', '')))
    title = sanitize_text(str(row.get('title', '')))
    content_body = sanitize_text(str(row.get('content_body', '')))
    source_tab = str(row.get('source_tab', ''))
    
    if not title and not content_body:
        continue
        
    # Jei tai zakładka sandelyje, generuojame į content/sandelyje/{slug}/index.md
    if source_tab == 'sandelyje' and slug and slug.lower() != 'nan':
        file_path = f"content/sandelyje/{slug}/index.md"
    # Pagrindinis puslapis (jei slug tuščias, 'index' arba '/')
    elif not slug or slug.lower() == 'nan' or slug.lower() == 'index' or slug == '/':
        file_path = "content/_index.md"
    else:
        file_path = f"content/{slug}/index.md"

    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    markdown_content = f"""---
title: "{title}"
draft: false
---

{content_body}
"""

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
    print(f"Įrašyta: {file_path}")

# Automatinis Git sinchronizavimas su pataisytu '-m' parametru
print("Vykdomas Git sinchronizavimas...")
try:
    subprocess.run(["git", "add", "-A"], check=True)
    status_res = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True)
    if status_res.stdout.strip():
        subprocess.run(["git", "commit", "-m", "Auto-update: sync products, static pages and sandelyje"], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print("Valio! Visi pakeitimai iškeliavo į GitHub ir Cloudflare.")
    else:
        print("Jokių naujų pakeitimų faile nėra.")
except subprocess.CalledProcessError as e:
    print(f"Klaida vykdant Git: {e}")
