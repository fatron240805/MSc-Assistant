"""
BƯỚC 3: Đọc toàn bộ folder HTML Wikipedia → Extract nội dung → Lưu vào 1 file JSON

Cấu trúc JSON output mỗi bài:
{
  "title": "...",
  "url": "...",
  "source_file": "...",
  "categories": [...],
  "intro": "...",           # đoạn văn trước section đầu tiên
  "sections": [
    {
      "level": 2,
      "heading": "...",
      "content": [          # danh sách các block nội dung theo thứ tự
        {"type": "paragraph", "text": "..."},
        {"type": "list",      "items": [...]},
        {"type": "table",     "caption": "...", "headers": [...], "rows": [[...]]},
        {"type": "see_also",  "text": "..."},
      ],
      "subsections": [...]  # đệ quy section con
    }
  ],
  "see_also": [...],        # danh sách link "Xem thêm"
  "references_count": N
}
"""

import os
import re
import json
from bs4 import BeautifulSoup, NavigableString, Tag
from urllib.parse import unquote

# ===================== CẤU HÌNH ĐƯỜNG DẪN =====================
INPUT_DIR   = "./downloaded_html"    # Thư mục chứa file HTML tải về
OUTPUT_FILE = "wiki_extracted.json"  # File JSON đầu ra
# ===============================================================


# ─── Helpers ──────────────────────────────────────────────────

def clean_text(text: str) -> str:
    """Làm sạch text: bỏ khoảng trắng thừa, newline thừa."""
    text = re.sub(r'\[sửa\s*\|?\s*sửa mã nguồn\]', '', text)
    text = re.sub(r'\[\d+\]', '', text)          # bỏ [1], [2], ...
    text = re.sub(r'\[note \d+\]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def get_heading_level(div) -> int:
    """Lấy level heading từ class mw-heading2/3/4."""
    for cls in div.get('class', []):
        m = re.match(r'mw-heading(\d)', cls)
        if m:
            return int(m.group(1))
    return 0


def extract_list_items(ul_or_ol) -> list:
    """Trích xuất các item từ <ul> hoặc <ol>."""
    items = []
    for li in ul_or_ol.find_all('li', recursive=False):
        text = clean_text(li.get_text())
        if text:
            items.append(text)
    return items


def extract_table(table_tag) -> dict:
    """Trích xuất bảng wikitable thành dict có cấu trúc."""
    result = {"type": "table", "caption": "", "headers": [], "rows": []}

    # Caption
    caption = table_tag.find('caption')
    if caption:
        result["caption"] = clean_text(caption.get_text())

    rows = table_tag.find_all('tr')
    header_rows = []
    data_rows = []

    for row in rows:
        ths = row.find_all('th')
        tds = row.find_all('td')
        if ths and not tds:
            header_rows.append([clean_text(th.get_text()) for th in ths])
        else:
            cells = row.find_all(['th', 'td'])
            if cells:
                data_rows.append([clean_text(c.get_text()) for c in cells])

    if header_rows:
        # Gộp tất cả header rows thành 1 list phẳng (thường multi-row header)
        result["headers"] = header_rows
    result["rows"] = data_rows
    return result


def extract_content_block(element) -> dict | None:
    """Chuyển 1 element HTML thành content block dict."""
    tag = element.name
    cls = element.get('class', [])

    # Bỏ qua hatnote (chú thích "Xem thêm:" / "Bài chi tiết:")
    if 'hatnote' in cls:
        text = clean_text(element.get_text())
        if text:
            return {"type": "hatnote", "text": text}
        return None

    # Đoạn văn
    if tag == 'p':
        text = clean_text(element.get_text())
        if text:
            return {"type": "paragraph", "text": text}
        return None

    # Danh sách
    if tag in ('ul', 'ol'):
        # bỏ qua references list
        if 'references' in cls:
            return None
        items = extract_list_items(element)
        if items:
            return {"type": "list", "ordered": tag == 'ol', "items": items}
        return None

    # Bảng
    if tag == 'table':
        return extract_table(element)

    return None


# ─── Parser chính ─────────────────────────────────────────────

def parse_wiki_html(html_content: str, source_file: str = "") -> dict:
    soup = BeautifulSoup(html_content, "lxml")

    # --- Meta ---
    title_tag = soup.find("title")
    title = ""
    if title_tag:
        title = title_tag.text.replace(" – Wikipedia tiếng Việt", "").strip()

    # URL từ canonical
    url = ""
    canonical = soup.find("link", {"rel": "canonical"})
    if canonical:
        url = canonical.get("href", "")

    # Categories từ #mw-normal-catlinks
    categories = []
    catlinks = soup.find("div", {"id": "mw-normal-catlinks"})
    if catlinks:
        for a in catlinks.find_all("a")[1:]:  # bỏ link "Thể loại" đầu
            categories.append(a.text.strip())

    # --- Lấy vùng nội dung chính ---
    parser_output = soup.find("div", {"class": "mw-parser-output"})
    if not parser_output:
        return {"title": title, "url": url, "source_file": source_file,
                "categories": categories, "intro": "", "sections": [],
                "see_also": [], "references_count": 0}

    # Lấy tất cả element con trực tiếp (bỏ style, link, meta, script)
    SKIP_TAGS = {'style', 'link', 'meta', 'script'}
    elements = [
        c for c in parser_output.children
        if isinstance(c, Tag) and c.name not in SKIP_TAGS
    ]

    # Bỏ sidebar (table.sidebar) và bảng điều hướng
    elements = [
        e for e in elements
        if not ('sidebar' in e.get('class', []) or
                'navbox' in e.get('class', []) or
                'navigation-box' in e.get('class', []))
    ]

    # ── Xây dựng cây section ──────────────────────────────────
    # Phân vùng: intro (trước heading đầu tiên), rồi từng section
    intro_blocks = []
    sections_flat = []   # list of {level, heading, blocks[]}

    current_section = None

    for elem in elements:
        cls = elem.get('class', [])
        is_heading = any(re.match(r'mw-heading\d', c) for c in cls)

        if is_heading:
            level = get_heading_level(elem)
            heading_text = clean_text(elem.get_text())
            current_section = {
                "level": level,
                "heading": heading_text,
                "blocks": []
            }
            sections_flat.append(current_section)
        else:
            block = extract_content_block(elem)
            if block is None:
                continue
            if current_section is None:
                intro_blocks.append(block)
            else:
                current_section["blocks"].append(block)

    # ── Tách "Xem thêm" và "Chú thích" ra riêng ──────────────
    see_also_items = []
    references_count = 0
    clean_sections_flat = []

    for sec in sections_flat:
        h = sec["heading"]
        if re.search(r'Xem thêm', h, re.IGNORECASE):
            for block in sec["blocks"]:
                if block["type"] == "list":
                    see_also_items.extend(block["items"])
            continue
        if re.search(r'Chú thích|Tham khảo|Ghi chú', h, re.IGNORECASE):
            # Đếm số references
            for block in sec["blocks"]:
                if block["type"] == "list":
                    references_count += len(block["items"])
            continue
        clean_sections_flat.append(sec)

    # ── Dựng cây section phân cấp ─────────────────────────────
    def build_tree(flat_sections):
        """Chuyển list phẳng thành cây phân cấp dựa vào level."""
        root = []
        stack = []  # stack of (level, node)

        for sec in flat_sections:
            node = {
                "level": sec["level"],
                "heading": sec["heading"],
                "content": sec["blocks"],
                "subsections": []
            }
            # Pop stack cho đến khi tìm được parent phù hợp
            while stack and stack[-1][0] >= sec["level"]:
                stack.pop()

            if stack:
                stack[-1][1]["subsections"].append(node)
            else:
                root.append(node)

            stack.append((sec["level"], node))

        return root

    sections_tree = build_tree(clean_sections_flat)

    # ── Intro: lấy text từ paragraph blocks ───────────────────
    intro_text = " ".join(
        b["text"] for b in intro_blocks if b.get("type") == "paragraph"
    ).strip()

    return {
        "title": title,
        "url": url,
        "source_file": source_file,
        "categories": categories,
        "intro": intro_text,
        "sections": sections_tree,
        "see_also": see_also_items,
        "references_count": references_count,
    }


# ─── Xử lý toàn bộ folder ─────────────────────────────────────

def process_folder(input_dir: str, output_file: str):
    # Lấy danh sách file HTML (bỏ qua file _ prefix là file hệ thống)
    html_files = sorted([
        f for f in os.listdir(input_dir)
        if f.endswith('.html') and not f.startswith('_')
    ])

    if not html_files:
        print(f"❌ Không tìm thấy file HTML nào trong: {input_dir}")
        return

    print(f"📂 Tìm thấy {len(html_files)} file HTML trong '{input_dir}/'")
    print(f"🔄 Bắt đầu extract...\n")

    results = []
    errors = []

    for i, filename in enumerate(html_files, 1):
        filepath = os.path.join(input_dir, filename)
        print(f"[{i:3d}/{len(html_files)}] {filename[:70]}", end=" ... ", flush=True)

        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                html_content = f.read()

            article = parse_wiki_html(html_content, source_file=filename)

            # Tính số section và số block để báo cáo
            def count_sections(secs):
                total = len(secs)
                for s in secs:
                    total += count_sections(s.get("subsections", []))
                return total

            n_sections = count_sections(article["sections"])
            print(f"✅  '{article['title']}' | {n_sections} sections")
            results.append(article)

        except Exception as e:
            print(f"❌  LỖI: {e}")
            errors.append({"file": filename, "error": str(e)})

    # Ghi JSON output
    output = {
        "meta": {
            "total_articles": len(results),
            "total_errors": len(errors),
            "source_dir": input_dir,
        },
        "articles": results,
        "errors": errors,
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # Thống kê
    print(f"\n{'='*55}")
    print(f"📊 KẾT QUẢ:")
    print(f"   ✅ Thành công : {len(results)} bài")
    print(f"   ❌ Lỗi       : {len(errors)} file")
    print(f"   💾 Output    : {output_file}")
    size_kb = os.path.getsize(output_file) / 1024
    print(f"   📦 Kích thước: {size_kb:.1f} KB ({size_kb/1024:.2f} MB)")


if __name__ == "__main__":
    process_folder(INPUT_DIR, OUTPUT_FILE)
