# TexBook

PDF 转 LaTeX 的 Python CLI 工具。它面向中文数学讲义：先从 PDF 提取页面文本、位置、字号并渲染页面图像，再调用 OpenAI-compatible 视觉模型重建 LaTeX 正文片段，最后由本地代码生成完整 `.tex` 文档。

## 环境要求

- Python 3.10+（开发验证环境使用 3.13）
- 可访问的 OpenAI-compatible API，且模型需要支持图片输入
- 推荐使用 [uv](https://docs.astral.sh/uv/) 管理依赖

TexBook 只安装 PDF 转 LaTeX 工具本身。生成的 `.tex` 默认使用 `ctexart`、`amsmath`、`amsthm`、`amssymb`；如果需要在本地编译生成结果，请自行准备 TeX Live、`xelatex` 和 `latexmk`。

## 安装

推荐使用 uv：

```bash
uv sync
```

也可以只安装运行时依赖：

```bash
uv pip install -e .
```

或使用 pip：

```bash
pip install -e .
```

包源码位于 `src/texbook`，从仓库根目录以可编辑模式安装后即可使用 `texbook` 命令。

## 配置

转换前需要配置模型和密钥：

```bash
export TEXBOOK_MODEL="your-vision-model"
export TEXBOOK_API_KEY="your-api-key"
export TEXBOOK_BASE_URL="https://your-api.example/v1"
```

`TEXBOOK_BASE_URL` 是可选项；使用默认 OpenAI SDK 地址时可以不设置。

也可以在命令行中使用 `--model`、`--api-key`、`--base-url` 临时覆盖环境变量。

## 使用方法

单文件转换到 stdout：

```bash
uv run texbook extract "input/lecture.pdf"
```

单文件转换到指定文件：

```bash
uv run texbook extract "input/lecture.pdf" -o "output/lecture.tex"
```

只给 `-o` 文件名时，输出路径会解析到仓库根目录的 `src/` 下；带目录时按仓库根目录解析。路径包含空格时请使用引号。

当前 `extract` 的 `-o` 始终表示单个 `.tex` 输出文件，不会根据路径后缀或目标路径是否为目录自动切换输出模式。目录化项目输出使用显式入口：

```bash
uv run texbook extract "input/lecture.pdf" --project -o "lecture-project"
```

只给 `-o` 项目名时，项目目录会解析到仓库根目录的 `src/` 下，例如 `src/lecture-project/main.tex`。项目模式默认只写入不存在或空目录；目标项目目录非空时会拒绝覆盖。确认要清空该项目目录并重新生成时，添加 `--force`：

```bash
uv run texbook extract "input/lecture.pdf" --project -o "lecture-project" --force
```

只转换部分页面：

```bash
uv run texbook extract "input/lecture.pdf" --pages 1,3-6 -o "output/partial.tex"
```

追加一次性转换要求：

```bash
uv run texbook extract "input/lecture.pdf" --pages 7 -o "output/formulas.tex" \
  --extra-prompt "只提取数学公式，忽略其他文字"
```

批量转换目录中的 PDF：

```bash
uv run texbook batch input/ -o output/
```

`batch` 默认匹配 `*.pdf`，并把每个 PDF 写成同名 `.tex`。单个文件失败时会记录原因并继续处理后续文件；如果没有匹配文件或存在失败文件，命令会以非零退出码结束。

批量项目输出使用 `batch --project`，每个 PDF 写入独立项目目录：

```bash
uv run texbook batch input/ --project -o src/
```

例如 `input/book.pdf` 会写入 `src/book/main.tex`。`batch --project --force` 只会清空对应 PDF 的项目目录，不会清空整个输出父目录。

## 本地编译

如果本地存在 `.latexmkrc`、`src/.latexmkrc` 和 `scripts/post-build.sh`，可以从仓库根目录运行：

```bash
latexmk src/test.tex
latexmk "src/6.1 集合与映射.tex"
latexmk src/lecture-project/main.tex
```

也可以进入 `src/` 后运行：

```bash
cd src
latexmk test.tex
latexmk "6.1 集合与映射.tex"
latexmk lecture-project/main.tex
```

本地 `.latexmkrc` 使用 `xelatex`，把 PDF 输出到 `out/`，把辅助产物输出或归位到 `build/`。`out/` 和 `build/` 会按入口文件相对 `src/` 的父目录镜像，例如 `src/test.tex` 生成 `out/test.pdf` 与 `build/test.*`，`src/lecture-project/main.tex` 生成 `out/lecture-project/main.pdf` 与 `build/lecture-project/main.*`。这些目录默认不进入 Git。

## 标题、日期和 Prompt 预设

- 默认使用 PDF 文件名作为 `\title{}`。
- `extract --title "..."` 可手动指定单文件标题。
- `extract` 和 `batch` 都支持 `--title-source filename|llm`；`llm` 会结合文件名、页面 heading、页面开头文本和已生成 LaTeX 章节线索生成标题，失败时退回文件名。
- 默认生成 `\date{}` 隐藏日期；添加 `--show-date` 会生成 `\date{\today}`。
- 默认 Prompt 预设是 `chinese-math`，面向中文数学讲义。
- `--preset NAME` 可选择内置或仓库本地预设。
- `--extra-prompt` 会追加到预设自带额外说明之后。

预设管理命令：

```bash
uv run texbook presets list
uv run texbook presets show chinese-math
uv run texbook presets add --name chinese-math-lite
uv run texbook presets add --name chinese-math-lite --from-preset chinese-math --overwrite
```

仓库本地预设保存在 `config/texbook/presets/<name>.json`。名称需匹配 `[a-z0-9][a-z0-9_-]{1,63}`，且不能覆盖内置预设。

## 常用参数

- `--pages`：页码选择，例如 `1,3-6`，页码从 1 开始。
- `--chunk-pages`：每次发送给 LLM 的页数，默认 `4`。
- `--image-dpi`：页面图像渲染精度，默认 `160`。
- `--image-dpi-min`、`--image-dpi-max`：`auto` 图片模式的自适应 DPI 范围。
- `--image-format`：页面图像格式，支持 `png`、`jpeg`、`jpg`、`auto`。
- `--jpeg-quality`：JPEG 图像质量，默认 `85`。
- `--prefetch-chunks`：预渲染后续 chunk 数，默认 `1`；LLM 请求仍顺序发送。
- `--timeout`：LLM 响应读取超时秒数，默认不限制等待时间。
- `--max-tokens`：LLM 响应最大 token 数，默认 `128000`。
- `--temperature`：LLM 采样温度，默认 `1.0`；`extract` 和 `batch` 都支持。
- `--project`：输出目录化 LaTeX 项目；`extract` 需要同时指定 `-o <dir>`，`batch` 会为每个 PDF 创建独立项目目录。
- `--force`：仅与 `--project` 一起使用，清空目标项目目录后重新写入。
- `--cache-dir`：断点续传缓存目录，默认 `build/.texbook_cache/`。
- `--no-cache`：禁用 chunk 缓存。
- `--clear-cache`：清理当前 PDF 和参数对应的缓存后再转换。

断点续传缓存默认启用。相同 PDF、页码和转换参数重跑时会复用已完成 chunk；中途失败后再次运行可从已完成 chunk 继续。等待未命中缓存的 LLM chunk 时，交互式终端会在 stderr 显示加载提示，stdout 仍只输出 LaTeX，便于重定向。

## 项目结构

```text
.
├─ .gitignore
├─ .python-version
├─ pyproject.toml
├─ uv.lock
├─ config/
│  └─ texbook/
│     └─ presets/                 # 可选：仓库本地 Prompt 预设
├─ src/
│  └─ texbook/                    # Python 包
│     ├─ cli.py                   # 命令行入口
│     ├─ convert/                 # LaTeX 文档外壳组装与输出
│     ├─ extract/                 # PDF 文本、位置、字号与图像提取
│     └─ llm/                     # LLM 客户端、缓存、流水线和 Prompt
└─ tests/                         # 单元测试
```

本地常用目录约定：

- `input/`、`docs/`：可放置待转换 PDF，默认不进入 Git。
- `output/`、`src/*.tex`：可放置生成的 `.tex`，默认不进入 Git。
- `build/`：默认缓存目录，默认不进入 Git。
- `out/`：可作为本地编译输出目录，默认不进入 Git。

## 开发

```bash
uv sync --group dev
uv run pytest
uv run ruff check
```

## 许可证

MIT
