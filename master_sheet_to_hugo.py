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
    # Obsługa uwierzytelniania: w chmurze (GitHub Actions) tworzy plik tymczasowy ze zmiennej środowiskowej,
    # lokalnie na laptopie szuka fizycznego pliku credentials.json.
    credentials_json_str = os.environ.get("GCP_CREDENTIALS_JSON")
    
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
    
    df_puslapiai = pd.DataFrame(spreadsheet.worksheet("puslapiai").get_all_records())
    df_puslapiai['source_tab'] = 'puslapiai'
    
    dfs_to_concat = [df_puslapiai]
    
    try:
        df_sandelyje = pd.DataFrame(spreadsheet.worksheet("sandelyje").get_all_records())
        df_sandelyje['source_tab'] = 'sandelyje'
        dfs_to_concat.append(df_sandelyje)
        print("Zakładka 'sandelyje' pomyślnie dołączona.")
    except Exception:
        print("Brak zakładki 'sandelyje' – pomijamy.")

    df = pd.concat(dfs_to_concat, ignore_index=True)
except Exception as e:
    print(f"Klaida jungiantis prie Google Sheets: {e}")
    exit(1)

def sanitize_text(text):
    if not isinstance(text, str):
        return ""
    return text.strip()

def fix_gdrive_url(url, max_width=1000):
    if "drive.google.com" in url:
        try:
            file_id = ""
            if "/file/d/" in url:
                file_id = url.split("/file/d/")[1].split("/")[0]
            elif "id=" in url:
                file_id = url.split("id=")[1].split("&")[0]
            
            if file_id:
                return f"https://lh3.googleusercontent.com/d/{file_id}=w{max_width}"
        except Exception:
            return url
    return url

def get_category_url(category_name):
    cat_lower = category_name.strip().lower()
    
    if "pakuot" in cat_lower:
        return "/pakuotes/"
    elif "reklam" in cat_lower or "stend" in cat_lower or "posm" in cat_lower:
        return "/reklaminiai-stendai-stovai/"
    elif "cnc" in cat_lower or "frez" in cat_lower or "pjov" in cat_lower:
        return "/cnc-paslaugos/"
    elif "medžiag" in cat_lower or "medziag" in cat_lower:
        return "/"
    elif "workshop" in cat_lower or "dirbtuv" in cat_lower or "mokym" in cat_lower or "minkšt" in cat_lower or "minkst" in cat_lower:
        return "/projektavimo-paslaugos/"
    else:
        return "/sandelyje/"

# 1. USUWANIE FOLDERU CONTENT/SEARCH/ JEŚLI ISTNIEJE (GŁÓWNA PRZYCZYNA BŁĘDU)
if os.path.exists("content/search") and os.path.isdir("content/search"):
    shutil.rmtree("content/search")
    print("Pašalintas klaidingas aplankas 'content/search/'.")

# 2. Usuwanie ewentualnego błędnego pliku sandelyje/index.md
if os.path.exists("content/sandelyje/index.md"):
    os.remove("content/sandelyje/index.md")

for index, row in df.iterrows():
    slug = sanitize_text(str(row.get('slug', '')))
    title = sanitize_text(str(row.get('title', '')))
    meta_desc = sanitize_text(str(row.get('meta_description', '')))
    content_body = sanitize_text(str(row.get('content_body', '')))
    
    hero_image = sanitize_text(str(row.get('hero_image', '')))
    if hero_image:
        hero_image = fix_gdrive_url(hero_image, max_width=1000)
        
    search_cloud = sanitize_text(str(row.get('search_cloud', '')))
    cloud_list = [tag.strip() for tag in search_cloud.split(',') if tag.strip()]
    
    code = sanitize_text(str(row.get('code', '')))
    category = sanitize_text(str(row.get('category', '')))
    category_url = get_category_url(category) if category else ""
    
    price = sanitize_text(str(row
