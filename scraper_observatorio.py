import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, unquote

BASE_FOLDER = "Observatorios"
BASE_URL = "https://iremai.wordpress.com/observatorio-4"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; IREMAI-Observatorio-Downloader/2.0)"
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

    text = text.strip()

    # Prioridad 1: años de 4 dígitos
    years = re.findall(r"\b(20\d{2})\b", text)
    if years:
        years = [int(y) for y in years if 2010 <= int(y) <= 2035]
        if years:
            return max(years)

    # Prioridad 2: fechas tipo 10/04/26 o (10/04/26)
    dates = re.findall(r"\(?(\d{2})/(\d{2})/(\d{2})\)?", text)
    if dates:
        yy = int(dates[-1][2])
        return 2000 + yy

    return None


def get_max_page():
    r = session.get(BASE_URL, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    pages = []
    for a in soup.find_all("a", class_="page-numbers"):
        txt = a.get_text(strip=True)
        if txt.isdigit():
            pages.append(int(txt))

    return max(pages) if pages else 1


def get_filename_from_url(url):
    path = urlparse(url).path
    filename = os.path.basename(path)
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"
    return safe_filename(filename)


def download_file(url, destination):
    with session.get(url, stream=True, timeout=90) as r:
        r.raise_for_status()
        with open(destination, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)


def ensure_folder(path):
    os.makedirs(path, exist_ok=True)


def possible_post_blocks(soup):
    blocks = []

    selectors = [
        "article",
        "div.post",
        "div.type-post",
        "div.hentry",
        "li",
    ]

    for sel in selectors:
        found = soup.select(sel)
        if found:
            blocks.extend(found)

    unique = []
    seen = set()
    for b in blocks:
        ident = id(b)
        if ident not in seen:
            unique.append(b)
            seen.add(ident)

    return unique


def block_text(block):
    return block.get_text(" ", strip=True)


def block_title(block):
    for tag in ["h1", "h2", "h3", "h4"]:
        t = block.find(tag)
        if t:
            txt = t.get_text(" ", strip=True)
            if txt:
                return txt

    t = block.find(class_=re.compile(r"(entry-title|post-title|archive-title)", re.I))
    if t:
        txt = t.get_text(" ", strip=True)
        if txt:
            return txt

    return None


def collect_pdf_links_from_block(block):
    links = []
    for a in block.find_all("a", href=True):
        href = a["href"].strip()
        if ".pdf" in href.lower():
            links.append((href, a.get_text(" ", strip=True)))
    return links


def main():
    ensure_folder(BASE_FOLDER)
    max_page = get_max_page()
    print(f"Se detectaron {max_page} páginas.")

    seen_links = set()

    for page in range(1, max_page + 1):
        url = BASE_URL if page == 1 else f"{BASE_URL}/page/{page}/"
        print(f"\nProcesando página: {url}")

        try:
            r = session.get(url, timeout=30)
            r.raise_for_status()
        except requests.RequestException as e:
            print(f"No se pudo acceder a {url}: {e}")
            continue

        soup = BeautifulSoup(r.text, "html.parser")
        blocks = possible_post_blocks(soup)

        print(f"Bloques detectados: {len(blocks)}")

        for block in blocks:
            text_full = block_text(block)
            title = block_title(block)
            year = extract_year(text_full) or extract_year(title)
            pdfs = collect_pdf_links_from_block(block)

            if not pdfs:
                continue

            for link, anchor_text in pdfs:
                if link in seen_links:
                    continue
                seen_links.add(link)

                filename = get_filename_from_url(link)

                # fallback final si el bloque no trae año
                final_year = (
                    year
                    or extract_year(anchor_text)
                    or extract_year(filename)
                )

                folder_name = str(final_year) if final_year else "Sin_clasificar"
                folder = os.path.join(BASE_FOLDER, folder_name)
                ensure_folder(folder)

                destination = os.path.join(folder, filename)

                if os.path.exists(destination):
                    print(f"Ya existe: {destination}")
                    continue

                try:
                    print(f"Descargando: {filename}")
                    print(f"  título: {title}")
                    print(f"  año detectado: {final_year}")
                    print(f"  carpeta: {folder_name}")
                    download_file(link, destination)
                except requests.RequestException as e:
                    print(f"Error descargando {link}: {e}")

    print("\nDescarga y organización completadas.")


if __name__ == "__main__":
    main()
