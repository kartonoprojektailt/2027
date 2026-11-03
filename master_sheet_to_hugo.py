import os
import json
import tempfile
import shutil
import urllib.request
import re
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

print("Jungiamasi prie Google Sheets (Master_turinys_kartonoprojektai) per API...")
try:
    credentials_json_str = os.environ.get("GCP_CREDENTIALS_JSON") or os.environ.get("GCP_CREDENTIALS")
    
    if credentials_json_str:
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as temp_cred:
            temp_cred.write(credentials_json_str)
            temp_cred_path = temp_cred.name
        creds = Credentials.from_service_account_file(temp_cred_path, scopes=SCOPES)
        print("Užteko poświadczeń z GitHub Secrets.")
    else:
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        print("Užteko lokalnego pliku credentials.json.")

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
content_dir = "content"

os.makedirs(images_dir, exist_ok=True)
os.makedirs(content_dir, exist_ok=True)

def extract_gdrive_id(url):
    if not isinstance(url, str) or not url.strip():
        return ""
    url = url.strip()
    if "tinkami norodu" in url.lower() or "grafika tik" in url.lower() or "cia tik" in url.lower():
        return ""
    url = url.replace("/d//", "/")
    
    match = re.search(r'(?:/file/d/|id=|usercontent\.com/d/)([a-zA-Z0-9_-]{25,})', url)
    if match:
        return match.group(1)
        
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

def download_and_cache_image(url, filename_prefix):
    if not isinstance(url, str) or not url.strip() or str(url).lower() == "nan":
        return ""
    url = url.strip()
    if url.startswith("/images/"):
        return url
    if "." in url and not url.startswith("http") and "/" not in url and "\\" not in url:
        return f"/images/{url}"
        
    file_id = extract_gdrive_id(url)
    local_filename = f"{filename_prefix}.jpg"
    local_filepath = os.path.join(images_dir, local_filename)
    public_url_path = f"/images/{local_filename}"

    if os.path.exists(local_filepath) and os.path.getsize(local_filepath) > 1000:
        return public_url_path

    download_urls = []
    if file_id:
        download_urls = [
            f"https://drive.google.com/uc?export=download&id={file_id}",
            f"https://lh3.googleusercontent.com/d/{file_id}=s1600",
            f"https://drive.google.com/thumbnail?id={file_id}&sz=w1600"
        ]
    elif url.startswith("http"):
        download_urls = [url]

    for d_url in download_urls:
        try:
            req = urllib.request.Request(d_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, timeout=15) as response, open(local_filepath, 'wb') as out_file:
                shutil.copyfileobj(response, out_file)
            
            if os.path.getsize(local_filepath) > 1000:
                optimize_and_save_image(local_filepath)
                return public_url_path
        except Exception:
            continue
            
    return public_url_path if os.path.exists(local_filepath) and os.path.getsize(local_filepath) > 1000 else url

print("Generuojami Markdown puslapiai ir prekės iš Google Sheets...")

# Zapewniamy, że sandelyje jest traktowane jako chroniony slug
valid_slugs = {"sandelyje"}

for _, row in df.iterrows():
    slug = str(row.get('slug', '')).strip()
    title = str(row.get('title', slug)).strip()
    
    if not slug or slug.lower() == 'nan' or slug == 'Unikalus puslapio adresas':
        continue
        
    # Automatyczne odfiltrowanie błędnego ogłoszenia o tytule/slug "Kartono projektų sandėlio pasiūlymai"
    if "sandėlio pasiūlymai" in title.lower() or slug.lower() == "kartono-projektu-sandelio-pasiulymai":
        continue

    source_tab = str(row.get('source_tab', 'puslapiai')).strip()
    if source_tab == 'puslapiai' and slug == 'sandelyje':
        continue
        
    valid_slugs.add(slug)

    if title.lower() == 'nan':
        title = slug
        
    hero_raw = row.get('hero_image', '')
    hero_image = download_and_cache_image(hero_raw, slug) if hero_raw and str(hero_raw).lower() != 'nan' else ""
    
    gallery_images = []
    gallery_raw = row.get('gallery_images', '')
    if gallery_raw and str(gallery_raw).lower() != 'nan':
        urls = [u.strip() for u in str(gallery_raw).replace('\n', ',').split(',') if u.strip()]
        for idx, u in enumerate(urls, start=1):
            g_img = download_and_cache_image(u, f"{slug}-g{idx}")
            if g_img:
                gallery_images.append(g_img)

    fm = [
        "---",
        f"title: {json.dumps(title)}",
        f"slug: {json.dumps(slug)}",
        f"type: {json.dumps('sandelyje' if source_tab == 'sandelyje' else 'page')}",
    ]
    
    meta_desc = row.get('meta_description ', '') or row.get('meta_description', '')
    if meta_desc and str(meta_desc).lower() != 'nan':
        fm.append(f"description: {json.dumps(str(meta_desc).strip())}")
        
    if source_tab == 'sandelyje':
        fm.append(f"url: {json.dumps('/' + slug + '/')}")
        fm.append('layout: "single"')
        
        code_val = row.get('code', '')
        if code_val and str(code_val).lower() != 'nan':
            fm.append(f"code: {json.dumps(str(code_val))}")
            fm.append(f"offer_code: {json.dumps(str(code_val))}")
            fm.append(f"sku: {json.dumps(str(code_val))}")
            
        category_val = row.get('category', '')
        if category_val and str(category_val).lower() != 'nan':
            fm.append(f"category: {json.dumps(str(category_val))}")
            
        price_val = row.get('price', '')
        if price_val and str(price_val).lower() != 'nan':
            fm.append(f"price: {json.dumps(str(price_val))}")
            fm.append(f"kaina: {json.dumps(str(price_val))}")
            
        unit_val = row.get('unit', '')
        if unit_val and str(unit_val).lower() != 'nan':
            fm.append(f"unit: {json.dumps(str(unit_val))}")
            
        stock_val = row.get('stock', '')
        if stock_val and str(stock_val).lower() != 'nan':
            fm.append(f"stock: {json.dumps(str(stock_val))}")
            fm.append(f"likutis: {json.dumps(str(stock_val))}")
            
        sale_reason_val = row.get('sale_reason', '')
        if sale_reason_val and str(sale_reason_val).lower() != 'nan':
            fm.append(f"sale_reason: {json.dumps(str(sale_reason_val))}")

        excluded_cols = {
            'slug', 'title', 'code', 'offer_code', 'sku', 'category', 
            'price', 'kaina', 'unit', 'stock', 'likutis', 'sale_reason', 
            'hero_image', 'gallery_images', 'search_cloud', 'content_body', 
            'content', 'source_tab', 'meta_description', 'meta_description '
        }
        
        for col, val in row.items():
            col_clean = str(col).strip()
            if col_clean not in excluded_cols and val and str(val).strip() and str(val).lower() != 'nan':
                fm.append(f"{col_clean}: {json.dumps(str(val).strip())}")

        stock_str = str(stock_val).lower()
        if stock_str in ['0', '0 vnt.', 'parduota']:
            fm.append("is_sold: true")
        else:
            fm.append("is_sold: false")
            
    if hero_image:
        fm.append(f"hero_image: {json.dumps(hero_image)}")
        
    if gallery_images:
        fm.append("gallery_images:")
        for g in gallery_images:
            fm.append(f"  - {json.dumps(g)}")
            
    search_cloud_val = row.get('search_cloud', '')
    if search_cloud_val and str(search_cloud_val).lower() != 'nan':
        clouds = [c.strip() for c in str(search_cloud_val).replace('\n', ',').split(',') if c.strip()]
        if clouds:
            fm.append("search_cloud:")
            for sc in clouds:
                fm.append(f"  - {json.dumps(sc)}")

    fm.append("---\n")
    
    content_body = str(row.get('content_body', '')).strip()
    if not content_body or content_body.lower() == 'nan':
        content_body = str(row.get('content', '')).strip()
    
    filename = f"{slug}.md"
    filepath = os.path.join(content_dir, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("\n".join(fm))
        if content_body and content_body.lower() != 'nan':
            f.write(content_body + "\n")

# Automatyczne czyszczenie starych plików produktów, które zniknęły z arkusza (chroniąc _index.md oraz sandelyje.md)
for filename in os.listdir(content_dir):
    if filename.endswith(".md") and filename not in ["_index.md", "sandelyje.md"]:
        file_slug = filename[:-3]
        if file_slug not in valid_slugs:
            old_path = os.path.join(content_dir, filename)
            os.remove(old_path)
            print(f"Pašalintas pasenęs failas: {filename}")

# Bezpieczne usunięcie starego folderu podrzędnego, jeśli jeszcze istnieje
old_sandelyje_dir = os.path.join(content_dir, "sandelyje")
if os.path.exists(old_sandelyje_dir):
    shutil.rmtree(old_sandelyje_dir)

print("Generavimas sėkmingai baigtas!")
