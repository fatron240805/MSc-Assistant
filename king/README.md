**TREE FORMAT**

Root (Array of Objects)
└── [Element Object]
    ├── matched_name: "Tên nhân vật xác định từ Wikipedia"
    ├── chu_han_extracted: "Chữ Hán của nhân vật (nếu có)"
    ├── ten_huy_that_extracted: "Tên húy hoặc tên thật của nhân vật"
    ├── ngay_nam_sinh_mat_extracted: "Thông tin năm sinh và năm mất"
    ├── que_quan_extracted: "Quê quán hoặc nơi sinh"
    ├── summary: "Đoạn tóm tắt ngắn về nhân vật"
    ├── content_hierarchy: (Cấu trúc phân cấp nội dung - Array)
    │   └── [Section Object]
    │       ├── title: "Tiêu đề mục (Ví dụ: Thân thế, Sự nghiệp)"
    │       ├── text: "Nội dung chi tiết của mục đó"
    │       └── subsections: (Mục con - Đệ quy cấu trúc Section Object)
    ├── citations: (Mảng chứa các chú thích/nguồn tham khảo)
    └── url: "Đường dẫn gốc đến bài viết Wikipedia"

    