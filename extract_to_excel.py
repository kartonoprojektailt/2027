import os
import glob
import csv
import re

content_dir = "content"
output_filename = "Master_content_kp_real.csv"

def clean_text(text):
    if not isinstance(text, str):
        return ""
    # Pašaliname Markdown žymes
    text = re.sub(r'^---[\s\S]*?---\s*', '', text)
    text = re.sub(r'^\s*[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    return text.strip()

def parse_markdown_sections(filepath):
    """Nuskaito .md failą ir iškarpo dalis į teisingus stulpelius pagal antraštes"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    title = ""
    description = ""
    
    # Ištraukiame frontmatter (title, description)
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            frontmatter_str = parts[1]
            body = parts[2].strip()
            for line in frontmatter_str.split("\n"):
                if line.startswith("title:"):
                    title = line.split(":", 1)[1].strip().strip('"\'')
                elif line.startswith("description:"):
                    description = line.split(":", 1)[1].strip().strip('"\'')
        else:
            body = content
    else:
        body = content

    # Numatyta reiksmes
    h1_text = title
    intro_text = ""
    specs_data = ""
    categories_content = ""
    human_text = ""
    order_process = "Užsakymo ir gamybos eiga: Susisiekite su mumis, pateikite užklausą."
    cta_contacts = "Susisiekite su mumis ir pateikite užklausą."

    # Paprastas sekcijų išskyrimas pagal antraštes
    sections = re.split(r'\n##\s+', body)
    
    # Pirmas blokas (iki pirmos ## antraštės) yra įvadas / H1
    if sections:
        first_part = sections[0].strip()
        # Jei yra # H1 antraštė
        h1_match = re.search(r'^#\s+(.+)$', first_part, re.MULTILINE)
        if h1_match:
            h1_text = h1_match.group(1).strip()
            intro_text = clean_text(first_part.replace(h1_match.group(0), ''))
        else:
            intro_text = clean_text(first_part)

    # Pereiname per likusias sekcijas ir sudeliojame į vietas
    for sec in sections[1:]:
        sec_lower = sec.lower()
        if "gamybos galimybės" in sec_lower or "specifikacija" in sec_lower or "parametrai" in sec_lower:
            specs_data = clean_text(sec)
        elif "kryptys" in sec_lower or "paslaugos" in sec_lower or "asortimentas" in sec_lower:
            categories_content = clean_text(sec)
        elif "apie mus" in sec_lower or "pasiekimai" in sec_lower:
            human_text = clean_text(sec)
        elif "užsakymo" in sec_lower or "eiga" in sec_lower:
            order_process = clean_text(sec)
        elif "kontaktai" in sec_lower or "rekvizitai" in sec_lower:
            cta_contacts = clean_text(sec)
        else:
            # Jei netelpa niekur kitur, pridedame prie human_text
            human_text += "\n\n" + clean_text(sec)

    if not human_text:
        human_text = clean_text(body)

    return title, description, h1_text, intro_text, specs_data, categories_content, human_text, order_process, cta_contacts

if not os.path.exists(content_dir):
    print(f"Klaida: nerastas '{content_dir}' katalogas.")
    exit(1)

headers = [
    "file_path", "page_title", "description", "intro_heading_h1", 
    "intro_text", "gallery_placeholder", "specs_heading_h2", 
    "specs_table_data", "categories_heading_h2", "categories_content", 
    "human_text", "order_process", "cta_and_contacts"
]

rows = []

for filepath in glob.glob(f"{content_dir}/**/*.md", recursive=True):
    title, description, h1_text, intro_text, specs_data, categories_content, human_text, order_process, cta_contacts = parse_markdown_sections(filepath)
    
    row = [
        filepath,
        title,
        description,
        h1_text,
        intro_text,
        "Galerija",
        "Gamybos galimybės ir techninė specifikacija",
        specs_data,
        "Pagrindinės gamybos ir paslaugų kryptys",
        categories_content,
        human_text,
        order_process,
        cta_contacts
    ]
    rows.append(row)

with open(output_filename, 'w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(headers)
    writer.writerows(rows)

print(f"Sėkmingai nuskaityta ir išskirstyta puslapių: {len(rows)}")
print(f"Sukurtas tvarkingas failas: {output_filename}")
