# LaTeX Tools

一个混合 LaTeX + Python 的仓库，用于中文数学讲义。

## 目录结构

```
src/
  *.tex                      LaTeX 源文档
  latex_tools/               Python 包，用于 PDF 提取与 LaTeX 转换
docs/                        原始 PDF
out/                         编译后的 PDF 输出（git 忽略）
build/                       LaTeX 构建产物（git 忽略）
```

## 环境要求

- TeX Live（需包含 xelatex、ctex 和 latexmk）
  ```bash
  sudo apt install texlive-xetex texlive-lang-chinese latexmk
  ```
- Python 3.13+ 和 uv
  ```bash
  uv python install 3.13
  ```

## 使用方法

### 编译 LaTeX

在 WSL 终端中运行：

```bash
latexmk src/test.tex
```

编译配置由仓库根目录的 `.latexmkrc` 统一管理：PDF 输出到 `out/`，其余 LaTeX 构建产物输出或归位到 `build/`。
多个不同文件名的 `.tex` 会在共用目录中按文件名区分各自的产物。
也可以在 `src/` 目录内运行 `latexmk test.tex`，`src/.latexmkrc` 会自动加载根目录配置。

### 提取 PDF 内容

```bash
# 单文件输出到 stdout
uv run latex-tools extract "docs/6.1 集合与映射.pdf"

# 单文件输出到指定文件
uv run latex-tools extract "docs/6.1 集合与映射.pdf" -o "src/6.1 集合与映射.tex"

# 批量转换 docs/ 目录下所有 PDF
uv run latex-tools batch docs/ -o src/
```

## 开发

```bash
uv sync --group dev
uv run pytest
uv run ruff check
```
