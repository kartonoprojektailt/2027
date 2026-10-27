import os
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
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
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
    
    price = sanitize_text(str(row.get('price', '')))
    unit = sanitize_text(str(row.get('unit', '')))
    stock = sanitize_text(str(row.get('stock', '')))
    
    gallery_raw = sanitize_text(str(row.get('gallery_images', '')))
    gallery_list = [fix_gdrive_url(img.strip(), max_width=800) for img in gallery_raw.split(',') if img.strip()]
    
    source_tab = str(row.get('source_tab', ''))
    
    if not title and not content_body:
        continue
        
    if source_tab == 'puslapiai' and slug.lower() == 'sandelyje':
        file_path = "content/sandelyje/_index.md"
    elif source_tab == 'sandelyje':
        if not slug or slug.lower() == 'nan' or slug.lower() == 'sandelyje':
            continue
        file_path = f"content/sandelyje/{slug}/index.md"
    elif slug.lower() == 'paieska' or slug.lower() == 'search':
        file_path = "content/search.md"
    elif not slug or slug.lower() == 'nan' or slug.lower() == 'index' or slug == '/':
        file_path = "content/_index.md"
    else:
        file_path = f"content/{slug}/index.md"

    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    gallery_yaml = "\n".join([f"  - \"{img}\"" for img in gallery_list])
    gallery_block = f"\ngallery_images:\n{gallery_yaml}" if gallery_yaml else ""

    cloud_yaml = "\n".join([f"  - \"{tag}\"" for tag in cloud_list])
    cloud_block = f"\nsearch_cloud:\n{cloud_yaml}" if cloud_yaml else ""

    hero_block = f"\nhero_image: \"{hero_image}\"" if hero_image else ""
    desc_block = f"\ndescription: \"{meta_desc}\"" if meta_desc else ""
    
    code_block = f"\noffer_code: \"{code}\"" if code else ""
    cat_block = f"\ncategory: \"{category}\"\ncategory_url: \"{category_url}\"" if category else ""
    price_block = f"\nprice: \"{price}\"" if price else ""
    unit_block = f"\nunit: \"{unit}\"" if unit else ""
    stock_block = f"\nstock: \"{stock}\"" if stock else ""

    if file_path == "content/search.md":
        markdown_content = """---
title: "Paieška"
description: "Kartono projektai paieška"
layout: "search"
---
"""
    elif file_path == "content/sandelyje/_index.md":
        markdown_content = f"""---
title: "{title}"{desc_block}{hero_block}{gallery_block}{cloud_block}
draft: false
type: "sandelyje"
layout: "list"
---

{content_body}
"""
    else:
        markdown_content = f"""---
title: "{title}"{desc_block}{hero_block}{gallery_block}{cloud_block}{code_block}{cat_block}{price_block}{unit_block}{stock_block}
draft: false
---

{content_body}
"""

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
    print(f"Įrašyta: {file_path}")

print("Vykdomas Git sinchronizavimas...")
try:
    subprocess.run(["git", "add", "-A"], check=True)
    status_res = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True)
    if status_res.stdout.strip():
        subprocess.run(["git", "commit", "-m", "Fix search page layout collision and remove search folder"], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print("Valio! Visi pakeitimai iškeliavo į GitHub.")
    else:
        print("Jokių naujų pakeitimų faile nėra.")
except subprocess.CalledProcessError as e:
    print(f"Klaida vykdant Git: {e}")
