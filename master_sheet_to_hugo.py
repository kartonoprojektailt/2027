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
    sheet = client.open_by_key(SPREADSHEET_ID).sheet1  
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

for index, row in df.iterrows():
    # Naudojame tikslų stulpelio pavadinimą iš tavo lentelemės: 'slug'
    slug = sanitize_text(str(row.get('slug', '')))
    title = sanitize_text(str(row.get('title', '')))
    content_body = sanitize_text(str(row.get('content_body', '')))
    
    # Jei nėra turinio ar pavadinimo, praleidžiam
    if not title and not content_body:
        continue
        
    # Jei tai pagrindinis puslapis (slug tuščias arba 'index'), rašom į _index.md
    if not slug or slug.lower() == 'index' or slug == '/':
        file_path = "content/_index.md"
    else:
        # Kitu atveju tai atskira podstrona folderio viduje
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
    print(f"Sukurtas/Atnaujintas puslapis: {file_path}")

# Automatinis Git sinchronizavimas
print("Vykdomas Git sinchronizavimas...")
try:
    subprocess.run(["git", "add", "-A"], check=True)
    status_res = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True)
    if status_res.stdout.strip():
        subprocess.run(["git", "commit", "-m", "Auto-update: safe sync pages using correct 'slug' column"], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print("Valio! Pakeitimai iškeliavo į GitHub ir Cloudflare.")
    else:
        print("Jokių naujų pakeitimų faile nėra.")
except subprocess.CalledProcessError as e:
    print(f"Klaida vykdant Git: {e}")
