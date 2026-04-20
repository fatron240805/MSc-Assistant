"""
Pipeline hoàn chỉnh – carre.edu.vn/nhan-vat-lich-su/
  Bước 1 (crawl)    : Duyệt tất cả trang danh sách → lưu character_links.txt
  Bước 2 (download) : Tải HTML từng nhân vật       → lưu vào folder html_pages/
  Bước 3 (extract)  : Parse HTML từng nhân vật      → lưu characters.json

Chạy toàn bộ  : python pipeline.py
Chạy từng bước: python pipeline.py --step 1   (hoặc 2, 3)
"""

import argparse
import json
import os
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ─────────────────────────── CONFIG ──────────────────────────────────────────
BASE_URL      = "https://carre.edu.vn"
LIST_URL      = BASE_URL + "/nhan-vat-lich-su/"          # trang 1
LIST_URL_PAGE = BASE_URL + "/nhan-vat-lich-su/page/{n}/" # trang 2+

LINKS_FILE  = "character_links.txt"
HTML_DIR    = "html_pages"
OUTPUT_JSON = "characters.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}
DELAY   = 0.6   # giây giữa mỗi request
TIMEOUT = 15
RETRY   = 3
# ─────────────────────────────────────────────────────────────────────────────


# ══════════════════════════════════════════════════════════════════════════════
# BƯỚC 1 – Crawl link
# ══════════════════════════════════════════════════════════════════════════════

def get_last_page(soup):
    """Đọc số trang cuối từ ul.page-numbers"""
    last = 1
    for a in soup.select("ul.page-numbers a"):
        href = a.get("href", "")
        m = re.search(r"/page/(\d+)/?$", href)
        if m:
            last = max(last, int(m.group(1)))
    return last


def extract_links_from_page(soup):
    links = []
    for box in soup.select("div.box-blog-post"):
        a = box.select_one("p.post-title a[href]") or box.select_one("a.plain[href]")
        if a:
            links.append(a["href"].strip())
    return links


def fetch(url, retries=RETRY):
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            r.encoding = "utf-8"
            if r.status_code == 200:
                return r.text
            print(f"  HTTP {r.status_code} (lần {attempt})")
        except Exception as e:
            print(f"  Lỗi: {e} (lần {attempt})")
        time.sleep(1)
    return None


def step1_crawl():
    print("\n" + "═"*55)
    print("BƯỚC 1 – Crawl danh sách link nhân vật")
    print("═"*55)

    # Trang 1
    print("Đang lấy trang 1 …")
    html = fetch(LIST_URL)
    if not html:
        print("❌ Không lấy được trang 1, dừng lại.")
        return

    soup      = BeautifulSoup(html, "html.parser")
    last_page = get_last_page(soup)
    print(f"  → Tổng số trang: {last_page}")

    all_links = extract_links_from_page(soup)
    print(f"  → Trang 1: {len(all_links)} link")

    for n in range(2, last_page + 1):
        url  = LIST_URL_PAGE.format(n=n)
        print(f"Đang lấy trang {n}/{last_page} …")
        html = fetch(url)
        if not html:
            print(f"  ⚠ Bỏ qua trang {n}")
            continue
        links = extract_links_from_page(BeautifulSoup(html, "html.parser"))
        print(f"  → {len(links)} link")
        all_links.extend(links)
        time.sleep(DELAY)

    # Dedup giữ thứ tự
    seen, unique = set(), []
    for lnk in all_links:
        if lnk not in seen:
            seen.add(lnk)
            unique.append(lnk)

    with open(LINKS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(unique))

    print(f"\n✅ Tổng cộng {len(unique)} link → {LINKS_FILE}")


# ══════════════════════════════════════════════════════════════════════════════
# BƯỚC 2 – Tải HTML
# ══════════════════════════════════════════════════════════════════════════════

def url_to_filename(url):
    """URL → tên file an toàn, giữ slug để dễ nhận dạng"""
    slug = url.rstrip("/").split("/")[-1]          # phần cuối URL
    slug = re.sub(r"[^\w\-]", "_", slug)[:160]
    return slug + ".html"


def step2_download():
    print("\n" + "═"*55)
    print("BƯỚC 2 – Tải HTML từng nhân vật")
    print("═"*55)

    if not os.path.exists(LINKS_FILE):
        print(f"❌ Không tìm thấy {LINKS_FILE}. Hãy chạy bước 1 trước.")
        return

    with open(LINKS_FILE, encoding="utf-8") as f:
        urls = [l.strip() for l in f if l.strip()]

    Path(HTML_DIR).mkdir(exist_ok=True)
    existing = set(os.listdir(HTML_DIR))
    total    = len(urls)
    success  = 0
    failed   = []

    for i, url in enumerate(urls, 1):
        fname    = url_to_filename(url)
        filepath = os.path.join(HTML_DIR, fname)

        if fname in existing:
            print(f"[{i:>4}/{total}] ⏭  Đã có: {fname}")
            success += 1
            continue

        print(f"[{i:>4}/{total}] ⬇  {url}")
        html = fetch(url)
        if html:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(html)
            existing.add(fname)
            success += 1
            print(f"           ✅ {fname}")
        else:
            failed.append(url)
            print(f"           ❌ Thất bại")

        time.sleep(DELAY)

    print(f"\n✅ Thành công: {success}/{total}")
    if failed:
        fail_file = "failed_links.txt"
        with open(fail_file, "w", encoding="utf-8") as f:
            f.write("\n".join(failed))
        print(f"❌ Thất bại : {len(failed)} → {fail_file}")


# ══════════════════════════════════════════════════════════════════════════════
# BƯỚC 3 – Extract → JSON
# ══════════════════════════════════════════════════════════════════════════════

def parse_character(filepath):
    with open(filepath, encoding="utf-8", errors="replace") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")

    # ── URL gốc ──────────────────────────────────────────────────────────────
    url = ""
    og = soup.find("meta", property="og:url")
    if og:
        url = og.get("content", "").strip()
    if not url:
        canon = soup.find("link", rel="canonical")
        if canon:
            url = canon.get("href", "").strip()

    # ── Tiêu đề ───────────────────────────────────────────────────────────────
    title = ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
    if not title:
        og_title = soup.find("meta", property="og:title")
        if og_title:
            title = og_title.get("content", "").strip()

    # ── Ngày đăng ─────────────────────────────────────────────────────────────
    date = ""
    # WordPress thường có <time datetime="..."> hoặc class published/entry-date
    time_el = soup.find("time")
    if time_el:
        date = time_el.get("datetime", "") or time_el.get_text(strip=True)
    if not date:
        for cls in ["entry-date", "published", "post-date", "date"]:
            el = soup.find(class_=cls)
            if el:
                date = el.get_text(strip=True)
                break

    # ── Tác giả ───────────────────────────────────────────────────────────────
    author = ""
    for cls in ["author", "entry-author", "post-author", "byline"]:
        el = soup.find(class_=cls)
        if el:
            author = el.get_text(strip=True)
            break

    # ── Excerpt / mô tả ngắn ─────────────────────────────────────────────────
    excerpt = ""
    og_desc = soup.find("meta", property="og:description") or \
              soup.find("meta", attrs={"name": "description"})
    if og_desc:
        excerpt = og_desc.get("content", "").strip()

    # ── Thumbnail ─────────────────────────────────────────────────────────────
    thumbnail = ""
    og_img = soup.find("meta", property="og:image")
    if og_img:
        thumbnail = og_img.get("content", "").strip()

    # ── Nội dung chính ───────────────────────────────────────────────────────
    # WordPress: article.post, div.entry-content, div.post-content
    content_el = (
        soup.select_one("div.entry-content")
        or soup.select_one("div.post-content")
        or soup.select_one("article.post")
        or soup.select_one("article")
    )

    content_text = ""
    content_paragraphs = []
    images_in_content  = []

    if content_el:
        # Xóa script / style / nav / aside
        for tag in content_el.find_all(["script", "style", "nav", "aside",
                                         "figure > figcaption"]):
            tag.decompose()

        # Thu thập ảnh trong bài
        for img in content_el.find_all("img"):
            src = img.get("src") or img.get("data-src") or ""
            if src.strip():
                images_in_content.append({
                    "url":     src.strip(),
                    "caption": img.get("alt", "").strip()
                })

        # Thu thập text theo đoạn
        for el in content_el.find_all(["h1","h2","h3","h4","h5","p","li","blockquote","td"]):
            txt = el.get_text(separator=" ", strip=True)
            if txt:
                content_paragraphs.append(txt)

        # Fallback: lấy toàn bộ text nếu không có thẻ con
        if not content_paragraphs:
            raw = content_el.get_text(separator="\n", strip=True)
            content_paragraphs = [l for l in raw.splitlines() if l.strip()]

        content_text = "\n\n".join(content_paragraphs)

    # ── Categories / Tags ────────────────────────────────────────────────────
    categories, tags = [], []
    for a in soup.select("a[rel='category tag'], a[rel='tag']"):
        tags.append(a.get_text(strip=True))
    for a in soup.select("a[rel='category']"):
        categories.append(a.get_text(strip=True))
    # fallback WordPress body class
    body = soup.find("body")
    if body:
        for cls in body.get("class", []):
            if cls.startswith("category-") and not cls.replace("category-","").isdigit():
                categories.append(cls.replace("category-","").replace("-"," "))

    categories = list(dict.fromkeys(categories))
    tags       = list(dict.fromkeys(tags))

    return {
        "title":      title,
        "url":        url,
        "date":       date,
        "author":     author,
        "excerpt":    excerpt,
        "thumbnail":  thumbnail,
        "categories": categories,
        "tags":       tags,
        "content":    content_text,
        "images":     images_in_content,
        "_filename":  Path(filepath).name,
    }


def step3_extract():
    print("\n" + "═"*55)
    print("BƯỚC 3 – Extract HTML → JSON")
    print("═"*55)

    if not os.path.isdir(HTML_DIR):
        print(f"❌ Không tìm thấy folder {HTML_DIR}. Hãy chạy bước 2 trước.")
        return

    files   = sorted(Path(HTML_DIR).glob("*.html"))
    total   = len(files)
    print(f"📂 {total} file HTML trong '{HTML_DIR}/'")

    results, errors = [], []

    for i, fp in enumerate(files, 1):
        try:
            rec = parse_character(fp)
            results.append(rec)
            label = rec["title"][:55] if rec["title"] else fp.name
            print(f"[{i:>4}/{total}] ✅ {label}")
        except Exception as e:
            errors.append({"file": fp.name, "error": str(e)})
            print(f"[{i:>4}/{total}] ❌ {fp.name}  —  {e}")

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    size_kb = os.path.getsize(OUTPUT_JSON) // 1024
    print(f"\n✅ Đã extract : {len(results)}/{total}")
    print(f"❌ Lỗi        : {len(errors)}")
    print(f"📄 Output     : {OUTPUT_JSON}  ({size_kb} KB)")

    if errors:
        with open("extract_errors.json", "w", encoding="utf-8") as f:
            json.dump(errors, f, ensure_ascii=False, indent=2)
        print("⚠️  Chi tiết lỗi: extract_errors.json")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Pipeline crawl nhân vật lịch sử")
    parser.add_argument(
        "--step", type=int, choices=[1, 2, 3],
        help="Chỉ chạy bước cụ thể (1=crawl, 2=download, 3=extract). "
             "Mặc định chạy cả 3 bước."
    )
    args = parser.parse_args()

    if args.step == 1 or args.step is None:
        step1_crawl()
    if args.step == 2 or args.step is None:
        step2_download()
    if args.step == 3 or args.step is None:
        step3_extract()


if __name__ == "__main__":
    main()
