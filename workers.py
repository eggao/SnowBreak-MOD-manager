import os
import json
from typing import Tuple

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QPixmap

from config import normalize_path, load_config
from utils import load_cached_thumb, THUMB_CELL_SIZE
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
        dir_comment_cache: dict[str, dict] = {}

        def load_dir_comments(dir_path: str) -> dict:
            cached = dir_comment_cache.get(dir_path)
            if cached is not None:
                return cached
            info_path = os.path.join(dir_path, "info.json")
            data = {}
            try:
                if os.path.isfile(info_path):
                    with open(info_path, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                    if isinstance(loaded, dict):
                        raw = loaded.get("comments", loaded)
                        if isinstance(raw, dict):
                            data = {str(k): str(v) for k, v in raw.items() if isinstance(k, str) and isinstance(v, str)}
            except Exception:
                data = {}
            dir_comment_cache[dir_path] = data
            return data

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
                if e.name.lower() == "info.json":
                    continue
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
                    if not is_dir and child_node.is_pak:
                        dir_comments = load_dir_comments(path)
                        if e.name in dir_comments:
                            child_node.comment = dir_comments[e.name]
                        else:
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
                pixmap = load_cached_thumb(path, THUMB_CELL_SIZE)
                if pixmap and not pixmap.isNull():
                    self.thumb_loaded_signal.emit(node, pixmap)
            except Exception:
                pass

class CommentMigrateWorker(QThread):
    finished_signal = pyqtSignal()

    def __init__(self, source_root: str, legacy_comments: dict):
        super().__init__()
        self.source_root = normalize_path(source_root)
        self.legacy_comments = legacy_comments if isinstance(legacy_comments, dict) else {}
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        if not self.source_root or not os.path.isdir(self.source_root):
            self.finished_signal.emit()
            return

        per_dir: dict[str, dict[str, str]] = {}
        for rel_path, comment in list(self.legacy_comments.items()):
            if self._cancel:
                return
            if not isinstance(rel_path, str) or not isinstance(comment, str):
                continue
            comment = comment.strip()
            if not comment:
                continue

            abs_path = normalize_path(os.path.join(self.source_root, rel_path))
            if not abs_path.lower().endswith(".pak"):
                continue
            if not os.path.isfile(abs_path):
                continue

            d = normalize_path(os.path.dirname(abs_path))
            n = os.path.basename(abs_path)
            if not d or not n:
                continue
            bucket = per_dir.get(d)
            if bucket is None:
                bucket = {}
                per_dir[d] = bucket
            bucket[n] = comment

        for d, mapping in per_dir.items():
            if self._cancel:
                return
            info_path = os.path.join(d, "info.json")
            data = {}
            try:
                if os.path.isfile(info_path):
                    with open(info_path, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                    if isinstance(loaded, dict):
                        data = loaded
            except Exception:
                data = {}

            comments = data.get("comments")
            if not isinstance(comments, dict):
                comments = {}

            for name, c in mapping.items():
                comments[name] = c

            data["comments"] = comments
            try:
                tmp = info_path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                os.replace(tmp, info_path)
            except Exception:
                pass

        self.finished_signal.emit()
