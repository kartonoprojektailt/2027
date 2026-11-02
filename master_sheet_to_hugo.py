import os
import json
import tempfile
import shutil
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
