import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, unquote

BASE_FOLDER = "Observatorios"
BASE_URL = "https://iremai.wordpress.com/observatorio-4"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; IREMAI-Observatorio-Downloader/1.0)"
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

    m = re.search(r"\(?(\d{2})/(\d{2})/(\d{2})\)?", text)
    if m:
        yy = int(m.group(3))
        return 2000 + yy

    m = re.search(r"\b(20\d{2})\b", text)
    if m:
        return int(m.group(1))

    m = re.search(r"[Ee]dici[oó]n\s+final.*?\b(20\d{2})\b", text)
    if m:
        return int(m.group(1))

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


def find_post_title(a_tag):
    candidates = [
        a_tag.find_parent("article"),
        a_tag.find_parent(class_=re.compile(r"(post|type-post|hentry|entry)", re.I)),
        a_tag.find_parent("li"),
        a_tag.find_parent("div", class_=re.compile(r"(post|entry|archive)", re.I)),
    ]

    for container in candidates:
        if not container:
            continue

        for tag in ["h1", "h2", "h3", "h4"]:
            title_tag = container.find(tag)
            if title_tag:
                text = title_tag.get_text(" ", strip=True)
                if text:
                    return text

        title_tag = container.find(class_=re.compile(r"entry-title|post-title|archive-title", re.I))
        if title_tag:
            text = title_tag.get_text(" ", strip=True)
            if text:
                return text

    return None


def download_file(url, destination):
    with session.get(url, stream=True, timeout=90) as r:
        r.raise_for_status()
        with open(destination, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)


def ensure_folder(path):
    os.makedirs(path, exist_ok=True)


def main():
    ensure_folder(BASE_FOLDER)
    max_page = get_max_page()
    print(f"Se detectaron {max_page} páginas.")

    seen_links = set()

    for page in range(1, max_page + 1):
        url = BASE_URL if page == 1 else f"{BASE_URL}/page/{page}/"
        print(f"\nProcesando: {url}")

        try:
            r = session.get(url, timeout=30)
            r.raise_for_status()
        except requests.RequestException as e:
            print(f"No se pudo acceder a {url}: {e}")
            continue

        soup = BeautifulSoup(r.text, "html.parser")

        for a in soup.find_all("a", href=True):
            link = a["href"].strip()

            if ".pdf" not in link.lower():
                continue

            if link in seen_links:
                continue
            seen_links.add(link)

            anchor_text = a.get_text(" ", strip=True)
            post_title = find_post_title(a)
            filename = get_filename_from_url(link)

            year = (
                extract_year(post_title)
                or extract_year(anchor_text)
                or extract_year(filename)
            )

            folder_name = str(year) if year else "Sin_clasificar"
            folder = os.path.join(BASE_FOLDER, folder_name)
            ensure_folder(folder)

            destination = os.path.join(folder, filename)

            if os.path.exists(destination):
                print(f"Ya existe: {destination}")
                continue

            try:
                print(f"Descargando: {filename}")
                print(f"  título post: {post_title}")
                print(f"  texto enlace: {anchor_text}")
                print(f"  carpeta: {folder_name}")
                download_file(link, destination)
            except requests.RequestException as e:
                print(f"Error descargando {link}: {e}")

    print("\nDescarga y organización completadas.")


if __name__ == "__main__":
    main()
