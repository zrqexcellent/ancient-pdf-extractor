---
name: ancient-pdf-extractor
description: >
  古籍研究著作PDF内容整理专用技能。提取OCR文字和文书影印件图片，
  输出结构化Excel + 命名图片。专门处理"现代印刷排版 + 嵌入古代文书影印件"
  的混合版面（如《敦煌碑铭讚辑释》《英藏敦煌文献》《法藏敦煌书苑》等）。
  触发条件：(1) 用户要求对古籍/敦煌/碑铭/出土文献类的PDF进行OCR识别、
  文字提取或图片截取；(2) 用户提供古籍研究著作PDF并要求整理内容、制作表格、
  提取文书图片；(3) 用户提到"古籍OCR""敦煌文书""碑铭赞""出土文献整理"
  等关键词；(4) PDF中同时包含印刷体正文和手写/影印文书图片，需要分别处理。
  核心能力：文字层诊断(判断pypdf是否可用) → 视觉模型逐页OCR →
  像素级精确裁剪文书图片 → 生僻字专项校验 → 结构化Excel输出。
  支持大PDF分批渲染（内置render_page/render_page_range等函数）。
---

# 古籍研究著作PDF内容整理

## 核心流程

```
PDF → 预检(文字层诊断+页数) → 结构分析 → OCR识别 → 文书图片提取 → 校验 → Excel+图片输出
```

**所有详细步骤、代码示例和经验教训见 [references/workflow.md](references/workflow.md)。**
以下仅列出核心决策点和快速参考。

## 1. 文字层诊断（必做，决定OCR方案）

```python
sys.path.insert(0, os.path.join(os.getenv('SKILL_PATH'), 'ancient-pdf-extractor', 'scripts'))
from extract_regions import detect_text_layer_quality, get_page_count

# 快速获取页数
total = get_page_count("input.pdf")
print(f"总页数: {total}")

# 诊断文字层
result = detect_text_layer_quality("input.pdf", sample_pages=2)
print(f"文字层可靠: {result['reliable']}")
print(f"原因: {result['reason']}")
```

| 诊断结果 | OCR方案 |
|---------|--------|
| 所有字体无ToUnicode | **必须用视觉模型**（pypdf文字层形近字错误率40-60%） |
| 有ToUnicode + 文字正常 | pypdf/pdfplumber直接提取即可 |
| 有ToUnicode但大量乱码 | 视觉模型 |

## 2. OCR方案B：视觉模型（古籍PDF标准方案）

1. **渲染**: `pypdfium2` scale=4（约288DPI），输出PNG
2. **逐页识别**: `view_image` + 精确prompt（要求保留[1]、（）、□等符号）
3. **生僻字校验**: 可疑字裁剪局部（单字/半行）重新识别

**关键陷阱**: 整页识别时低频字会被近义词替换（如"簉"→"筵"）。
分段/局部识别准确率 > 整页识别准确率。

## 3. 文书图片提取（像素级精确裁剪）

**不要用视觉模型返回的百分比坐标**（误差20-50px导致边缘截断）。

标准方法：
1. 高分辨率渲染 scale=6
2. 灰度+阈值(180)生成文字蒙版
3. 按行/列统计暗像素，自动检测文字边界
4. 排除页眉，在大间隙处分割上下文书
5. 边界外留30px缓冲裁剪

```python
from extract_regions import render_page, analyze_layout, crop_with_buffer

# 逐页渲染处理（内存友好）
img = render_page("input.pdf", page_idx=0, scale=6.0)
layout = analyze_layout(img)
for i, doc_region in enumerate(layout["doc_images"]):
    cropped = crop_with_buffer(img, doc_region, buffer=30)
    cropped.save(f"文书图片/{碑铭名称}_{原书页码}.png")
```

裁剪后用 `view_image` 逐张验证四边。左右边缘个别列截断需与原始PDF对比确认是否为原文排版特征。

## 4. 大PDF分批处理（>50页必用）

处理大PDF时**禁止一次性渲染全部页面**，必须使用内置分批函数：

```python
from extract_regions import get_page_count, get_batch_ranges, render_page_range, render_page

total = get_page_count("input.pdf")

# 方式1：分批渲染保存文件（适合批量预处理）
batches = get_batch_ranges(total, batch_size=10)  # [(0,10), (10,20), ...]
for start, end in batches:
    paths = render_page_range("input.pdf", start, end, scale=4.0, output_dir="./hd_pages")
    # 对 paths 中的图片逐张OCR...

# 方式2：逐页渲染（内存最优，适合分析+裁剪）
for i in range(total):
    img = render_page("input.pdf", i, scale=6.0)
    layout = analyze_layout(img)
    # 分析、裁剪...
    del img  # 显式释放内存
```

**规则：**
- ≤10页: 可用 `render_pdf_pages()` 一次性渲染
- 11-50页: 建议分批，每批10页
- >50页: **必须**分批，每批≤10页

## 5. 交付物格式

**Excel** 含以下Sheet：
- **篇目总览**: 序号/标题/编号/PDF页码/原书页码/摘要
- **完整OCR文字**: 按页码分行记录全部识别文字
- **文书图片**: 文件名/原书页码/嵌入图片/说明
- （可选）方案对比/教训与优化

**文书图片命名**: `{碑铭名称}_{原书页码}.png`，一页两张时加`_上`/`_下`

## 6. 常见陷阱速查

| 陷阱 | 症状 | 解决 |
|------|------|------|
| 无ToUnicode | pypdf提取全是形近字错误 | 用视觉模型OCR |
| 整页OCR生僻字错 | "簉"→"筵"等低频字被替换 | 裁剪局部重新识别 |
| 百分比坐标裁剪不准 | 边缘文字被截断 | 用像素级自动检测 |
| pdfplumber图片碎片 | 同一图片拆成多个碎片 | 不依赖图片坐标，用渲染+像素检测 |
| 左右边缘截断 | 边缘列文字缺失 | 与原始PDF对比确认是否原文特征 |
| 页码不对应 | PDF第1页≠原书第1页 | 始终同时记录PDF页码和原书页码 |
| 大PDF内存溢出 | 一次性渲染全部页面OOM | 用render_page_range分批渲染 |