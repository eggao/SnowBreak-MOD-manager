import os
import shutil
import base64
import re
import tempfile
from datetime import datetime
from typing import List, Optional, Tuple
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from PyQt6.QtCore import Qt, QMimeData, pyqtSignal
from PyQt6.QtGui import QImage, QKeySequence, QPixmap
from PyQt6.QtWidgets import QApplication, QLabel

from utils import extract_virtual_files

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".webp")


class ClipboardFilePasteHelper:
    @staticmethod
    def paste_to_directory(target_dir: str, mime_data: QMimeData) -> Tuple[int, List[str]]:
        copied = 0
        errors: List[str] = []

        if (
            mime_data.hasFormat("FileGroupDescriptorW")
            or mime_data.hasFormat("FileGroupDescriptor")
        ) and mime_data.hasFormat("FileContents"):
            v_copied, v_errors = extract_virtual_files(target_dir)
            copied += v_copied
            errors.extend(v_errors)

        if mime_data.hasUrls():
            for url in mime_data.urls():
                if not url.isLocalFile():
                    continue
                src_path = url.toLocalFile()
                try:
                    if not os.path.exists(src_path):
                        continue
                    name = os.path.basename(src_path)
                    dst_path = os.path.join(target_dir, name)

                    if os.path.abspath(src_path).lower() == os.path.abspath(dst_path).lower():
                        continue

                    if os.path.isdir(src_path):
                        shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
                    else:
                        shutil.copy2(src_path, dst_path)
                    copied += 1
                except Exception as e:
                    errors.append(f"{os.path.basename(src_path)}: {e}")

        if copied == 0 and mime_data.hasImage():
            image = ClipboardDragImageHelper.extract_qimage(mime_data)
            if image is not None and not image.isNull():
                file_name = ClipboardFilePasteHelper._make_clipboard_image_name(target_dir)
                save_path = os.path.join(target_dir, file_name)
                if image.save(save_path, "PNG"):
                    copied += 1
                else:
                    errors.append("剪贴板图片保存失败")

        return copied, errors

    @staticmethod
    def _make_clipboard_image_name(target_dir: str) -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"clipboard_image_{ts}"
        candidate = base_name + ".png"
        i = 1
        while os.path.exists(os.path.join(target_dir, candidate)):
            candidate = f"{base_name}_{i}.png"
            i += 1
        return candidate


class ClipboardDragImageHelper:
    @staticmethod
    def is_supported_image_mime(mime_data: QMimeData) -> bool:
        if ClipboardDragImageHelper.extract_local_image_path(mime_data) is not None:
            return True
        image = ClipboardDragImageHelper.extract_qimage(mime_data)
        if image is not None and not image.isNull():
            return True
        return ClipboardDragImageHelper.extract_remote_image_url(mime_data) is not None

    @staticmethod
    def extract_local_image_path(mime_data: QMimeData) -> Optional[str]:
        if not mime_data.hasUrls():
            return None
        for url in mime_data.urls():
            if not url.isLocalFile():
                continue
            file_path = url.toLocalFile()
            ext = os.path.splitext(file_path)[1].lower()
            if ext in IMAGE_EXTENSIONS:
                return file_path
        return None

    @staticmethod
    def extract_qimage(mime_data: QMimeData) -> Optional[QImage]:
        if not mime_data.hasImage():
            return None
        data = mime_data.imageData()
        if isinstance(data, QImage):
            return data
        if isinstance(data, QPixmap):
            return data.toImage()
        if hasattr(data, "toImage"):
            try:
                return data.toImage()
            except Exception:
                return None
        return None

    @staticmethod
    def extract_remote_image_url(mime_data: QMimeData) -> Optional[str]:
        if mime_data.hasUrls():
            for url in mime_data.urls():
                if url.isLocalFile():
                    continue
                s = url.toString()
                parsed = urlparse(s)
                if parsed.scheme in ("http", "https", "data"):
                    return s

        if mime_data.hasText():
            text = (mime_data.text() or "").strip()
            m = re.search(r"(https?://[^\s'\"<>]+|data:image/[^\s'\"<>]+)", text)
            if m:
                return m.group(1)

        return None


class RemoteImageFetcher:
    @staticmethod
    def fetch_to_temp(url: str, timeout_sec: int = 10, max_bytes: int = 20 * 1024 * 1024) -> Tuple[Optional[str], Optional[str]]:
        if not url:
            return None, "URL为空"

        if url.startswith("data:image/"):
            return RemoteImageFetcher._fetch_data_url_to_temp(url)

        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return None, f"不支持的URL协议：{parsed.scheme}"

        ext = os.path.splitext(parsed.path)[1].lower()
        if ext not in IMAGE_EXTENSIONS:
            ext = ".png"

        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urlopen(req, timeout=timeout_sec) as resp:
                content_type = (resp.headers.get("Content-Type") or "").lower()
                if ext == ".png":
                    mapped = RemoteImageFetcher._content_type_to_ext(content_type)
                    if mapped is not None:
                        ext = mapped

                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
                tmp_path = tmp.name
                total = 0
                too_large = False
                try:
                    while True:
                        chunk = resp.read(64 * 1024)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > max_bytes:
                            too_large = True
                            break
                        tmp.write(chunk)
                finally:
                    tmp.close()

                if too_large:
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
                    return None, f"图片过大（>{max_bytes}字节）"

            return tmp_path, None
        except Exception as e:
            return None, f"{type(e).__name__}: {e}"

    @staticmethod
    def _content_type_to_ext(content_type: str) -> Optional[str]:
        if "image/png" in content_type:
            return ".png"
        if "image/jpeg" in content_type:
            return ".jpg"
        if "image/webp" in content_type:
            return ".webp"
        if "image/bmp" in content_type:
            return ".bmp"
        return None

    @staticmethod
    def _fetch_data_url_to_temp(data_url: str) -> Tuple[Optional[str], Optional[str]]:
        m = re.match(r"^data:(image/[a-zA-Z0-9.+-]+);base64,(.+)$", data_url, re.DOTALL)
        if not m:
            return None, "无法解析data URL"
        mime = (m.group(1) or "").lower()
        payload = m.group(2) or ""

        ext = RemoteImageFetcher._content_type_to_ext(mime) or ".png"
        try:
            data = base64.b64decode(payload, validate=False)
        except Exception as e:
            return None, f"{type(e).__name__}: {e}"

        try:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
            tmp_path = tmp.name
            try:
                tmp.write(data)
            finally:
                tmp.close()
            return tmp_path, None
        except Exception as e:
            return None, f"{type(e).__name__}: {e}"


class PasteDropImageLabel(QLabel):
    doubleClicked = pyqtSignal()
    imageDropped = pyqtSignal(str)
    imagePasted = pyqtSignal(object)
    imageUrlDropped = pyqtSignal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit()
        super().mouseDoubleClickEvent(event)

    def dragEnterEvent(self, event):
        if ClipboardDragImageHelper.is_supported_image_mime(event.mimeData()):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dropEvent(self, event):
        mime_data = event.mimeData()
        image_path = ClipboardDragImageHelper.extract_local_image_path(mime_data)
        if image_path:
            self.imageDropped.emit(image_path)
            event.acceptProposedAction()
            return

        image = ClipboardDragImageHelper.extract_qimage(mime_data)
        if image is not None and not image.isNull():
            self.imagePasted.emit(image)
            event.acceptProposedAction()
            return

        url = ClipboardDragImageHelper.extract_remote_image_url(mime_data)
        if url:
            self.imageUrlDropped.emit(url)
            event.acceptProposedAction()
            return

        super().dropEvent(event)

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Paste):
            clipboard = QApplication.clipboard()
            mime_data = clipboard.mimeData()

            image_path = ClipboardDragImageHelper.extract_local_image_path(mime_data)
            if image_path:
                self.imageDropped.emit(image_path)
                return

            image = ClipboardDragImageHelper.extract_qimage(mime_data)
            if image is not None and not image.isNull():
                self.imagePasted.emit(image)
                return

            url = ClipboardDragImageHelper.extract_remote_image_url(mime_data)
            if url:
                self.imageUrlDropped.emit(url)
                return

        super().keyPressEvent(event)
