"""从矢量源图生成带透明圆角的多分辨率 WSLg 图标。"""

from pathlib import Path
import struct

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


ROOT = Path(__file__).resolve().parents[1]
ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)


def build_icon() -> None:
    renderer = QSvgRenderer(str(ROOT / "assets" / "icon.svg"))
    if not renderer.isValid():
        raise ValueError("无法读取应用图标 SVG。")

    entries = []
    images = []
    offset = 6 + 16 * len(ICON_SIZES)
    for size in ICON_SIZES:
        image = QImage(size * 4, size * 4, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        image = image.scaled(
            size, size, Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not image.save(buffer, "PNG"):
            raise RuntimeError(f"无法生成 {size} 像素图标。")
        png = bytes(buffer.data())
        entries.append(struct.pack(
            "<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(png), offset,
        ))
        images.append(png)
        offset += len(png)

    output = ROOT / "assets" / "icon.ico"
    output.write_bytes(
        struct.pack("<HHH", 0, 1, len(ICON_SIZES)) + b"".join(entries) + b"".join(images)
    )
    print(f"已生成 {output}（{len(ICON_SIZES)} 种尺寸）。")


if __name__ == "__main__":
    build_icon()
