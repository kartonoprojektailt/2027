import os
import secrets
import shutil
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
import fitz  # PyMuPDF do konwersji PDF -> obrazki w tle

app = Flask(__name__)
app.secret_key = secrets.token_hex(24)

HUGO_CONTENT_DIR = os.path.abspath("../content/sandelyje")
UPLOAD_FOLDER = os.path.abspath("../static/uploads")

os.makedirs(HUGO_CONTENT_DIR, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin") 

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('index'))
        flash('Neteisingas slaptažodis!', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    listings = []
    if os.path.exists(HUGO_CONTENT_DIR):
        for item in sorted(os.listdir(HUGO_CONTENT_DIR), reverse=True):
            item_path = os.path.join(HUGO_CONTENT_DIR, item)
            if os.path.isdir(item_path):
                md_file = os.path.join(item_path, 'index.md')
                if os.path.exists(md_file):
                    with open(md_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        listings.append({'folder': item, 'preview': content[:150]})
    return render_template('index.html', listings=listings)

@app.route('/publish', methods=['GET', 'POST'])
def publish():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        title = request.form.get('title')
        category = request.form.get('category')
        price = request.form.get('price')
        stock_qty = request.form.get('stock_qty')
        stock_unit = request.form.get('stock_unit', 'vnt.')
        status = request.form.get('status', 'aktyvus')
        description = request.form.get('description')
        specs = request.form.get('specs')
        application = request.form.get('application')
        manager_email = "info@kartonoprojektai.lt"
        
        # Generowanie kodu: kp + DATA + inteligentny sufiks literowy
        date_str = datetime.now().strftime('%Y%m%d')
        prefix = f"kp{date_str}"
        
        existing_suffixes = []
        if os.path.exists(HUGO_CONTENT_DIR):
            for item in os.listdir(HUGO_CONTENT_DIR):
                if item.startswith(prefix):
                    rest = item[len(prefix):]
                    suffix = rest.split('-')[0]
                    if suffix and suffix.isalpha():
                        existing_suffixes.append(suffix.lower())
        
        def get_next_suffix(existing):
            def num_to_letters(n):
                result = ""
                while n >= 0:
                    result = chr(ord('a') + (n % 26)) + result
                    n = n // 26 - 1
                return result

            if not existing:
                return 'a'
            max_val = -1
            for s in existing:
                val = 0
                for char in s:
                    val = val * 26 + (ord(char) - ord('a') + 1)
                if val > max_val:
                    max_val = val
            return num_to_letters(max_val)

        next_suffix = get_next_suffix(existing_suffixes)
        offer_code = f"{prefix}{next_suffix}"
        
        safe_title_slug = ''.join(c if c.isalnum() else '-' for c in title.lower())
        while '--' in safe_title_slug:
            safe_title_slug = safe_title_slug.replace('--', '-')
        safe_title_slug = safe_title_slug.strip('-')[:40]
        
        folder_name = f"{offer_code}-{safe_title_slug}"
        offer_dir = os.path.join(HUGO_CONTENT_DIR, folder_name)
        os.makedirs(offer_dir, exist_ok=True)
        
        # Obsługa wielu zdjęć
        image_paths = []
        for file in request.files.getlist('images'):
            if file and file.filename:
                filename = f"{offer_code}_{secure_filename(file.filename)}"
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                image_paths.append(f"/uploads/{filename}")
                
        images_yaml = "\n".join([f"  - \"{img}\"" for img in image_paths]) if image_paths else "  - \"/images/default.jpg\""
        
        # Obsługa wielu plików PDF oraz konwersja stron na obrazki podglądu
        pdf_docs = []
        tech_image_paths = []
        
        for file in request.files.getlist('pdf_files'):
            if file and file.filename:
                orig_name = file.filename
                safe_name = secure_filename(orig_name)
                filename = f"{offer_code}_{safe_name}"
                pdf_save_path = os.path.join(UPLOAD_FOLDER, filename)
                file.save(pdf_save_path)
                
                pdf_docs.append({
                    'name': orig_name,
                    'url': f"/uploads/{filename}"
                })
                
                try:
                    doc = fitz.open(pdf_save_path)
                    for page_index, page in enumerate(doc):
                        pix = page.get_pixmap(dpi=150)
                        img_filename = f"{offer_code}_page_{page_index}_{safe_name}.png"
                        img_save_path = os.path.join(UPLOAD_FOLDER, img_filename)
                        pix.save(img_save_path)
                        tech_image_paths.append(f"/uploads/{img_filename}")
                except Exception as e:
                    print(f"Błąd konwersji PDF do obrazu: {e}")
                
        pdf_yaml_lines = []
        if pdf_docs:
            pdf_yaml_lines.append("pdf_documents:")
            for doc in pdf_docs:
                pdf_yaml_lines.append(f"  - title: \"{doc['name']}\"")
                pdf_yaml_lines.append(f"    url: \"{doc['url']}\"")
        pdf_yaml = "\n".join(pdf_yaml_lines)

        tech_images_yaml_lines = []
        if tech_image_paths:
            tech_images_yaml_lines.append("tech_images:")
            for img_path in tech_image_paths:
                tech_images_yaml_lines.append(f"  - \"{img_path}\"")
        tech_images_yaml = "\n".join(tech_images_yaml_lines)

        md_content = f"""---
title: "{title}"
date: {datetime.now().strftime('%Y-%m-%dT%H:%M:%S+03:00')}
draft: false
description: "{description[:120]}"
offer_code: "{offer_code}"
category: "{category}"
price: "{price}"
stock: "{stock_qty} {stock_unit}"
status: "{status}"
manager_email: "{manager_email}"
images:
{images_yaml}
{pdf_yaml}
{tech_images_yaml}
---

### Aprašymas
{description}

### Techninės specifikacijos
{specs}

### Paskirtis ir taikymo sritys
{application}
"""
        with open(os.path.join(offer_dir, 'index.md'), 'w', encoding='utf-8') as f:
            f.write(md_content)
            
        flash(f'Pasiūlymas sėkmingai publikuotas! Kodas: {offer_code}', 'success')
        return redirect(url_for('index'))
        
    return render_template('edit.html')

@app.route('/delete/<folder_name>', methods=['POST'])
def delete_offer(folder_name):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    safe_folder = secure_filename(folder_name)
    folder_path = os.path.join(HUGO_CONTENT_DIR, safe_folder)
    
    if os.path.exists(folder_path) and os.path.isdir(folder_path):
        offer_code = safe_folder.split('-')[0]
        if os.path.exists(UPLOAD_FOLDER):
            for file in os.listdir(UPLOAD_FOLDER):
                if file.startswith(offer_code):
                    try:
                        os.remove(os.path.join(UPLOAD_FOLDER, file))
                    except:
                        pass
        shutil.rmtree(folder_path)
        flash(f'Pasiūlymas {safe_folder} sėkmingai ištrintas!', 'success')
    else:
        flash('Pasiūlymas nerastas.', 'error')
        
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)
