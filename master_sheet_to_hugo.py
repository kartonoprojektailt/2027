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
    
    # 1. Zakładka główna ze stronami 'puslapiai'
    df_puslapiai = pd.DataFrame(spreadsheet.worksheet("puslapiai").get_all_records())
    df_puslapiai['source_tab'] = 'puslapiai'
    
    dfs_to_concat = [df_puslapiai]
    
    # 2. Zakładka magazynowa / ogłoszenia 'sandelyje'
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

# Usuwamy błędny plik index.md z głównego folderu content (zapobiega konfliktom)
rogue_index = "content/index.md"
if os.path.exists(rogue_index):
    os.remove(rogue_index)
    print("Pašalintas klaidingas 'content/index.md' iš pagrindinio aplanko.")

for index, row in df.iterrows():
    slug = sanitize_text(str(row.get('slug', '')))
    title = sanitize_text(str(row.get('title', '')))
    meta_desc = sanitize_text(str(row.get('meta_description', '')))
    content_body = sanitize_text(str(row.get('content_body', '')))
    hero_image = sanitize_text(str(row.get('hero_image', '')))
    search_cloud = sanitize_text(str(row.get('search_cloud', '')))
    
    # Nowe pola dla ogłoszeń magazynowych
    code = sanitize_text(str(row.get('code', '')))
    category = sanitize_text(str(row.get('category', '')))
    price = sanitize_text(str(row.get('price', '')))
    unit = sanitize_text(str(row.get('unit', '')))
    stock = sanitize_text(str(row.get('stock', '')))
    
    # Obsługa galerii zdjęć po przecinku
    gallery_raw = sanitize_text(str(row.get('gallery_images', '')))
    gallery_list = [img.strip() for img in gallery_raw.split(',') if img.strip()]
    
    source_tab = str(row.get('source_tab', ''))
    
    if not title and not content_body:
        continue
        
    # Mapowanie ścieżek
    if source_tab == 'puslapiai' and slug.lower() == 'sandelyje':
        file_path = "content/sandelyje/_index.md"
    elif source_tab == 'sandelyje' and slug and slug.lower() != 'nan':
        file_path = f"content/sandelyje/{slug}/index.md"
    elif not slug or slug.lower() == 'nan' or slug.lower() == 'index' or slug == '/':
        file_path = f"content/_index.md"
    else:
        file_path = f"content/{slug}/index.md"

    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    # Budowanie nagłówka YAML
    gallery_yaml = "\n".join([f"  - \"{img}\"" for img in gallery_list])
    gallery_block = f"\ngallery_images:\n{gallery_yaml}" if gallery_yaml else ""

    hero_block = f"\nhero_image: \"{hero_image}\"" if hero_image else ""
    desc_block = f"\ndescription: \"{meta_desc}\"" if meta_desc else ""
    cloud_block = f"\nsearch_cloud: \"{search_cloud}\"" if search_cloud else ""
    
    # Bloki dla magazynu
    code_block = f"\noffer_code: \"{code}\"" if code else ""
    cat_block = f"\ncategory: \"{category}\"" if category else ""
    price_block = f"\nprice: \"{price}\"" if price else ""
    unit_block = f"\nunit: \"{unit}\"" if unit else ""
    stock_block = f"\nstock: \"{stock}\"" if stock else ""

    # Szablon pliku Markdown
    if file_path == "content/sandelyje/_index.md":
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

# Git Push
print("Vykdomas Git sinchronizavimas...")
try:
    subprocess.run(["git", "add", "-A"], check=True)
    status_res = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True)
    if status_res.stdout.strip():
        subprocess.run(["git", "commit", "-m", "Sync updated inventory schema"], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print("Valio! Visi pakeitimai iškeliavo į GitHub ir Cloudflare Pages atsinaujins akimirksniu.")
    else:
        print("Jokių naujų pakeitimų faile nėra.")
except subprocess.CalledProcessError as e:
    print(f"Klaida vykdant Git: {e}")
