# Ancient PDF Extractor | 古籍研究著作PDF内容整理

[English](#english) | [中文](#中文)

---

## 中文

### 📚 项目介绍

**古籍研究著作PDF内容整理**是一个专业的数字人文技能，针对古籍研究领域的PDF文档设计，特别是处理"现代印刷排版 + 嵌入古代文书影印件"的混合版面（如《敦煌碑铭讚辑释》《英藏敦煌文献》《法藏敦煌书苑》等）。

### ✨ 核心功能

- **文字层诊断**：智能检测PDF文字层质量，自动选择最优OCR方案
- **视觉OCR识别**：利用视觉模型进行高准确率的OCR识别，准确处理生僻字
- **文书图片提取**：像素级精确裁剪文书影印件，自动去除页眉、分割文档
- **结构化输出**：生成专业的Excel表格 + 命名规范的文书图片集合
- **大文件优化**：内置分批处理机制，支持超大PDF高效处理
- **生僻字校验**：专项验证和校正古籍中的形近字和生僻字

### 🔄 工作流

```
PDF输入 
  ↓
预检(文字层诊断+页数)
  ↓
结构分析(布局/页码/篇章)
  ↓
OCR识别(方案选择)
  ↓
文书图片提取(像素级裁剪)
  ↓
质量校验(生僻字/形近字)
  ↓
交付物输出(Excel+图片)
```

### 🚀 快速开始

#### 1. 文字层诊断

```python
import sys
import os

# 加载 skill 脚本
sys.path.insert(0, os.path.join(os.getenv('SKILL_PATH'), 'ancient-pdf-extractor', 'scripts'))
from extract_regions import detect_text_layer_quality, get_page_count

# 获取PDF总页数
total = get_page_count("input.pdf")
print(f"总页数: {total}")

# 诊断文字层质量
result = detect_text_layer_quality("input.pdf", sample_pages=2)
print(f"文字层可靠: {result['reliable']}")
print(f"诊断原因: {result['reason']}")
```

| 诊断结果 | 推荐方案 |
|---------|---------|
| 所有字体无ToUnicode | ⚡ 使用视觉模型OCR |
| 有ToUnicode + 文字正常 | ✅ 直接提取文字 |
| 有ToUnicode但大量乱码 | ⚡ 使用视觉模型OCR |

#### 2. 视觉模型OCR

```python
from extract_regions import render_page

# 渲染页面为高分辨率图片 (288DPI)
img = render_page("input.pdf", page_idx=0, scale=4.0)

# 使用视觉模型识别 (via view_image API)
# 精确prompt要求保留特殊符号：[1]、（）、□等
```

#### 3. 文书图片提取

```python
from extract_regions import render_page, analyze_layout, crop_with_buffer

# 高分辨率渲染 (432DPI)
img = render_page("input.pdf", page_idx=0, scale=6.0)

# 自动布局分析
layout = analyze_layout(img)

# 精确裁剪并保存
for i, doc_region in enumerate(layout["doc_images"]):
    cropped = crop_with_buffer(img, doc_region, buffer=30)
    cropped.save(f"文书图片/碑铭_{i:03d}.png")
```

#### 4. 大PDF分批处理

```python
from extract_regions import get_batch_ranges, render_page_range

total = get_page_count("large_document.pdf")

# 分批渲染处理（每批10页）
batches = get_batch_ranges(total, batch_size=10)
for start, end in batches:
    paths = render_page_range(
        "large_document.pdf", 
        start, end, 
        scale=4.0, 
        output_dir="./hd_pages"
    )
    # 对每张图片进行OCR...
```

### 📁 项目结构

```
ancient-pdf-extractor/
├── SKILL.md              # Skill定义和快速参考
├── README.md             # 本文档
├── scripts/
│   ├── extract_regions.py       # 核心处理函数库
│   └── __pycache__/
└── references/
    └── workflow.md       # 详细工作流文档
```

### ⚠️ 关键陷阱

1. **不要用视觉模型返回的百分比坐标裁剪文书图片** — 误差会导致20-50px的边界截断
2. **禁止一次性渲染大PDF全部页面** — 必须分批处理，防止内存溢出
3. **整页识别不如分段识别准确** — 低频字易被近义词替换，应按段/句裁剪重新识别

### 📖 详细文档

- **[工作流详解](references/workflow.md)** — 完整的六阶段处理流程、常见问题和经验教训
- **[SKILL定义](SKILL.md)** — Skill触发条件和核心决策点

### 🔧 依赖

- `pypdf` / `pdfplumber` — PDF文本提取
- `pypdfium2` — 高质量PDF渲染
- `PIL/Pillow` — 图像处理
- 视觉模型API（如Claude vision、GPT-4V等）

### 💡 适用场景

✅ 敦煌文书、碑铭、出土文献的数字化整理  
✅ 古籍研究著作中嵌入影印件的提取  
✅ 需要同时提取文字和图片的古代文献PDF  
✅ 大规模古籍数字资源的批量处理  

❌ 单纯的现代印刷文本PDF（推荐用更轻量的方案）  
❌ 需要OCR纠错或NER任务的场景

### 📝 使用建议

1. **优先读[工作流详解](references/workflow.md)** — 了解完整的处理思路
2. **从小规模测试开始** — 先用示例PDF验证流程
3. **保存中间结果** — 便于质量检查和问题排查
4. **关注生僻字校验** — 古籍中的形近字需要专项验证

---

## English

### 📚 Project Overview

**Ancient PDF Extractor** is a professional digital humanities skill designed for academic publications on ancient texts, particularly for handling mixed layouts combining "modern typeset + embedded document facsimiles" (such as *Dunhuang Stele Eulogies*, *British Library Dunhuang Manuscripts*, *Bibliothèque nationale de France Dunhuang Collection*, etc.).

### ✨ Key Features

- **Text Layer Diagnosis**: Intelligently detects PDF text layer quality and automatically selects the optimal OCR method
- **Visual OCR Recognition**: Leverages vision models for high-accuracy OCR with special handling of rare characters
- **Document Image Extraction**: Pixel-level precise cropping of facsimile documents, automatic header removal and document segmentation
- **Structured Output**: Generates professional Excel tables + properly named document image collections
- **Large File Optimization**: Built-in batch processing for efficient handling of extra-large PDFs
- **Rare Character Validation**: Specialized verification and correction of orthographic variants in ancient texts

### 🔄 Workflow

```
PDF Input
  ↓
Pre-check (Text layer diagnosis + page count)
  ↓
Structure Analysis (Layout / Page numbers / Chapters)
  ↓
OCR Recognition (Method selection)
  ↓
Document Image Extraction (Pixel-level cropping)
  ↓
Quality Validation (Rare characters / Similar characters)
  ↓
Deliverable Output (Excel + Images)
```

### 🚀 Quick Start

#### 1. Text Layer Diagnosis

```python
import sys
import os

# Load skill scripts
sys.path.insert(0, os.path.join(os.getenv('SKILL_PATH'), 'ancient-pdf-extractor', 'scripts'))
from extract_regions import detect_text_layer_quality, get_page_count

# Get total page count
total = get_page_count("input.pdf")
print(f"Total pages: {total}")

# Diagnose text layer quality
result = detect_text_layer_quality("input.pdf", sample_pages=2)
print(f"Text layer reliable: {result['reliable']}")
print(f"Reason: {result['reason']}")
```

| Diagnosis Result | Recommended Method |
|------------------|-------------------|
| No ToUnicode in any fonts | ⚡ Use Vision Model OCR |
| ToUnicode present + normal text | ✅ Direct text extraction |
| ToUnicode present but garbled | ⚡ Use Vision Model OCR |

#### 2. Visual Model OCR

```python
from extract_regions import render_page

# Render page as high-resolution image (288DPI)
img = render_page("input.pdf", page_idx=0, scale=4.0)

# Recognize with vision model (via view_image API)
# Use precise prompts to preserve special symbols: [1], （）, □, etc.
```

#### 3. Document Image Extraction

```python
from extract_regions import render_page, analyze_layout, crop_with_buffer

# High-resolution rendering (432DPI)
img = render_page("input.pdf", page_idx=0, scale=6.0)

# Automatic layout analysis
layout = analyze_layout(img)

# Precise cropping and saving
for i, doc_region in enumerate(layout["doc_images"]):
    cropped = crop_with_buffer(img, doc_region, buffer=30)
    cropped.save(f"document_images/stele_{i:03d}.png")
```

#### 4. Large PDF Batch Processing

```python
from extract_regions import get_batch_ranges, render_page_range

total = get_page_count("large_document.pdf")

# Batch processing (10 pages per batch)
batches = get_batch_ranges(total, batch_size=10)
for start, end in batches:
    paths = render_page_range(
        "large_document.pdf", 
        start, end, 
        scale=4.0, 
        output_dir="./hd_pages"
    )
    # Apply OCR to each image...
```

### 📁 Project Structure

```
ancient-pdf-extractor/
├── SKILL.md              # Skill definition and quick reference
├── README.md             # This document
├── scripts/
│   ├── extract_regions.py       # Core processing library
│   └── __pycache__/
└── references/
    └── workflow.md       # Detailed workflow documentation
```

### ⚠️ Critical Pitfalls

1. **Don't crop document images using percentage coordinates from vision models** — Errors cause 20-50px boundary truncation
2. **Never render all pages of large PDFs at once** — Must use batch processing to prevent memory overflow
3. **Full-page recognition is less accurate than segment recognition** — Rare characters get replaced by similar characters; segment/sentence-level recognition is more reliable

### 📖 Detailed Documentation

- **[Workflow Details](references/workflow.md)** — Complete six-stage processing pipeline, FAQs and lessons learned
- **[SKILL Definition](SKILL.md)** — Skill activation conditions and key decision points

### 🔧 Dependencies

- `pypdf` / `pdfplumber` — PDF text extraction
- `pypdfium2` — High-quality PDF rendering
- `PIL/Pillow` — Image processing
- Vision model API (e.g., Claude Vision, GPT-4V, etc.)

### 💡 Applicable Scenarios

✅ Digitization of Dunhuang manuscripts, stelae, archaeological documents  
✅ Extraction of embedded facsimiles in academic publications on ancient texts  
✅ Ancient document PDFs requiring simultaneous text and image extraction  
✅ Batch processing of large-scale ancient text digital resources  

❌ Plain modern printed text PDFs (lighter solutions recommended)  
❌ Tasks requiring OCR error correction or NER

### 📝 Usage Recommendations

1. **Read [Workflow Details](references/workflow.md) first** — Understand the complete processing pipeline
2. **Start with small-scale tests** — Validate the workflow with sample PDFs
3. **Preserve intermediate results** — Facilitates quality checks and troubleshooting
4. **Pay attention to rare character validation** — Orthographic variants in ancient texts require special verification

### 🤝 Contributing

Contributions are welcome! Please open issues or submit pull requests for:
- Bug fixes
- Performance improvements
- Support for additional document types
- Better handling of edge cases

### 📄 License

This project is part of the digital humanities research at the intersection of ancient texts and computational methods.

---

**Last Updated**: 2026-05-20  
**Author**: Digital Humanities Research Team  
**GitHub**: [zrqexcellent/ancient-pdf-extractor](https://github.com/zrqexcellent/ancient-pdf-extractor)
