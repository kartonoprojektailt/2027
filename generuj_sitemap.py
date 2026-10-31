import csv
import xml.etree.ElementTree as ET
from xml.dom import minidom

# 1. Twój adres bazowy domeny (musi mieć https:// na początku i BRAK slasha na końcu)
BASE_URL = "https://kartonoprojektai.lt"

# 2. Nazwa Twojego pliku CSV z danymi
CSV_FILE = "dane.csv" 

# Tworzenie głównego elementu XML
urlset = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")

# --- Dodanie strony głównej ---
url_elem = ET.SubElement(urlset, "url")
loc_elem = ET.SubElement(url_elem, "loc")
loc_elem.text = f"{BASE_URL}/"

# --- Odczytanie adresów z pliku CSV ---
# Zmień 'sciezka' na nazwę kolumny w Twoim pliku CSV, która zawiera adresy podstron
try:
    with open(CSV_FILE, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Pobieramy ścieżkę z CSV (np. "/sandelyje/a3-balto-kartono-lapai-kp20261016b/")
            path = row['sciezka'].strip()
            
            # Upewniamy się, że ścieżka zaczyna się od slasha
            if not path.startswith('/'):
                path = '/' + path
                
            # Łączymy domenę ze ścieżką -> https://kartonoprojektai.lt/sandelyje/...
            full_url = f"{BASE_URL}{path}"
            
            # Dodajemy wpis do XML
            url_node = ET.SubElement(urlset, "url")
            loc_node = ET.SubElement(url_node, "loc")
            loc_node.text = full_url

    # Ładne formatowanie pliku XML (wcięcia)
    xml_str = minidom.parseString(ET.tostring(urlset, encoding='utf-8')).toprettyxml(indent="  ")

    # Zapis do pliku sitemap.xml w folderze static/ lub root
    with open("static/sitemap.xml", "w", encoding="utf-8") as xml_file:
        xml_file.write(xml_str)

    print("SUKCES: Plik static/sitemap.xml został poprawnie wygenerowany!")

except Exception as e:
    print(f"BŁĄD: {e}")
