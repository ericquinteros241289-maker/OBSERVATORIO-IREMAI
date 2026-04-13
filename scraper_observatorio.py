import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, unquote

BASE_FOLDER = "Observatorios"
BASE_URL = "https://iremai.wordpress.com/observatorio-4"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; IREMAI-Observatorio-Downloader/3.0)"
}

session = requests.Session()
session.headers.update(HEADERS)


def safe_filename(name):
    name = unquote(name)
    name = re.sub(r'[\\/*?:"<>|]', "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name or "archivo.pdf"


def extract_year(text):
    if not text:
        return None

    years = re.findall(r"\b(20\d{2})\b", text)
    years = [int(y) for y in years if 2010 <= int(y) <= 2035]
    if years:
        return max(years)

    dates = re.findall(r"\(?(\d{2})/(\d{2})/(\d{2})\)?", text)
    if dates:
        yy = int(dates[-1][2])
        return 2000 + yy

    return None


def get_filename_from_url(url):
    path = urlparse(url).path
    filename = os.path.basename(path)
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"
    return safe_filename(filename)


def ensure_folder(path):
    os.makedirs(path, exist_ok=True)


def download_file(url, destination):
    with session.get(url, stream=True, timeout=90) as r:
        r.raise_for_status()
        with open(destination, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)


def find_content_blocks(soup):
    blocks = soup.find_all(["article", "li", "div"])
    useful = []

    for b in blocks:
        text = b.get_text(" ", strip=True)
        hrefs = [a.get("href", "") for a in b.find_all("a", href=True)]
        if any(".pdf" in h.lower() for h in hrefs):
            useful.append(b)

    return useful


def main():
    ensure_folder(BASE_FOLDER)

    seen_links = set()
    consecutive_pages_without_new_pdfs = 0
    page = 1
    max_pages_to_try = 30

    while page <= max_pages_to_try:
        url = BASE_URL if page == 1 else f"{BASE_URL}/page/{page}/"
        print(f"\nProcesando página {page}: {url}")

        try:
            r = session.get(url, timeout=30)
            if r.status_code != 200:
                print(f"Página no disponible ({r.status_code}).")
                break
        except requests.RequestException as e:
            print(f"Error accediendo a {url}: {e}")
            break

        soup = BeautifulSoup(r.text, "html.parser")
        blocks = find_content_blocks(soup)

        page_new_pdfs = 0

        for block in blocks:
            text_full = block.get_text(" ", strip=True)
            year = extract_year(text_full)

            for a in block.find_all("a", href=True):
                link = a["href"].strip()
                if ".pdf" not in link.lower():
                    continue

                if link in seen_links:
                    continue
                seen_links.add(link)

                anchor_text = a.get_text(" ", strip=True)
                filename = get_filename_from_url(link)

                final_year = year or extract_year(anchor_text) or extract_year(filename)
                folder_name = str(final_year) if final_year else "Sin_clasificar"
                folder = os.path.join(BASE_FOLDER, folder_name)
                ensure_folder(folder)

                destination = os.path.join(folder, filename)

                try:
                    print(f"Descargando: {filename} -> {folder_name}")
                    download_file(link, destination)
                    page_new_pdfs += 1
                except requests.RequestException as e:
                    print(f"Error descargando {link}: {e}")

        if page_new_pdfs == 0:
            consecutive_pages_without_new_pdfs += 1
        else:
            consecutive_pages_without_new_pdfs = 0

        if consecutive_pages_without_new_pdfs >= 2:
            print("No se encontraron PDFs nuevos en dos páginas seguidas. Fin.")
            break

        page += 1

    print(f"\nTotal de PDFs descargados: {len(seen_links)}")


if __name__ == "__main__":
    main()
