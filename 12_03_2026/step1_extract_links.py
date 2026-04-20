"""
BƯỚC 1: Đọc file HTML → Trích xuất tất cả links Wikipedia → Lưu vào file output
"""

import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse, unquote


class WikiLinkExtractor(HTMLParser):
    """Parser trích xuất các link Wikipedia từ HTML."""

    def __init__(self, base_url="https://vi.wikipedia.org"):
        super().__init__()
        self.links = []
        self.seen = set()
        self.base_url = base_url

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return

        attrs_dict = dict(attrs)
        href = attrs_dict.get("href", "")

        if not href:
            return

        # Bỏ qua các link đặc biệt, neo, javascript
        if href.startswith(("#", "javascript:", "mailto:")):
            return

        # Chuyển relative URL thành absolute
        full_url = urljoin(self.base_url, href)

        parsed = urlparse(full_url)

        # Chỉ lấy links đến các trang wiki (có /wiki/ trong path)
        if "/wiki/" not in parsed.path:
            return

        # Bỏ qua các trang đặc biệt không phải bài viết
        skip_prefixes = [
            "/wiki/Đặc_biệt:",
            "/wiki/%C4%90%E1%BA%B7c_bi%E1%BB%87t:",  # URL-encoded "Đặc biệt"
            "/wiki/Wikipedia:",
            "/wiki/Thảo_luận",
            "/wiki/Th%E1%BA%A3o_lu%E1%BA%ADn",
            "/wiki/Trợ_giúp:",
            "/wiki/Tr%E1%BB%A3_gi%C3%BAp:",
        ]
        if any(parsed.path.startswith(p) for p in skip_prefixes):
            return

        # Bỏ query string và fragment
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

        if clean_url not in self.seen:
            self.seen.add(clean_url)
            # Giải mã URL để dễ đọc
            readable = unquote(clean_url)
            self.links.append({"url": clean_url, "readable": readable})


def extract_links_from_html_file(input_path: str, output_path: str):
    print(f"📖 Đọc file: {input_path}")

    with open(input_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    print(f"   Kích thước: {len(html_content):,} ký tự")

    # Phát hiện base URL từ nội dung HTML (thẻ <link rel="canonical">)
    base_url = "https://vi.wikipedia.org"
    canonical_match = re.search(r'<link rel="canonical" href="([^"]+)"', html_content)
    if canonical_match:
        parsed = urlparse(canonical_match.group(1))
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        print(f"   Base URL phát hiện: {base_url}")

    # Trích xuất links
    extractor = WikiLinkExtractor(base_url=base_url)
    extractor.feed(html_content)

    links = extractor.links
    print(f"✅ Tìm thấy {len(links)} link Wikipedia duy nhất")

    # Ghi ra file output
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# Wikipedia links extracted from: {input_path}\n")
        f.write(f"# Total: {len(links)} links\n")
        f.write("#" * 60 + "\n")
        for item in links:
            # Mỗi dòng: URL thực tế | tên dễ đọc
            f.write(f"{item['url']}\n")

    print(f"💾 Đã lưu links vào: {output_path}")

    # In preview
    print("\n--- Preview (10 links đầu) ---")
    for item in links[:10]:
        print(f"  {item['readable']}")
    if len(links) > 10:
        print(f"  ... và {len(links) - 10} link nữa")

    return links


if __name__ == "__main__":
    # ===================== CẤU HÌNH ĐƯỜNG DẪN =====================
    INPUT_FILE  = "address.txt"        # File HTML đầu vào
    OUTPUT_FILE = "wiki_links.txt"   # File lưu danh sách links
    # ===============================================================

    extract_links_from_html_file(INPUT_FILE, OUTPUT_FILE)
