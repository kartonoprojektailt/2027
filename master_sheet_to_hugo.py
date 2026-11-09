import os
import json
import tempfile
import shutil
import urllib.request
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
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
df = None
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

if df is None or df.empty:
    print("[KLAIDA] DataFrame `df` jest pusty lub nie został zainicjalizowany.")
    exit(1)

images_dir = os.path.join("static", "images")
content_dir = "content"
data_dir = "data"

os.makedirs(images_dir, exist_ok=True)
os.makedirs(content_dir, exist_ok=True)
os.makedirs(data_dir, exist_ok=True)

def is_valid_val(val):
    if val is None:
        return False
    s = str(val).strip().lower()
    return bool(s and s != 'nan' and s != 'none' and s != 'null' and s != 'undefined')

def clean_slug(val):
    if not is_valid_val(val):
        return ""
    slug = str(val).strip().lower()
    slug = ''.join(c for c in unicodedata.normalize('NFD', slug) if unicodedata.category(c) != 'Mn')
    slug = re.sub(r'[^a-z0-9_-]', '-', slug)
    return re.sub(r'-+', '-', slug).strip('-')

def extract_gdrive_id(url):
    if not isinstance(url, str) or not url.strip():
        return ""
    url = url.strip().split()[0]
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
    if not is_valid_val(url):
        return ""
    url = str(url).strip().split()[0]
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
            
    return public_url_path if os.path.exists(local_filepath) and os.path.getsize(local_filepath) > 1000 else ""

def process_gallery_concurrently(urls, slug):
    gallery_images = []
    if not urls:
        return gallery_images
        
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(download_and_cache_image, u, f"{slug}-g{idx}") 
            for idx, u in enumerate(urls, start=1)
        ]
        for future in futures:
            res = future.result()
            if res:
                gallery_images.append(res)
    return gallery_images

print("Generuojami Markdown puslapiai ir prekės iš Google Sheets...")

valid_slugs = {"sandelyje", "_index", "search"}

search_file_path = os.path.join(content_dir, "search.md")
search_markdown = """---
title: "Paieška"
slug: "search"
layout: "search"
description: "Kartono projektai paieška ir inžineriniai raktažodžiai"
---
"""
with open(search_file_path, 'w', encoding='utf-8') as f:
    f.write(search_markdown)

llms_lines = []
matrix_tree = {}

for _, row in df.iterrows():
    raw_slug = str(row.get('slug', '')).strip()
    title_raw = str(row.get('title', '')).strip()
    
    content_body = str(row.get('content_body', '')).strip()
    if not is_valid_val(content_body):
        content_body = str(row.get('content', '')).strip()
    
    content_body = re.sub(r'UAB\s+Kartono\s+projektai', '', content_body, flags=re.IGNORECASE).strip()

    cat_name = str(row.get('category', '')).strip()
    menu_t = str(row.get('menu_title', '')).strip() or title_raw
    cloud_raw = str(row.get('search_cloud', '')).strip()
    
    if is_valid_val(cat_name) and cat_name != 'Unikalus puslapio adresas':
        if cat_name not in matrix_tree:
            matrix_tree[cat_name] = {}
        
        clouds_list = []
        if is_valid_val(cloud_raw):
            clouds_list = [c.strip() for c in cloud_raw.replace('\n', ',').split(',') if is_valid_val(c.strip())]
            
        if is_valid_val(menu_t) and menu_t != 'Pavadinimas':
            matrix_tree[cat_name][menu_t] = clouds_list

    if raw_slug in ['_index', 'index', '/'] or "kartoninės pakuotės" in title_raw.lower():
        title = title_raw if is_valid_val(title_raw) else "Pradžia"
        
        hero_raw = row.get('hero_image', '')
        hero_image = download_and_cache_image(hero_raw, "index-hero") if is_valid_val(hero_raw) else ""
        
        fm = [
            "---",
            f"title: {json.dumps(title)}",
            f"slug: {json.dumps('_index')}",
            'type: "page"',
        ]
        
        meta_desc = row.get('meta_description ', '') or row.get('meta_description', '')
        if is_valid_val(meta_desc):
            fm.append(f"description: {json.dumps(str(meta_desc).strip())}")
            
        if hero_image:
            fm.append(f"hero_image: {json.dumps(hero_image)}")
            fm.append(f"image: {json.dumps(hero_image)}")
            fm.append(f"featured_image: {json.dumps(hero_image)}")
            fm.append("cover:")
            fm.append(f"  image: {json.dumps(hero_image)}")
            
        gallery_images = []
        gallery_raw = row.get('gallery_images', '')
        if is_valid_val(gallery_raw):
            urls = [u.strip() for u in str(gallery_raw).replace('\n', ',').split(',') if is_valid_val(u.strip())]
            gallery_images = process_gallery_concurrently(urls, "index")
            
        if gallery_images:
            fm.append("gallery_images:")
            for g in gallery_images:
                fm.append(f"  - {json.dumps(g)}")
                
        search_cloud_val = row.get('search_cloud', '')
        if is_valid_val(search_cloud_val):
            clouds = [c.strip() for c in str(search_cloud_val).replace('\n', ',').split(',') if is_valid_val(c.strip())]
            if clouds:
                fm.append("search_cloud:")
                for sc in clouds:
                    fm.append(f"  - {json.dumps(sc)}")

        fm.append("---\n")
        
        filepath = os.path.join(content_dir, "_index.md")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("\n".join(fm))
            if is_valid_val(content_body):
                f.write(content_body + "\n")
        continue

    slug = clean_slug(raw_slug)
    if not slug or slug in ['unikalus-puslapio-adresas', 'search']:
        continue
        
    title = title_raw if is_valid_val(title_raw) else slug
    
    if "sandėlio pasiūlymai" in title.lower() and slug != "sandelyje":
        continue

    source_tab = str(row.get('source_tab', 'puslapiai')).strip()
    
    if slug == "sandelyje":
        valid_slugs.add("sandelyje")
        hero_raw = row.get('hero_image', '')
        hero_image = download_and_cache_image(hero_raw, slug) if is_valid_val(hero_raw) else ""
        
        fm = [
            "---",
            f"title: {json.dumps(title)}",
            f"slug: {json.dumps(slug)}",
            'type: "sandelyje"',
            'layout: "list"',
            f"url: {json.dumps('/sandelyje/')}"
        ]
        
        meta_desc = row.get('meta_description ', '') or row.get('meta_description', '')
        if is_valid_val(meta_desc):
            fm.append(f"description: {json.dumps(str(meta_desc).strip())}")
            
        if hero_image:
            fm.append(f"hero_image: {json.dumps(hero_image)}")
            fm.append(f"image: {json.dumps(hero_image)}")
            
        fm.append("---\n")
        
        filepath = os.path.join(content_dir, "sandelyje.md")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("\n".join(fm))
            if is_valid_val(content_body):
                f.write(content_body + "\n")
        continue

    valid_slugs.add(slug)

    hero_raw = row.get('hero_image', '')
    hero_image = download_and_cache_image(hero_raw, slug) if is_valid_val(hero_raw) else ""
    
    gallery_images = []
    gallery_raw = row.get('gallery_images', '')
    if is_valid_val(gallery_raw):
        urls = [u.strip() for u in str(gallery_raw).replace('\n', ',').split(',') if is_valid_val(u.strip())]
        gallery_images = process_gallery_concurrently(urls, slug)

    fm = [
        "---",
        f"title: {json.dumps(title)}",
        f"slug: {json.dumps(slug)}",
        f"type: {json.dumps('sandelyje' if source_tab == 'sandelyje' else 'page')}",
    ]
    
    menu_title_val = row.get('menu_title', '')
    if is_valid_val(menu_title_val):
        fm.append(f"menu_title: {json.dumps(str(menu_title_val).strip())}")
    else:
        fm.append(f"menu_title: {json.dumps(title)}")
    
    meta_desc = row.get('meta_description ', '') or row.get('meta_description', '')
    if is_valid_val(meta_desc):
        fm.append(f"description: {json.dumps(str(meta_desc).strip())}")
        
    if source_tab == 'sandelyje':
        fm.append(f"url: {json.dumps('/' + slug + '/')}")
        fm.append('layout: "single"')
        
        code_val = row.get('code', '')
        if is_valid_val(code_val):
            code_str = str(code_val).strip()
            fm.append(f"code: {json.dumps(code_str)}")
            fm.append(f"offer_code: {json.dumps(code_str)}")
            fm.append(f"sku: {json.dumps(code_str)}")
            
        category_val = row.get('category', '')
        if is_valid_val(category_val):
            fm.append(f"category: {json.dumps(str(category_val).strip())}")
            
        price_val = row.get('price', '')
        if is_valid_val(price_val):
            fm.append(f"price: {json.dumps(str(price_val).strip())}")
            fm.append(f"kaina: {json.dumps(str(price_val).strip())}")
            
        unit_val = row.get('unit', '')
        if is_valid_val(unit_val):
            fm.append(f"unit: {json.dumps(str(unit_val).strip())}")
            
        stock_val = row.get('stock', '')
        if is_valid_val(stock_val):
            stock_str = str(stock_val).strip()
            fm.append(f"stock: {json.dumps(stock_str)}")
            fm.append(f"likutis: {json.dumps(stock_str)}")
            
            stock_clean_digits = re.sub(r'[^0-9]', '', stock_str)
            if stock_clean_digits == '0' or 'parduota' in stock_str.lower():
                fm.append("is_sold: true")
            else:
                fm.append("is_sold: false")
        else:
            fm.append("is_sold: false")
            
        sale_reason_val = row.get('sale_reason', '')
        if is_valid_val(sale_reason_val):
            fm.append(f"sale_reason: {json.dumps(str(sale_reason_val).strip())}")

        p_code = str(row.get('code', '')).strip()
        p_price = str(row.get('price', '')).strip()
        p_stock = str(row.get('stock', '')).strip()
        p_cat = str(row.get('category', '')).strip()
        if title and slug:
            p_url = f"https://kartonoprojektai.lt/sandelyje/{slug}/"
            llms_lines.append(f"- [{title} (/{slug}/)]({p_url}) - Kod: {p_code}, Kaina: {p_price} EUR, Likutis: {p_stock} vnt. Kategorija: {p_cat}")

        # UKRYWANIE PÓL "Image:" i "Menu Title:" Z GOOGLE SHEETS DLA PODSTRONY OGŁOSZENIA
        excluded_cols = {
            'slug', 'title', 'menu_title', 'menu title', 'image', 'code', 'offer_code', 'sku', 'category', 
            'price', 'kaina', 'unit', 'stock', 'likutis', 'sale_reason', 
            'hero_image', 'gallery_images', 'search_cloud', 'content_body', 
            'content', 'source_tab', 'meta_description', 'meta_description '
        }
        
        for col, val in row.items():
            col_clean = str(col).strip()
            if col_clean not in excluded_cols and is_valid_val(val):
                fm.append(f"{col_clean}: {json.dumps(str(val).strip())}")

    if hero_image:
        fm.append(f"hero_image: {json.dumps(hero_image)}")
        fm.append(f"image: {json.dumps(hero_image)}")
        
    if gallery_images:
        fm.append("gallery_images:")
        for g in gallery_images:
            fm.append(f"  - {json.dumps(g)}")
            
    search_cloud_val = row.get('search_cloud', '')
    if is_valid_val(search_cloud_val):
        clouds = [c.strip() for c in str(search_cloud_val).replace('\n', ',').split(',') if is_valid_val(c.strip())]
        if clouds:
            fm.append("search_cloud:")
            for sc in clouds:
                fm.append(f"  - {json.dumps(sc)}")

    fm.append("---\n")
    
    filename = f"{slug}.md"
    filepath = os.path.join(content_dir, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("\n".join(fm))
        if is_valid_val(content_body):
            f.write(content_body + "\n")

matrix_filepath = os.path.join(data_dir, "search_matrix.json")
with open(matrix_filepath, 'w', encoding='utf-8') as f:
    json.dump(matrix_tree, f, ensure_ascii=False, indent=2)
print("Pomyślnie wygenerowano plik data/search_matrix.json z danymi dla wyszukiwarki.")

llms_filepath = os.path.join(content_dir, "llms.txt")
with open(llms_filepath, 'w', encoding='utf-8') as f:
    f.write("\n".join(llms_lines) + "\n")
print("Plik llms.txt został pomyślnie zaktualizowany z Google Sheets.")

for filename in os.listdir(content_dir):
    if filename.endswith(".md") and filename not in ["_index.md", "search.md", "llms.txt"]:
        file_slug = filename[:-3]
        if file_slug not in valid_slugs:
            old_path = os.path.join(content_dir, filename)
            os.remove(old_path)
            print(f"Pašalintas pasenęs failas: {filename}")

old_sandelyje_dir = os.path.join(content_dir, "sandelyje")
if os.path.exists(old_sandelyje_dir):
    shutil.rmtree(old_sandelyje_dir)

print("Generavimas sėkmingai baigtas!")
