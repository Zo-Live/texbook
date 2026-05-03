# LaTeX Tools

一个混合 LaTeX + Python 的仓库，用于中文数学讲义。

## 目录结构

```
src/
  *.tex                      LaTeX 源文档
  latex_tools/               Python 包，用于 LLM 辅助 PDF 转 LaTeX
docs/                        原始 PDF（git 忽略）
out/                         编译后的 PDF 输出（git 忽略）
build/                       LaTeX 构建产物（git 忽略）
```

## 环境要求

- TeX Live（需包含 xelatex、ctex 和 latexmk）
  ```bash
  sudo apt install texlive-xetex texlive-lang-chinese latexmk
  ```
- Python 3.10+（开发验证环境使用 3.13）

## 安装

推荐使用 [uv](https://docs.astral.sh/uv/)：

```bash
# 克隆后进入仓库根目录
uv sync              # 安装项目依赖（含开发组）
# 或
uv pip install -e .  # 仅安装运行时依赖
```

也可以直接使用 pip：

```bash
pip install -e .
```

> 包源码位于 `src/latex_tools`，因此需要从仓库根目录以可编辑模式（`-e`）安装，才能正确使用 `latex-tools` 命令。

## 使用方法

### 编译 LaTeX

在 WSL 终端中运行：

```bash
latexmk src/test.tex
```

编译配置由仓库根目录的 `.latexmkrc` 统一管理：PDF 输出到 `out/`，其余 LaTeX 构建产物输出或归位到 `build/`。
多个不同文件名的 `.tex` 会在共用目录中按文件名区分各自的产物。
也可以在 `src/` 目录内运行 `latexmk test.tex`，`src/.latexmkrc` 会自动加载根目录配置。

### LLM 辅助转换 PDF

转换流程会先用 `pymupdf` 提取页级文本、位置、字号并渲染页面图像，再把这些上下文发送给 OpenAI-compatible API，由 LLM 生成 LaTeX 正文片段。本地代码负责固定 `ctexart`、数学包和定理环境的文档外壳。

需要先配置模型和密钥：

```bash
export LATEX_TOOLS_LLM_MODEL="your-vision-model"
export LATEX_TOOLS_LLM_API_KEY="your-api-key"

# 如使用第三方或自建 OpenAI-compatible 服务，再配置：
export LATEX_TOOLS_LLM_BASE_URL="https://your-api.example/v1"
```

常用命令：

```bash
# 单文件输出到 stdout
uv run latex-tools extract "docs/6.1 集合与映射.pdf"

# 单文件输出到指定文件
uv run latex-tools extract "docs/6.1 集合与映射.pdf" -o "src/6.1 集合与映射.tex"

# 只转换部分页面
uv run latex-tools extract "docs/6.1 集合与映射.pdf" --pages 1,3-6 -o "src/6.1 集合与映射.tex"

# 追加自定义要求，例如只提取数学公式
uv run latex-tools extract "docs/6.1 集合与映射.pdf" --pages 7  -o "src/extra.tex"\
  --extra-prompt "只提取数学公式，忽略其他文字"

# 批量转换 docs/ 目录下所有 PDF
uv run latex-tools batch docs/ -o src/
```

可选参数：

- `--model`、`--api-key`、`--base-url` 可覆盖环境变量。
- `--extra-prompt` 追加到默认 system prompt 后的自定义要求，可用于指定提取内容类型、格式偏好等。
- `--chunk-pages` 控制每次发送给 LLM 的页数，默认 `4`。
- `--image-dpi` 控制页面图像渲染精度，默认 `160`。
- `--image-dpi-min`、`--image-dpi-max` 控制 `auto` 图片模式的自适应 DPI 范围。
- `--image-format` 控制页面图像格式，支持 `png`、`jpeg`、`jpg`、`auto`。
- `--jpeg-quality` 控制 JPEG 图像质量，默认 `85`。
- `--prefetch-chunks` 控制预渲染的后续 chunk 数，默认 `1`；LLM 请求仍保持顺序发送。
- `--cache-dir` 指定断点续传缓存目录，默认 `build/.latex_tools_cache/`。
- `--no-cache` 禁用 chunk 缓存；`--clear-cache` 清理当前 PDF 和参数对应的缓存后再转换。
- 使用的模型需要支持图片输入；否则数学公式和版面还原质量会明显下降。

断点续传缓存默认启用。相同 PDF、页码和转换参数重跑时会复用已完成 chunk；中途失败后再次运行可从已完成 chunk 继续。

## 开发

```bash
uv sync --group dev
uv run pytest
uv run ruff check
```
