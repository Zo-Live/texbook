# 仓库协作说明

## 交流约定

使用中文与用户交流或编写文档。

## 当前仓库用途

这是一个混合 LaTeX + Python 的仓库，用于整理中文数学讲义。

- `docs/` 存放原始 PDF。
- `src/` 存放 LaTeX 源文件，以及 `latex_tools` Python 包。
- `out/` 存放编译后的 PDF，受 `.gitignore` 忽略。
- `build/` 存放 LaTeX 辅助产物，受 `.gitignore` 忽略。

## LaTeX 编译约定

主要使用 WSL 终端编译，不维护 Windows 侧 VS Code 终端或保存触发构建的行为。

推荐从仓库根目录运行：

```bash
latexmk src/test.tex
```

也可以进入 `src/` 后运行：

```bash
latexmk test.tex
```

`src/.latexmkrc` 会转发加载仓库根目录的 `.latexmkrc`。

`.latexmkrc` 是唯一的 LaTeX 编译配置入口：

- 使用 `xelatex`。
- PDF 输出到 `out/`。
- 其它构建产物输出或归位到 `build/`。
- `post-build.sh` 会把 `synctex.gz` 等 latexmk 临时放错位置的产物归位到 `build/`。

`out/` 与 `build/` 是共用目录。不同文件名的 `.tex` 会按文件名区分各自产物，例如：

- `src/test.tex` -> `out/test.pdf`、`build/test.*`
- `src/6.1 集合与映射.tex` -> `out/6.1 集合与映射.pdf`、`build/6.1 集合与映射.*`

同名 `.tex` 重新编译会覆盖同名 PDF，这是按文件名区分的预期行为。

## VS Code 配置状态

`LaTeX.code-workspace` 当前只保留工作区文件夹配置，不包含 LaTeX Workshop 自动构建设置。

不要重新添加保存 `.tex` 时触发构建的配置，除非用户明确要求重新维护该路径。

## PDF 转 LaTeX 工具

Python 包入口是 `latex-tools`，定义在 `pyproject.toml`。

常用命令：

```bash
uv run latex-tools extract "docs/6.1 集合与映射.pdf"
uv run latex-tools extract "docs/6.1 集合与映射.pdf" -o "src/6.1 集合与映射.tex"
uv run latex-tools extract "docs/6.1 集合与映射.pdf" --pages 7 --extra-prompt "只提取数学公式，忽略其他文字"
uv run latex-tools batch docs/ -o src/
```

路径约定：

- `extract` 不带 `-o` 时输出到 stdout。
- `extract -o` 的相对路径按仓库根目录解析；只给文件名时默认写入 `src/`。
- `batch docs/ -o src/` 会把 `docs/` 下的 PDF 转成同名 `.tex` 并写入 `src/`。

常用参数：

- `--chunk-pages` 控制每次发送给 LLM 的页数，默认 `4`。
- `--image-dpi` 控制页面图像渲染精度，默认 `160`。
- `--image-dpi-min`、`--image-dpi-max` 控制 `auto` 图片模式的自适应 DPI 范围。
- `--image-format` 支持 `png`、`jpeg`、`jpg`、`auto`。
- `--jpeg-quality` 控制 JPEG 图像质量，默认 `85`。
- `--prefetch-chunks` 控制预渲染的后续 chunk 数，默认 `1`；LLM 请求仍保持顺序发送。

断点续传缓存：

- CLI 默认启用 chunk 级缓存，目录为 `build/.latex_tools_cache/`。
- 重跑相同 PDF、页码和转换参数时会复用已完成 chunk；失败后可从已完成 chunk 继续。
- 使用 `--no-cache` 禁用缓存，`--clear-cache` 清理当前 PDF/参数对应缓存，`--cache-dir` 指定缓存目录。

转换流程当前会：

- 先用 `pymupdf` 提取页级文本、位置、字号，并渲染页面图像。
- 把这些上下文发送给 OpenAI-compatible API，由 LLM 重建 LaTeX 正文片段。
- 由本地代码固定 `ctexart`、`amsmath`、`amsthm`、`amssymb` 的文档外壳。
- 仍保留文本层识别结果作为 LLM 辅助信息。

使用前需要配置：

- `LATEX_TOOLS_LLM_MODEL`
- `LATEX_TOOLS_LLM_API_KEY`
- 可选 `LATEX_TOOLS_LLM_BASE_URL`

## 验证命令

修改工程配置后，优先运行：

```bash
perl -c .latexmkrc
bash -n scripts/post-build.sh
python3 -m json.tool LaTeX.code-workspace
python3 -m py_compile src/latex_tools/cli.py src/latex_tools/convert/latex_converter.py src/latex_tools/extract/base.py src/latex_tools/extract/text_extractor.py src/latex_tools/llm/cache.py src/latex_tools/llm/config.py src/latex_tools/llm/client.py src/latex_tools/llm/pipeline.py src/latex_tools/llm/prompts.py
latexmk src/test.tex
```

如果验证 PDF 转 LaTeX 工具，可运行：

```bash
uv run latex-tools extract "docs/6.1 集合与映射.pdf" --pages 7 > /tmp/latex_tools_extract_stdout.tex
uv run latex-tools batch docs/ -o src/
```

验证 PDF 转 LaTeX 工具时，优先选择 1 页或少量页，例如 `--pages 7` 或 `--pages 15-17`，避免无意中处理完整文件。只有在需要验证整篇、批量或跨页行为时才运行完整 PDF 或 `batch`，并说明原因。

在受限沙箱中，`uv` 可能需要写用户缓存目录；如果因缓存目录权限失败，需要在获得授权后重试。
