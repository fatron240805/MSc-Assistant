"""
Pipeline – Wikipedia vi: Thể loại:Nhân vật lịch sử Việt Nam
─────────────────────────────────────────────────────────────
Bước 1 (crawl)    : Đệ quy qua tất cả thể loại con
                    → lấy toàn bộ link nhân vật (title + href)
                    → lưu character_links.jsonl
Bước 2 (download) : Tải HTML từng trang nhân vật
                    → lưu vào html_pages/
Bước 3 (extract)  : Parse HTML Wikipedia → plain text có cấu trúc
                    → lưu characters.json

Cài đặt : pip install requests beautifulsoup4
Chạy cả pipeline : python pipeline.py
Chạy từng bước   : python pipeline.py --step 1  (hoặc 2, 3)
"""

import argparse, json, os, re, time
from pathlib import Path
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup

# ── CONFIG ────────────────────────────────────────────────────────────────────
WIKI_BASE    = "https://vi.wikipedia.org"
START_CAT    = "/wiki/Thể_loại:Nhân_vật_lịch_sử_Việt_Nam"

LINKS_FILE   = "character_links.jsonl"   # 1 JSON object mỗi dòng
HTML_DIR     = "html_pages"
OUTPUT_JSON  = "characters.json"

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; wiki-scraper/1.0)"}
DELAY   = 0.5
TIMEOUT = 15
RETRY   = 3
# ─────────────────────────────────────────────────────────────────────────────


# ══════════════════════════════════════════════════════════════════════════════
# UTILS
# ══════════════════════════════════════════════════════════════════════════════

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


def abs_wiki(href):
    if href.startswith("http"):
        return href
    return WIKI_BASE + href


def is_category(href):
    return "/wiki/Thể_loại:" in href or "/wiki/Th%E1%BB%83_lo%E1%BA%A1i:" in href


def is_article(href):
    if not href.startswith("/wiki/"):
        return False
    skip = [
        "Đặc_biệt:", "Thảo_luận:", "Thành_viên:", "Wikipedia:",
        "Trợ_giúp:", "Tập_tin:", "Cổng_thông_tin:", "Thể_loại:",
        "%C4%90%E1%BA%B7c_bi%E1%BB%87t:",
        "Th%E1%BA%A3o_lu%E1%BA%ADn:",
        "Th%E1%BB%83_lo%E1%BA%A1i:",
        "T%E1%BA%ADp_tin:",
    ]
    return not any(s in href for s in skip)


# ══════════════════════════════════════════════════════════════════════════════
# BƯỚC 1 – Crawl link từ thể loại (đệ quy)
# ══════════════════════════════════════════════════════════════════════════════

def parse_category_page(html):
    soup = BeautifulSoup(html, "html.parser")
    articles, sub_cats = [], []

    # Nhân vật (mw-pages)
    mw_pages = soup.find(id="mw-pages")
    if mw_pages:
        for a in mw_pages.find_all("a", href=True):
            href = a["href"]
            if is_article(href):
                articles.append({
                    "title": a.get("title") or a.get_text(strip=True),
                    "href":  href,
                    "url":   abs_wiki(href),
                })

    # Thể loại con (mw-subcategories)
    mw_sub = soup.find(id="mw-subcategories")
    if mw_sub:
        for a in mw_sub.find_all("a", href=True):
            if is_category(a["href"]):
                sub_cats.append(abs_wiki(a["href"]))

    # Phân trang thể loại
    next_url = None
    for a in soup.find_all("a", href=True):
        txt = a.get_text(strip=True).lower()
        if txt in ("trang tiếp", "next page", "tiếp theo", "›", "»"):
            next_url = abs_wiki(a["href"])
            break
    if not next_url:
        for a in soup.find_all("a", href=True):
            if "pagefrom" in a["href"] or "cmcontinue" in a["href"]:
                txt = a.get_text(strip=True).lower()
                if "trước" not in txt and "prev" not in txt:
                    next_url = abs_wiki(a["href"])
                    break

    return articles, sub_cats, next_url


def crawl_category(url, visited_cats, all_articles, article_hrefs):
    if url in visited_cats:
        return
    visited_cats.add(url)

    page_num = 1
    cur_url  = url

    while cur_url:
        print(f"  📂 [{page_num}] {cur_url}")
        html = fetch(cur_url)
        if not html:
            break

        articles, sub_cats, next_url = parse_category_page(html)
        new = [a for a in articles if a["href"] not in article_hrefs]
        for a in new:
            article_hrefs.add(a["href"])
            all_articles.append(a)
        print(f"     → +{len(new)} nhân vật mới | {len(sub_cats)} thể loại con")

        for sub in sub_cats:
            crawl_category(sub, visited_cats, all_articles, article_hrefs)

        cur_url  = next_url
        page_num += 1
        time.sleep(DELAY)


def step1_crawl():
    print("\n" + "═"*60)
    print("BƯỚC 1 – Crawl link nhân vật từ Wikipedia")
    print("═"*60)

    visited_cats  = set()
    all_articles  = []
    article_hrefs = set()

    crawl_category(abs_wiki(START_CAT), visited_cats, all_articles, article_hrefs)

    with open(LINKS_FILE, "w", encoding="utf-8") as f:
        for art in all_articles:
            f.write(json.dumps(art, ensure_ascii=False) + "\n")

    print(f"\n✅ {len(all_articles)} nhân vật từ {len(visited_cats)} thể loại → {LINKS_FILE}")


# ══════════════════════════════════════════════════════════════════════════════
# BƯỚC 2 – Tải HTML
# ══════════════════════════════════════════════════════════════════════════════

def slug_from_href(href):
    name = href.split("/wiki/")[-1]
    name = unquote(name)
    name = re.sub(r"[^\w\u00C0-\u024F\u1E00-\u1EFF\-]", "_", name)
    return name[:180] + ".html"


def step2_download():
    print("\n" + "═"*60)
    print("BƯỚC 2 – Tải HTML từng nhân vật")
    print("═"*60)

    if not os.path.exists(LINKS_FILE):
        print(f"❌ Không tìm thấy {LINKS_FILE}. Hãy chạy bước 1 trước.")
        return

    with open(LINKS_FILE, encoding="utf-8") as f:
        records = [json.loads(l) for l in f if l.strip()]

    Path(HTML_DIR).mkdir(exist_ok=True)
    existing = set(os.listdir(HTML_DIR))
    total, success, failed = len(records), 0, []

    for i, rec in enumerate(records, 1):
        fname    = slug_from_href(rec["href"])
        filepath = os.path.join(HTML_DIR, fname)

        if fname in existing:
            print(f"[{i:>4}/{total}] ⏭  {rec['title'][:60]}")
            success += 1
            continue

        print(f"[{i:>4}/{total}] ⬇  {rec['title'][:60]}")
        html = fetch(rec["url"])
        if html:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(html)
            existing.add(fname)
            success += 1
        else:
            failed.append(rec)
            print(f"           ❌ Thất bại")
        time.sleep(DELAY)

    print(f"\n✅ Thành công: {success}/{total}")
    if failed:
        with open("failed_links.jsonl", "w", encoding="utf-8") as f:
            for r in failed:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"❌ Thất bại : {len(failed)} → failed_links.jsonl")


# ══════════════════════════════════════════════════════════════════════════════
# BƯỚC 3 – Extract Wikipedia HTML → JSON
# ══════════════════════════════════════════════════════════════════════════════

def parse_wiki_article(filepath):
    with open(filepath, encoding="utf-8", errors="replace") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")

    # Tiêu đề
    title = ""
    h1 = soup.find(id="firstHeading") or soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)

    # URL
    url = ""
    canon = soup.find("link", rel="canonical")
    if canon:
        url = canon.get("href", "")
    if not url:
        og = soup.find("meta", property="og:url")
        if og:
            url = og.get("content", "")

    # Thumbnail từ infobox
    thumbnail = ""
    infobox_el = soup.find("table", class_=re.compile(r"infobox|wikitable"))
    if infobox_el:
        img = infobox_el.find("img")
        if img:
            src = img.get("src", "")
            thumbnail = ("https:" + src) if src.startswith("//") else src

    # Categories
    categories = []
    cat_div = soup.find(id="mw-normal-catlinks")
    if cat_div:
        for a in cat_div.find_all("a", href=True):
            if is_category(a["href"]):
                categories.append(a.get_text(strip=True))

    # Infobox key-value
    infobox_data = {}
    if infobox_el:
        for row in infobox_el.find_all("tr"):
            cells = row.find_all(["th", "td"])
            if len(cells) >= 2:
                key = cells[0].get_text(separator=" ", strip=True)
                val = cells[1].get_text(separator=" ", strip=True)
                if key and val:
                    infobox_data[key] = val
            elif len(cells) == 1:
                txt = cells[0].get_text(strip=True)
                if txt:
                    infobox_data.setdefault("_caption", txt)

    # Nội dung chính theo sections
    content_el = soup.find(id="mw-content-text")
    sections   = []
    images_all = []

    if content_el:
        # Xóa noise: script, style, ref, navbox
        for tag in content_el.find_all(["script", "style", "sup"]):
            tag.decompose()
        for tag in content_el.find_all("div", class_=re.compile(
                r"navbox|reflist|mw-references|noprint|sistersitebox|"
                r"portal|hatnote|toc")):
            tag.decompose()

        current_heading = "Mở đầu"
        current_paras   = []
        current_imgs    = []

        def flush():
            if current_paras or current_imgs:
                sections.append({
                    "heading":    current_heading,
                    "paragraphs": list(current_paras),
                    "images":     list(current_imgs),
                })

        for el in content_el.find_all(
            ["h2","h3","h4","p","ul","ol","blockquote","div","table"],
            recursive=False   # chỉ top-level để tránh trùng lặp
        ):
            cls = " ".join(el.get("class", []))

            if el.name in ("h2","h3","h4"):
                flush()
                current_heading = (el.find("span", class_="mw-headline") or el).get_text(strip=True)
                current_paras   = []
                current_imgs    = []

            elif el.name == "div" and "thumb" in cls:
                img = el.find("img")
                cap = el.find(class_=re.compile(r"thumbcaption"))
                if img:
                    src = img.get("src","")
                    src = ("https:"+src) if src.startswith("//") else src
                    entry = {"url": src, "caption": (cap.get_text(strip=True) if cap else img.get("alt",""))}
                    current_imgs.append(entry)
                    images_all.append(entry)

            elif el.name == "table" and re.search(r"infobox|wikitable", cls):
                # table đã xử lý ở infobox_data, bỏ qua
                pass

            elif el.name in ("p","ul","ol","blockquote"):
                txt = el.get_text(separator=" ", strip=True)
                if txt and len(txt) > 15:
                    current_paras.append(txt)

            elif el.name == "div":
                # div.mw-parser-output chứa tất cả → đệ quy tầng con
                for child in el.find_all(
                    ["h2","h3","h4","p","ul","ol","blockquote"],
                    recursive=True
                ):
                    c_cls = " ".join(child.get("class",[]))
                    if child.name in ("h2","h3","h4"):
                        flush()
                        current_heading = (child.find("span", class_="mw-headline") or child).get_text(strip=True)
                        current_paras   = []
                        current_imgs    = []
                    else:
                        txt = child.get_text(separator=" ", strip=True)
                        if txt and len(txt) > 15:
                            current_paras.append(txt)

        flush()

    # Plain text nối sections
    parts = []
    for sec in sections:
        if sec["heading"] != "Mở đầu":
            parts.append(f"\n== {sec['heading']} ==")
        parts.extend(sec["paragraphs"])
    full_text = "\n\n".join(parts).strip()

    return {
        "title":      title,
        "url":        url,
        "thumbnail":  thumbnail,
        "categories": categories,
        "infobox":    infobox_data,
        "sections":   sections,
        "content":    full_text,
        "images":     images_all,
        "_filename":  Path(filepath).name,
    }


def step3_extract():
    print("\n" + "═"*60)
    print("BƯỚC 3 – Extract HTML → JSON")
    print("═"*60)

    if not os.path.isdir(HTML_DIR):
        print(f"❌ Không tìm thấy folder {HTML_DIR}. Hãy chạy bước 2 trước.")
        return

    files   = sorted(Path(HTML_DIR).glob("*.html"))
    total   = len(files)
    print(f"📂 {total} file HTML trong '{HTML_DIR}/'")

    results, errors = [], []

    for i, fp in enumerate(files, 1):
        try:
            rec = parse_wiki_article(fp)
            results.append(rec)
            print(f"[{i:>4}/{total}] ✅ {rec['title'][:50]:<50}  "
                  f"sections={len(rec['sections'])}  "
                  f"infobox={len(rec['infobox'])}  "
                  f"ảnh={len(rec['images'])}")
        except Exception as e:
            errors.append({"file": fp.name, "error": str(e)})
            print(f"[{i:>4}/{total}] ❌ {fp.name} — {e}")

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
    parser = argparse.ArgumentParser(
        description="Pipeline Wikipedia – Nhân vật lịch sử Việt Nam"
    )
    parser.add_argument(
        "--step", type=int, choices=[1, 2, 3],
        help="Chỉ chạy bước cụ thể (1=crawl, 2=download, 3=extract). "
             "Mặc định: cả 3."
    )
    args = parser.parse_args()
    run_all = args.step is None
    if run_all or args.step == 1: step1_crawl()
    if run_all or args.step == 2: step2_download()
    if run_all or args.step == 3: step3_extract()


if __name__ == "__main__":
    main()
