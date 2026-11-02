import os
import json
import tempfile
import shutil
import subprocess
import re
import urllib.request
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from PIL import Image

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
        if not data or len(data) < 3:
            return pd.DataFrame()
        
        headers = [str(h).strip() for h in data[0]]
        rows_data = data[2:] 
        
        df_sheet = pd.DataFrame(rows_data, columns=headers)
        df_sheet = df_sheet.loc[:, df_sheet.columns != '']
        return df_sheet

    df_puslapiai = fetch_sheet_as_df("puslapiai")
    df_puslapiai['source_tab'] = 'puslapiai'
    
    dfs_to_concat = [df_puslapiai]
    
    try:
        df_sandelyje = fetch_sheet_as_df("sandelyje")
        df_sandelyje['source_tab'] = 'sandelyje'
        dfs_to_concat.append(df_sandelyje)
        print("Zakładka 'sandelyje' pomyślnie dołączona.")
    except Exception as e:
        print(f"Brak zakładki 'sandelyje' lub błąd: {e}")

    df = pd.concat(dfs_to_concat, ignore_index=True)
except Exception as e:
    print(f"Klaida jungiantis prie Google Sheets: {e}")
    exit(1)

images_dir = os.path.join("static", "images")
os.makedirs(images_dir, exist_ok=True)

def extract_gdrive_id(url):
    if not isinstance(url, str) or not url.strip():
        return ""
    url = url.strip()
    
    if "tinkami norodu" in url.lower() or "grafika tik" in url.lower() or "cia tik" in url.lower():
        return ""
    
    url = url.replace("/d//", "/")
    
    if "/file/d/" in url:
        try:
            return url.split("/file/d/")[1].split("/")[0].split("?")[0]
        except Exception:
            pass
    elif "id=" in url:
        try:
            return url.split("id=")[1].split("&")[0].split("/")[0]
        except Exception:
            pass
    elif "googleusercontent.com/d/" in url:
        try:
            clean = url.split("googleusercontent.com/d/")[1].replace("//", "/")
            return clean.split("/")[0].split("=")[0].split("?")[0]
        except Exception:
            pass
    return ""

def optimize_and_save_image(filepath):
    try:
        with Image.open(filepath) as img:
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            max_dimension = 1600
            img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
            
            img.save(filepath, "JPEG", quality=85, optimize=True)
    except Exception as e:
        print(f"Błąd optymalizacji pliku {filepath}: {e}")

def download_and_cache_image(url, filename_prefix, index_suffix=0):
    if not isinstance(url, str) or not url.strip() or str(url).lower() == "nan":
        return ""

    url = url.strip()

    if url.startswith("/images/"):
        return url

    if "." in url and not url.startswith("http") and "/" not in url and "\\" not in url:
        return f"/images/{url}"
        
    file_id = extract_gdrive_id(url)
    
    local_filename = f"{filename_prefix}-{index_suffix}.jpg" if index_suffix > 0 else f"{filename_prefix}.jpg"
    local_filepath = os.path.join(images_dir, local_filename)
    public_url_path = f"/images/{local_filename}"
    
    if not file_id:
        return ""
        
    if os.path.exists(local_filepath) and os.path.getsize(local_filepath) > 1000:
        return public_url_path

    download_urls = [
        f"https://drive.google.com/uc?export=download&id={file_id}",
        f"https://lh3.googleusercontent.com/d/{file_id}"
    ]
    
    success = False
    for d_url in download_urls:
        try:
            req = urllib.request.Request(d_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, timeout=12) as response, open(local_filepath, 'wb') as out_file:
                shutil.copyfileobj(response, out_file)
            
            if os.path.exists(local_filepath) and os.path.getsize(local_filepath) > 1000:
                optimize_and_save_image(local_filepath)
                print(f"✓ Pobrano i zoptymalizowano zdjęcie: {local_filename}")
                success = True
                break
        except Exception:
            continue
            
    if not success:
        print(f"⚠ Ostrzeżenie: Nie udało się pobrać pliku dla ID: {file_id}")
        return ""
        
    return public_url_path

def sanitize_text(text):
    if not isinstance(text, str):
        return ""
    return text.strip()

output_dir = "content"
os.makedirs(output_dir, exist_ok=True)

processed_count = 0

for index, row in df.iterrows():
    title = sanitize_text(row.get("title", ""))
    slug = sanitize_text(row.get("slug", ""))
    
    if not title and not slug:
        continue
        
    if not slug:
        slug = title.lower().replace(" ", "-").replace("ą", "a").replace("č", "c").replace("ę", "e").replace("ė", "e").replace("į", "i").replace("š", "s").replace("ų", "u").replace("ū", "u").replace("ž", "z")
    
    description = sanitize_text(row.get("description", ""))
    content = sanitize_text(row.get("content body", "") or row.get("content", ""))
    
    if not content:
        content = f"Informacija apie {title} atnaujinama."

    hero_raw = row.get("hero image", "") or row.get("hero_image", "")
    hero_image = download_and_cache_image(hero_raw, f"{slug}-hero") if hero_raw else ""
    
    gallery_raw = row.get("gallery images", "") or row.get("gallery_images", "")
    gallery_images = []
    if gallery_raw and str(gallery_raw).lower() != "nan":
        parts = str(gallery_raw).replace("\n", ",").split(",")
        idx = 1
        for p in parts:
            p_clean = p.strip()
            if p_clean:
                cached_img = download_and_cache_image(p_clean, f"{slug}-gallery", idx)
                if cached_img:
                    gallery_images.append(cached_img)
                    idx += 1

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
    
    # PŁASKA HIERARCHIA: bezpośrednio pliki content/slug.md
    file_path = os.path.join(output_dir, f"{slug}.md")
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(file_content)
        
    processed_count += 1

print("\n" + "="*50)
print(f"SUDERINIMAS BAIGTAS: Sėkmingai sugeneruoti {processed_count} puslapiai płaskiej struktury (content/slug.md)!")
print("="*50)
