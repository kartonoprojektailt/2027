import os
import json
import tempfile
import shutil
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
    credentials_json_str = os.environ.get("GCP_CREDENTIALS_JSON") or os.environ.get("GCP_CREDENTIALS")
    
    if credentials_json_str:
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as temp_cred:
            temp_cred.write(credentials_json_str)
            temp_cred_path = temp_cred.name
        creds = Credentials.from_service_account_file(temp_cred_path, scopes=SCOPES)
        print("Użyto poświadczeń z GitHub Secrets.")
    else:
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        print("Użyto lokalnego pliku credentials.json.")

    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    
    def fetch_sheet_as_df(sheet_name):
        worksheet = spreadsheet.worksheet(sheet_name)
        data = worksheet.get_all_values()
        if not data:
            return pd.DataFrame()
        headers = [str(h).strip() for h in data[0]]
        df_sheet = pd.DataFrame(data[1:], columns=headers)
        # Czyszczenie ewentualnych pustych nagłówków bez nazwy
        df_sheet = df_sheet.loc[:, df_sheet.columns != '']
        return df_sheet

    # 1. Zakładka 'puslapiai' - pomijamy wiersz 2 (instrukcyjny)
    df_puslapiai = fetch_sheet_as_df("puslapiai")
    df_puslapiai['source_tab'] = 'puslapiai'
    if len(df_puslapiai) > 0:
        df_puslapiai = df_puslapiai.iloc[1:].reset_index(drop=True)
    
    dfs_to_concat = [df_puslapiai]
    
    # 2. Zakładka 'sandelyje' - pomijamy wiersz 2 (instrukcyjny)
    try:
        df_sandelyje = fetch_sheet_as_df("sandelyje")
        df_sandelyje['source_tab'] = 'sandelyje'
        if len(df_sandelyje) > 0:
            df_sandelyje = df_sandelyje.iloc[1:].reset_index(drop=True)
        dfs_to_concat.append(df_sandelyje)
        print("Zakładka 'sandelyje' pomyślnie dołączona.")
    except Exception as e:
        print(f"Brak zakładki 'sandelyje' lub klaida: {e}")

    df = pd.concat(dfs_to_concat, ignore_index=True)
except Exception as e:
    print(f"Klaida jungiantis prie Google Sheets: {e}")
    exit(1)

def sanitize_text(text):
    if not isinstance(text, str):
        return ""
    return text.strip()

def fix_gdrive_url(url, max_width=1000):
    if not isinstance(url, str) or not url.strip():
        return ""
    url = url.strip()
    file_id = ""
    
    # Precyzyjne wyciąganie ID pliku z różnych formatów linków Google Drive / lh3
    if "/file/d/" in url:
        try:
            file_id = url.split("/file/d/")[1].split("/")[0]
        except Exception:
            pass
    elif "id=" in url:
        try:
            file_id = url.split("id=")[1].split("&")[0]
        except Exception:
            pass
    elif "lh3.googleusercontent.com/d/" in url:
        try:
            file_id = url.split("lh3.googleusercontent.com/d/")[1].split("=")[0].rstrip("/").split("/")[0]
        except Exception:
            pass
            
    if file_id:
        # Używamy uniwersalnego endpointu bezpośredniego podglądu z Google Drive
        return f"https://drive.google.com/uc?export=view&id={file_id}"
    return url

def get_category_url(category_name):
    cat_lower = category_name.strip().lower()
    
    if "fefco" in cat_lower:
        return "/fefco-dezes/"
    elif "dovan" in cat_lower:
        return "/dovanu-dezutes/"
    elif "dėžutė" in cat_lower or "dezute" in cat_lower:
        return "/dezutes/"
    elif "dėžė" in cat_lower or "deze" in cat_lower or "pakuot" in cat_lower:
        return "/pakuotes/"
    elif "stend" in cat_lower or "stov" in cat_lower or "posm" in cat_lower:
        return "/reklaminiai-stendai-stovai/"
    elif "foto" in cat_lower or "sienel" in cat_lower:
        return "/foto-sieneles/"
    elif "dekorac" in cat_lower:
        return "/parduotuviu-dekoracijos/"
    elif "akril" in cat_lower:
        return "/akrilo-gaminiai/"
    elif "frezavim" in cat_lower:
        return "/cnc-frezavimas/"
    elif "pjovim" in cat_lower:
        return "/cnc-pjovimas/"
    elif "cnc" in cat_lower:
        return "/cnc-paslaugos/"
    elif "projektavim" in cat_lower:
        return "/projektavimo-paslaugos/"
    return "/"

# Generowanie plików Markdown dla Hugo z uwzględnieniem hero_image i galerii
output_dir = "content"
os.makedirs(output_dir, exist_ok=True)

for index, row in df.iterrows():
    title = sanitize_text(row.get("title", ""))
    slug = sanitize_text(row.get("slug", ""))
    if not title and not slug:
        continue
        
    if not slug:
        slug = title.lower().replace(" ", "-").replace("ą", "a").replace("č", "c").replace("ę", "e").replace("ė", "e").replace("į", "i").replace("š", "s").replace("ų", "u").replace("ū", "u").replace("ž", "z")
    
    description = sanitize_text(row.get("description", ""))
    content = sanitize_text(row.get("content", ""))
    
    # Przetwarzanie zdjęcia głównego
    hero_raw = row.get("hero_image", "")
    hero_image = fix_gdrive_url(hero_raw, max_width=1200)
    
    # Przetwarzanie galerii zdjęć (rozdzielanie po przecinku lub nowej linii)
    gallery_raw = row.get("gallery_images", "")
    gallery_images = []
    if gallery_raw:
        parts = gallery_raw.replace("\n", ",").split(",")
        for p in parts:
            p_clean = p.strip()
            if p_clean:
                fixed_p = fix_gdrive_url(p_clean, max_width=1000)
                if fixed_p:
                    gallery_images.append(fixed_p)

    front_matter = f"""---
title: "{title}"
date: 2026-03-23T00:00:00Z
draft: false
description: "{description}"
hero_image: "{hero_image}"
gallery_images:
"""
    for img in gallery_images:
        front_matter += f"  - \"{img}\"\n"
    front_matter += "---\n\n"
    
    file_content = front_matter + content
    
    file_path = os.path.join(output_dir, f"{slug}.md")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(file_content)

print("Wygenerowano pliki Markdown pomyślnie wraz z obsługą bezpośrednich linków do obrazów.")
