"""
BƯỚC 2: Đọc file links → Tải HTML từng trang Wikipedia về → Lưu local
"""

import os
import time
import json
from urllib.parse import urlparse, unquote
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError


def url_to_filename(url: str) -> str:
    """Chuyển URL thành tên file hợp lệ."""
    parsed = urlparse(url)
    # Lấy phần path sau /wiki/
    path = parsed.path.replace("/wiki/", "", 1)
    # Giải mã URL encoding
    path = unquote(path)
    # Thay ký tự không hợp lệ trong tên file
    for char in r'\/:*?"<>|':
        path = path.replace(char, "_")
    # Giới hạn độ dài tên file
    if len(path) > 200:
        path = path[:200]
    return path + ".html"


def load_links(links_file: str) -> list:
    """Đọc danh sách links từ file."""
    links = []
    with open(links_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Bỏ qua dòng comment và dòng trống
            if not line or line.startswith("#"):
                continue
            links.append(line)
    return links


def download_page(url: str, delay: float = 1.5) -> tuple[bool, str, str]:
    """
    Tải một trang HTML.
    Returns: (success, html_content, error_message)
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; WikiScraper/1.0; "
            "Educational purpose; Python)"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "vi,en;q=0.5",
        "Accept-Encoding": "identity",
    }

    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=30) as response:
            # Lấy encoding từ header hoặc dùng utf-8
            content_type = response.headers.get("Content-Type", "")
            charset = "utf-8"
            if "charset=" in content_type:
                charset = content_type.split("charset=")[-1].strip()

            raw = response.read()
            html = raw.decode(charset, errors="replace")
            return True, html, ""

    except HTTPError as e:
        return False, "", f"HTTP Error {e.code}: {e.reason}"
    except URLError as e:
        return False, "", f"URL Error: {e.reason}"
    except Exception as e:
        return False, "", f"Error: {str(e)}"


def download_all(
    links_file: str,
    output_dir: str,
    delay: float = 1.5,
    limit: int = None,
    resume: bool = False,
):
    # Tạo thư mục output
    os.makedirs(output_dir, exist_ok=True)

    # File theo dõi trạng thái tải
    status_file = os.path.join(output_dir, "_download_status.json")
    status = {}
    if resume and os.path.exists(status_file):
        with open(status_file, "r", encoding="utf-8") as f:
            status = json.load(f)
        print(f"📂 Resume mode: đã có {len(status)} trang trong status")

    # Đọc danh sách links
    links = load_links(links_file)
    print(f"📋 Tổng số links: {len(links)}")

    if limit:
        links = links[:limit]
        print(f"⚠️  Giới hạn: chỉ tải {limit} trang")

    # Thống kê
    success_count = 0
    skip_count = 0
    fail_count = 0
    failed_urls = []

    print(f"\n🚀 Bắt đầu tải về thư mục: {output_dir}/")
    print(f"⏱️  Delay giữa requests: {delay}s\n")

    for i, url in enumerate(links, 1):
        filename = url_to_filename(url)
        filepath = os.path.join(output_dir, filename)
        readable_name = unquote(urlparse(url).path.replace("/wiki/", "", 1))

        print(f"[{i}/{len(links)}] {readable_name[:60]}")

        # Skip nếu resume và đã tải thành công
        if resume and status.get(url) == "ok" and os.path.exists(filepath):
            print(f"         ⏭️  Bỏ qua (đã có)")
            skip_count += 1
            continue

        # Tải trang
        ok, html, error = download_page(url, delay)

        if ok:
            # Lưu file HTML
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(html)
            status[url] = "ok"
            success_count += 1
            file_size = len(html.encode("utf-8"))
            print(f"         ✅ Lưu: {filename} ({file_size/1024:.1f} KB)")
        else:
            status[url] = f"error: {error}"
            fail_count += 1
            failed_urls.append(url)
            print(f"         ❌ Lỗi: {error}")

        # Lưu status sau mỗi trang
        with open(status_file, "w", encoding="utf-8") as f:
            json.dump(status, f, ensure_ascii=False, indent=2)

        # Delay trước request tiếp theo
        if i < len(links):
            time.sleep(delay)

    # Tổng kết
    print("\n" + "=" * 50)
    print("📊 KẾT QUẢ:")
    print(f"   ✅ Thành công : {success_count}")
    print(f"   ⏭️  Bỏ qua    : {skip_count}")
    print(f"   ❌ Thất bại  : {fail_count}")
    print(f"   📁 Thư mục   : {output_dir}/")
    print(f"   📄 Status    : {status_file}")

    if failed_urls:
        fail_log = os.path.join(output_dir, "_failed_urls.txt")
        with open(fail_log, "w", encoding="utf-8") as f:
            for u in failed_urls:
                f.write(u + "\n")
        print(f"   ⚠️  URL lỗi  : {fail_log}")


if __name__ == "__main__":
    # ===================== CẤU HÌNH ĐƯỜNG DẪN =====================
    LINKS_FILE  = "wiki_links.txt"      # File links output từ step1
    OUTPUT_DIR  = "./downloaded_html"   # Thư mục lưu HTML tải về

    DELAY       = 1.5      # Giây chờ giữa mỗi request (nên >= 1.0)
    LIMIT       = None     # Số trang tối đa cần tải, None = tải tất cả
    RESUME      = False    # True = bỏ qua trang đã tải thành công
    # ===============================================================

    download_all(
        links_file=LINKS_FILE,
        output_dir=OUTPUT_DIR,
        delay=DELAY,
        limit=LIMIT,
        resume=RESUME,
    )
