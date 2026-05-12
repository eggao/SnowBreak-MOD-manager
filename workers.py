import os
from typing import Tuple

from PyQt6.QtCore import QThread, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap

from config import normalize_path, load_config
from utils import load_qpixmap
from models import FsNode
from i18n import tr

class ScanWorker(QThread):
    finished_signal = pyqtSignal(FsNode)
    error_signal = pyqtSignal(str)

    def __init__(self, source_root: str, max_nodes: int = 20000):
        super().__init__()
        self.source_root = source_root
        self.max_nodes = max_nodes
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            root_node = self._build_fs_tree(self.source_root)
            if not self._cancel:
                self.finished_signal.emit(root_node)
        except Exception as e:
            if not self._cancel:
                self.error_signal.emit(str(e))

    def _build_fs_tree(self, root_path: str) -> FsNode:
        root_path = normalize_path(root_path)
        if not root_path:
            raise ValueError(tr("源MOD目录为空"))
        if not os.path.isdir(root_path):
            raise ValueError(tr("源MOD目录不存在或不是文件夹"))

        counter = 0
        cfg = load_config()
        comments = cfg.get("comments", {})

        def walk_dir(path: str, parent: FsNode) -> None:
            nonlocal counter
            if self._cancel or counter >= self.max_nodes:
                return

            try:
                with os.scandir(path) as it:
                    entries = list(it)
            except OSError:
                return

            for e in entries:
                if self._cancel or counter >= self.max_nodes:
                    break
                try:
                    is_dir = e.is_dir(follow_symlinks=False)
                    stat = e.stat(follow_symlinks=False)
                    mtime = stat.st_mtime
                except OSError:
                    is_dir = False
                    mtime = 0.0

                counter += 1
                child_node = FsNode(name=e.name, path=e.path, is_dir=is_dir, parent=parent, mtime=mtime)
                
                try:
                    rel_path = os.path.relpath(e.path, root_path)
                    if rel_path in comments:
                        child_node.comment = comments[rel_path]
                except Exception:
                    pass
                    
                parent.children.append(child_node)
                if is_dir:
                    walk_dir(e.path, child_node)

        root_node = FsNode(name=os.path.basename(root_path) or root_path, path=root_path, is_dir=True)
        walk_dir(root_path, root_node)
        return root_node

class ThumbLoaderWorker(QThread):
    thumb_loaded_signal = pyqtSignal(object, QPixmap)

    def __init__(self, items: list[Tuple[FsNode, str]]):
        super().__init__()
        self.items = items
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        for node, path in self.items:
            if self._cancel:
                break
            try:
                pixmap = load_qpixmap(path, QSize(40, 40))
                if pixmap and not pixmap.isNull():
                    self.thumb_loaded_signal.emit(node, pixmap)
            except Exception:
                pass
