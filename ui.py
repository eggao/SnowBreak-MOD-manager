import os
import shutil
import stat
import sys
from typing import Optional, Tuple

from PyQt6.QtCore import Qt, QSize, QPoint, QEvent, QModelIndex, QTimer, QByteArray, QRect, QPersistentModelIndex, QVariantAnimation, QEasingCurve, QObject, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap, QImage, QColor, QKeySequence, QShortcut, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QSplitter, QTreeView,
    QAbstractItemView, QFileDialog, QMessageBox, QHeaderView,
    QFrame, QSizePolicy, QMenu, QComboBox, QInputDialog, QDialog, QTextBrowser
)

from config import load_config, save_config, normalize_path, resource_path
from utils import PIL_AVAILABLE, PIL_IMPORT_ERROR, get_pillow_webp_support, is_pak_file, load_qpixmap
from models import FsNode, FsTreeModel, TreeItemDelegate
from workers import ScanWorker, ThumbLoaderWorker
from i18n import tr, get_available_languages, get_language, set_language
from transfer_helpers import ClipboardFilePasteHelper, PasteDropImageLabel, RemoteImageFetcher

class BranchTreeView(QTreeView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._branch_anims = {}
        self.expanded.connect(self._on_index_expanded)
        self.collapsed.connect(self._on_index_collapsed)

    def _start_branch_anim(self, index: QModelIndex, target_open: bool):
        pidx = QPersistentModelIndex(index)
        if not pidx.isValid():
            return

        existing = self._branch_anims.get(pidx)
        if existing:
            existing.stop()
            self._branch_anims.pop(pidx, None)

        start = 0.0
        end = 1.0
        if not target_open:
            start, end = 1.0, 0.0

        anim = QVariantAnimation(self)
        anim.setDuration(140)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        def _tick(_v=None):
            try:
                self.viewport().update()
            except Exception:
                pass

        def _done():
            self._branch_anims.pop(pidx, None)
            _tick()

        anim.valueChanged.connect(_tick)
        anim.finished.connect(_done)
        self._branch_anims[pidx] = anim
        anim.start()

    def _on_index_expanded(self, index: QModelIndex):
        self._start_branch_anim(index, True)

    def _on_index_collapsed(self, index: QModelIndex):
        self._start_branch_anim(index, False)

    def _branch_progress(self, index: QModelIndex) -> float:
        pidx = QPersistentModelIndex(index)
        anim = self._branch_anims.get(pidx)
        if anim:
            try:
                return float(anim.currentValue())
            except Exception:
                return 1.0 if self.isExpanded(index) else 0.0
        return 1.0 if self.isExpanded(index) else 0.0

    def drawBranches(self, painter, rect: QRect, index: QModelIndex):
        model = self.model()
        if model is None:
            return
        if not model.hasChildren(index):
            return

        seg = self.indentation() or 20
        icon_rect = QRect(rect.right() - seg, rect.top(), seg, rect.height())

        color = QColor("#FFFFFF")
        progress = self._branch_progress(index)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(color, 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        cx = icon_rect.center().x()
        cy = icon_rect.center().y()
        s = max(4, min(icon_rect.width(), icon_rect.height()) // 4)

        painter.translate(cx, cy)
        painter.rotate(90.0 * progress)
        painter.translate(-cx, -cy)

        painter.drawLine(cx - 1, cy - s, cx + s, cy)
        painter.drawLine(cx + s, cy, cx - 1, cy + s)

        painter.restore()

THEME_QSS = """
QWidget#Central {
  background: #0B1020;
}

QDialog, QMessageBox, QInputDialog, QFileDialog {
  background: #0F172A;
}

QFrame[card="true"] {
  background: #0F172A;
  border: 1px solid #1F2A44;
  border-radius: 5px;
}

QLabel[role="sectionTitle"] {
  color: #E5E7EB;
  font-weight: 600;
}

QLabel {
  color: #E5E7EB;
}

QLineEdit, QComboBox, QTextBrowser {
  background: #0B1224;
  border: 1px solid #22304D;
  border-radius: 5px;
  padding: 6px 10px;
  color: #E5E7EB;
  selection-background-color: #1D4ED8;
  selection-color: #FFFFFF;
}

QLineEdit:focus, QComboBox:focus, QTextBrowser:focus {
  border: 1px solid #3B82F6;
}

QComboBox::drop-down {
  border: 0px;
  width: 24px;
}

QComboBox QAbstractItemView {
  background: #0F172A;
  color: #E5E7EB;
  border: 1px solid #22304D;
  selection-background-color: #1E3A8A;
  selection-color: #FFFFFF;
  outline: 0;
}

QComboBox QAbstractItemView::viewport {
  background: #0F172A;
}

QComboBoxPrivateContainer {
  background: #0F172A;
  border: 1px solid #22304D;
  border-radius: 5px;
}

QComboBoxPrivateContainer QWidget {
  background: #0F172A;
  color: #E5E7EB;
}

QComboBox QAbstractItemView::item {
  padding: 6px 10px;
}

QComboBox QAbstractItemView::item:selected {
  background: #1E3A8A;
  color: #FFFFFF;
}

QPushButton {
  background: #0B1224;
  border: 1px solid #22304D;
  border-radius: 5px;
  padding: 6px 12px;
  color: #E5E7EB;
}

QPushButton[kind="treeTool"] {
  color: #FFFFFF;
}

QPushButton#BtnExpandAll, QPushButton#BtnCollapseAll {
  color: #FFFFFF;
  font-weight: 600;
}

QPushButton:hover {
  background: #111C33;
}

QPushButton:pressed {
  background: #16213D;
}

QPushButton:disabled {
  color: #94A3B8;
  background: #0B1224;
  border-color: #1F2A44;
}

QPushButton[variant="primary"] {
  background: #2563EB;
  border-color: #2563EB;
  color: #FFFFFF;
  font-weight: 600;
}

QPushButton[variant="primary"]:hover {
  background: #1D4ED8;
  border-color: #1D4ED8;
}

QPushButton[variant="success"] {
  background: #16A34A;
  border-color: #16A34A;
  color: #FFFFFF;
  font-weight: 600;
}

QPushButton[variant="success"]:hover {
  background: #15803D;
  border-color: #15803D;
}

QPushButton[variant="danger"] {
  background: #DC2626;
  border-color: #DC2626;
  color: #FFFFFF;
  font-weight: 600;
}

QPushButton[variant="danger"]:hover {
  background: #B91C1C;
  border-color: #B91C1C;
}

QTreeView {
  background: #0F172A;
  border: 1px solid #1F2A44;
  border-radius: 5px;
  outline: 0;
  selection-background-color: #1E3A8A;
  selection-color: #E5E7EB;
  alternate-background-color: #0F172A;
}

QTreeView::branch {
  background: transparent;
  border: 0px;
  width: 16px;
  height: 16px;
}

QTreeView::item {
  padding: 6px 8px;
  color: #E5E7EB;
  border-radius: 0px;
  background: transparent;
}

QTreeView::item:hover {
  background: #111C33;
}

QTreeView::item:selected {
  background: #1E3A8A;
}

QTreeView::indicator {
  width: 14px;
  height: 14px;
}

QTreeView::indicator:unchecked {
  background: transparent;
  border: 1px solid #64748B;
  border-radius: 3px;
}

QTreeView::indicator:unchecked:hover {
  background: #111C33;
  border-color: #93C5FD;
}

QTreeView::indicator:checked {
  background: transparent;
  border: 1px solid #93C5FD;
  border-radius: 3px;
}

QTreeView::indicator:checked:hover {
  background: transparent;
  border-color: #FFFFFF;
}

QTreeView::indicator:indeterminate {
  background: #2563EB;
  border: 1px solid #2563EB;
  border-radius: 3px;
}

QHeaderView::section {
  background: #0B1224;
  color: #CBD5E1;
  font-weight: 600;
  padding: 8px 8px;
  border: 0px;
  border-bottom: 1px solid #1F2A44;
}

QSplitter::handle {
  background: #1F2A44;
}

QFrame#PreviewFrame {
  background: #0F172A;
  border: 1px dashed #334155;
  border-radius: 5px;
}

QScrollBar:vertical {
  background: transparent;
  width: 10px;
  margin: 6px 4px 6px 4px;
}

QTreeView#DirTable QScrollBar:vertical {
  width: 20px;
}

QScrollBar::handle:vertical {
  background: #334155;
  min-height: 30px;
  border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
  background: #475569;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
  height: 0px;
}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
  background: transparent;
}
"""

class HelpWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("帮助"))
        self.resize(720, 560)

        layout = QVBoxLayout(self)
        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(True)
        layout.addWidget(self._browser)

    def set_html(self, html: str):
        self._browser.setHtml(html)

class TreeViewModel(QObject):
    loading_changed = pyqtSignal(bool, str)
    error = pyqtSignal(str)
    model_ready = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scan_worker: Optional[ScanWorker] = None
        self._thumb_worker: Optional[ThumbLoaderWorker] = None
        self._model: Optional[FsTreeModel] = None
        self._root: Optional[FsNode] = None
        self._source_dir: str = ""
        self._target_dir: str = ""
        self._sort_mode: str = "name_asc"
        self._dnd_mode: bool = False

    @property
    def model(self) -> Optional[FsTreeModel]:
        return self._model

    def set_target_dir(self, target_dir: str) -> None:
        self._target_dir = normalize_path(target_dir)
        self.update_enabled_marks()

    def set_sort_mode(self, sort_mode: str) -> None:
        self._sort_mode = sort_mode or "name_asc"
        if self._model:
            self._model.set_sort_mode(self._sort_mode)
            self.update_enabled_marks()

    def set_dnd_mode(self, enabled: bool) -> None:
        self._dnd_mode = bool(enabled)
        if self._model:
            self._model.apply_filter(self._dnd_mode)
            self.update_enabled_marks()

    def refresh(self, source_dir: str, sort_mode: str, dnd_mode: bool) -> None:
        self._source_dir = normalize_path(source_dir)
        self._sort_mode = sort_mode or "name_asc"
        self._dnd_mode = bool(dnd_mode)

        if self._scan_worker and self._scan_worker.isRunning():
            self._scan_worker.cancel()
            self._scan_worker.wait()
        if self._thumb_worker and self._thumb_worker.isRunning():
            self._thumb_worker.cancel()
            self._thumb_worker.wait()

        self._model = None
        self._root = None

        self.loading_changed.emit(True, tr("正在读取源MOD目录结构..."))
        self._scan_worker = ScanWorker(self._source_dir)
        self._scan_worker.finished_signal.connect(self._on_scan_finished)
        self._scan_worker.error_signal.connect(self._on_scan_error)
        self._scan_worker.start()

    def _on_scan_error(self, err: str):
        self.loading_changed.emit(False, tr("就绪"))
        self.error.emit(err or tr("未知错误"))

    def _on_scan_finished(self, root_node: FsNode):
        self._root = root_node
        self._model = FsTreeModel(root_node, self)
        self._model.set_sort_mode(self._sort_mode)
        if self._dnd_mode:
            self._model.apply_filter(True)

        self.update_enabled_marks()
        self._start_thumb_loading(root_node)
        self.model_ready.emit(self._model)
        self.loading_changed.emit(False, tr("就绪"))

    def _start_thumb_loading(self, root_node: FsNode):
        items_to_load = []
        def walk(n: FsNode):
            if n.is_pak and n.preview_path:
                items_to_load.append((n, n.preview_path))
            for c in n.children:
                walk(c)
        walk(root_node)

        if not items_to_load:
            return

        self._thumb_worker = ThumbLoaderWorker(items_to_load)
        self._thumb_worker.thumb_loaded_signal.connect(self._on_thumb_loaded)
        self._thumb_worker.start()

    def _on_thumb_loaded(self, node: FsNode, pixmap: QPixmap):
        if self._model:
            self._model.set_node_thumb(node, pixmap)

    def _is_pak_enabled(self, source_pak_path: str) -> bool:
        if not self._source_dir or not self._target_dir:
            return False
        if not os.path.isdir(self._target_dir):
            return False
        try:
            rel = os.path.relpath(source_pak_path, self._source_dir)
        except Exception:
            return False
        candidate = normalize_path(os.path.join(self._target_dir, rel))
        return os.path.isfile(candidate)

    def update_enabled_marks(self) -> None:
        if not self._model:
            return

        def walk(node: FsNode) -> Tuple[int, int]:
            if not node.is_dir and not node.is_pak:
                return 0, 0

            total = 0
            enabled = 0

            if node.is_dir:
                for c in node.children:
                    t, e = walk(c)
                    total += t
                    enabled += e
                if total > 0:
                    if enabled == total:
                        node.dir_state = "enabled"
                    elif enabled > 0:
                        node.dir_state = "partial"
                    else:
                        node.dir_state = None
                return total, enabled

            if node.is_pak:
                node.pak_enabled = self._is_pak_enabled(node.path)
                return 1, 1 if node.pak_enabled else 0

            return 0, 0

        walk(self._model._root)
        self._model.refresh_state_ui()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(tr("尘白MOD管理柒"))
        
        icon_path = resource_path("icon.png")
        if os.path.isfile(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            
        self.resize(1024, 680)

        self._vm = TreeViewModel(self)
        self._tree_model: Optional[FsTreeModel] = None
        self._dnd_mode_enabled = False
        self._current_sort_mode = "name_asc"
        self._help_window = None
        
        cfg = load_config()
        self.source_dir = normalize_path(str(cfg.get("source_dir", "")))
        self.target_dir = normalize_path(str(cfg.get("target_dir", "")))

        geometry_hex = cfg.get("window_geometry")
        if geometry_hex:
            try:
                self.restoreGeometry(QByteArray.fromHex(geometry_hex.encode("ascii")))
            except Exception:
                pass

        self._build_ui()
        self._apply_theme()

        self._vm.loading_changed.connect(self._set_loading)
        self._vm.error.connect(lambda err: self._error(tr("读取失败"), err))
        self._vm.model_ready.connect(self._on_tree_model_ready)
        
        if self.source_dir and os.path.isdir(self.source_dir):
            QTimer.singleShot(100, self.refresh_source_tree)

    def _apply_theme(self):
        self.setStyleSheet(THEME_QSS)

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("Central")
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # Top section (Paths)
        top_card = QFrame()
        top_card.setProperty("card", True)
        top_layout = QHBoxLayout(top_card)
        top_layout.setContentsMargins(12, 12, 12, 12)
        top_layout.setSpacing(10)
        
        self.lbl_src = QLabel(tr("源MOD目录："))
        top_layout.addWidget(self.lbl_src)
        self.src_edit = QLineEdit(self.source_dir)
        self.src_edit.returnPressed.connect(self.refresh_source_tree)
        top_layout.addWidget(self.src_edit, 1)
        self.btn_src = QPushButton(tr("选择..."))
        self.btn_src.clicked.connect(self._choose_source)
        top_layout.addWidget(self.btn_src)
        self.btn_open_src = QPushButton(tr("打开"))
        self.btn_open_src.clicked.connect(lambda: self._open_dir_in_explorer(self.src_edit.text()))
        top_layout.addWidget(self.btn_open_src)

        self.lbl_tgt = QLabel(tr("目标MOD目录："))
        top_layout.addWidget(self.lbl_tgt)
        self.tgt_edit = QLineEdit(self.target_dir)
        self.tgt_edit.returnPressed.connect(self._on_target_dir_entered)
        top_layout.addWidget(self.tgt_edit, 1)
        self.btn_tgt = QPushButton(tr("选择..."))
        self.btn_tgt.clicked.connect(self._choose_target)
        top_layout.addWidget(self.btn_tgt)
        self.btn_open_tgt = QPushButton(tr("打开"))
        self.btn_open_tgt.clicked.connect(lambda: self._open_dir_in_explorer(self.tgt_edit.text()))
        top_layout.addWidget(self.btn_open_tgt)
        
        self.btn_clear_target = QPushButton(tr("清空目标目录"))
        self.btn_clear_target.setProperty("variant", "danger")
        self.btn_clear_target.clicked.connect(self._clear_target_directory)
        top_layout.addWidget(self.btn_clear_target)

        main_layout.addWidget(top_card)

        # Middle section (Splitter)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.splitterMoved.connect(lambda pos, idx: self._on_splitter_moved())
        main_layout.addWidget(self.splitter, 1)

        # Left: Tree
        left_widget = QWidget()
        left_widget.setMinimumWidth(730) # 限制整个左侧区域（含按钮）的最小宽度
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)
        
        left_top = QHBoxLayout()
        left_top.setSpacing(8)
        self.lbl_src_struct = QLabel(tr("源MOD目录结构"))
        self.lbl_src_struct.setProperty("role", "sectionTitle")
        self.lbl_src_struct.setVisible(False)
        
        self.btn_dnd = QPushButton(tr("免打扰：关"))
        self.btn_dnd.setCheckable(True)
        self.btn_dnd.clicked.connect(self._toggle_dnd_mode)
        
        self.combo_sort = QComboBox()
        self.combo_sort.addItem(tr("按名称排序 (升序)"), "name_asc")
        self.combo_sort.addItem(tr("按名称排序 (降序)"), "name_desc")
        self.combo_sort.addItem(tr("按时间排序 (最新在前)"), "mtime_desc")
        self.combo_sort.addItem(tr("按时间排序 (最旧在前)"), "mtime_asc")
        self.combo_sort.currentIndexChanged.connect(self._on_sort_changed)
        
        self.btn_expand = QPushButton(tr("全部展开"))
        self.btn_expand.setObjectName("BtnExpandAll")
        self.btn_expand.setProperty("kind", "treeTool")
        self.btn_expand.clicked.connect(self._expand_all)
        self.btn_collapse = QPushButton(tr("全部收起"))
        self.btn_collapse.setObjectName("BtnCollapseAll")
        self.btn_collapse.setProperty("kind", "treeTool")
        self.btn_collapse.clicked.connect(self._collapse_all)
        self.btn_new_folder = QPushButton(tr("新建文件夹"))
        self.btn_new_folder.setObjectName("BtnNewFolder")
        self.btn_new_folder.setProperty("kind", "treeTool")
        self.btn_new_folder.clicked.connect(self._on_new_folder)
        self.btn_disable = QPushButton(tr("禁用"))
        self.btn_disable.setProperty("variant", "danger")
        self.btn_disable.clicked.connect(self._disable_checked)
        self.btn_enable = QPushButton(tr("启用"))
        self.btn_enable.setProperty("variant", "success")
        self.btn_enable.clicked.connect(self._enable_checked)
        self.btn_refresh = QPushButton(tr("刷新"))
        self.btn_refresh.clicked.connect(self.refresh_source_tree)
        
        left_group = QHBoxLayout()
        left_group.setSpacing(8)
        left_group.addWidget(self.btn_dnd)
        left_group.addWidget(self.combo_sort)
        left_group.addWidget(self.btn_expand)
        left_group.addWidget(self.btn_collapse)
        left_group.addWidget(self.btn_new_folder)
        
        right_group = QHBoxLayout()
        right_group.setSpacing(8)
        right_group.setContentsMargins(0, 0, 12, 0)
        right_group.addWidget(self.btn_disable)
        right_group.addWidget(self.btn_enable)
        right_group.addWidget(self.btn_refresh)
        
        left_top.addLayout(left_group)
        left_top.addStretch()
        left_top.addLayout(right_group)
        
        # Action Buttons Layout (New Features)
        action_layout = QHBoxLayout()
        action_layout.setSpacing(8)
        self.btn_save_state = QPushButton(tr("记忆当前启用状态"))
        self.btn_save_state.setProperty("variant", "primary")
        self.btn_save_state.clicked.connect(self._save_enabled_state)
        
        action_layout.addWidget(self.btn_save_state)
        action_layout.addSpacing(12)
        
        self.lbl_saved = QLabel(tr("已存记忆："))
        action_layout.addWidget(self.lbl_saved)
        self.combo_saved_states = QComboBox()
        self.combo_saved_states.setMinimumWidth(120)
        action_layout.addWidget(self.combo_saved_states)
        self._refresh_saved_states_combo()
        
        self.btn_apply_state = QPushButton(tr("应用记忆"))
        self.btn_apply_state.setProperty("variant", "primary")
        self.btn_apply_state.clicked.connect(self._apply_saved_state)
        
        self.btn_delete_state = QPushButton(tr("删除记忆"))
        self.btn_delete_state.setProperty("variant", "danger")
        self.btn_delete_state.clicked.connect(self._delete_saved_state)
        
        action_layout.addWidget(self.btn_apply_state)
        action_layout.addWidget(self.btn_delete_state)
        action_layout.setContentsMargins(0, 0, 0, 0)
        self.action_widget = QWidget()
        self.action_widget.setLayout(action_layout)
        self.action_widget.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        left_layout.addLayout(left_top)

        self.tree_view = BranchTreeView()
        self.tree_view.setObjectName("DirTable")
        self.tree_view.setMinimumWidth(730) # 限制左侧表格最小宽度
        self.tree_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tree_view.setAlternatingRowColors(False)
        self.tree_view.setAnimated(True)
        self.tree_view.setMouseTracking(True)
        self.tree_view.setAutoScroll(False)
        self.tree_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tree_view.viewport().installEventFilter(self)
        
        self.tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self._show_tree_context_menu)
        self.tree_view.doubleClicked.connect(self._on_tree_double_click)
        
        self.tree_delegate = TreeItemDelegate(self.tree_view)
        self.tree_view.setItemDelegate(self.tree_delegate)
        
        if self.tree_view.selectionModel():
            self.tree_view.selectionModel().selectionChanged.connect(self._on_tree_select)
            
        self.shortcut_paste = QShortcut(QKeySequence.StandardKey.Paste, self.tree_view)
        self.shortcut_paste.setContext(Qt.ShortcutContext.WidgetShortcut)
        self.shortcut_paste.activated.connect(self._on_tree_paste)
        
        left_layout.addWidget(self.tree_view, 1)
        self.splitter.addWidget(left_widget)

        # Right: Info & Preview
        right_widget = QWidget()
        right_widget.setMinimumWidth(100) # 限制右侧预览区域最小宽度
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(12, 0, 0, 0)
        right_layout.setSpacing(10)
        
        self.lbl_sel_info = QLabel(tr("选中项信息"))
        self.lbl_sel_info.setProperty("role", "sectionTitle")
        right_layout.addWidget(self.lbl_sel_info)
        
        path_layout = QHBoxLayout()
        self.lbl_path = QLabel(tr("路径："))
        path_layout.addWidget(self.lbl_path)
        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        path_layout.addWidget(self.path_edit, 1)
        right_layout.addLayout(path_layout)

        self.lbl_preview_title = QLabel(tr("预览："))
        self.lbl_preview_title.setProperty("role", "sectionTitle")
        right_layout.addWidget(self.lbl_preview_title)
        
        self.preview_frame = QFrame()
        self.preview_frame.setObjectName("PreviewFrame")
        self.preview_frame.setFrameShape(QFrame.Shape.Box)
        preview_frame_layout = QVBoxLayout(self.preview_frame)
        preview_frame_layout.setContentsMargins(12, 12, 12, 12)
        
        self.lbl_preview_img = PasteDropImageLabel(tr("可拖拽或粘贴图片到此处设置pak预览图。"))
        self.lbl_preview_img.setWordWrap(True)
        self.lbl_preview_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_preview_img.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.lbl_preview_img.doubleClicked.connect(self._on_preview_double_click)
        self.lbl_preview_img.imageDropped.connect(self._on_image_dropped)
        self.lbl_preview_img.imagePasted.connect(self._on_image_pasted)
        self.lbl_preview_img.imageUrlDropped.connect(self._on_image_url_dropped)
        preview_frame_layout.addWidget(self.lbl_preview_img)
        right_layout.addWidget(self.preview_frame, 1)

        self.splitter.addWidget(right_widget)
        self.splitter.splitterMoved.connect(self._on_splitter_moved)
        
        # 禁用左右两侧的折叠功能，强制生效 minimumWidth 限制
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)
        
        # Restore splitter state or set default
        cfg = load_config()
        saved_sizes = cfg.get("splitter_sizes")
        if isinstance(saved_sizes, list) and len(saved_sizes) == 2:
            self.splitter.setSizes(saved_sizes)
        else:
            self.splitter.setStretchFactor(0, 2)
            self.splitter.setStretchFactor(1, 1)
            self.splitter.setSizes([666, 333])

        # Bottom section
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(8)
        
        self.btn_help = QPushButton(tr("帮助"))
        self.btn_help.setProperty("variant", "primary")
        self.btn_help.clicked.connect(self._show_help)
        self.btn_exit = QPushButton(tr("退出"))
        self.btn_exit.setProperty("variant", "danger")
        self.btn_exit.clicked.connect(self.close)
        
        self.combo_lang = QComboBox()
        langs = get_available_languages()
        for code, name in langs.items():
            self.combo_lang.addItem(name, code)
        
        # Set current lang
        current_lang = get_language()
        idx = self.combo_lang.findData(current_lang)
        if idx >= 0:
            self.combo_lang.setCurrentIndex(idx)
            
        self.combo_lang.currentIndexChanged.connect(self._on_language_changed)
        
        if hasattr(self, "action_widget") and self.action_widget:
            bottom_layout.addWidget(self.action_widget)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.btn_help)
        bottom_layout.addWidget(self.combo_lang)
        bottom_layout.addWidget(self.btn_exit)
        main_layout.addLayout(bottom_layout)


    
    def changeEvent(self, event):
        from PyQt6.QtCore import QEvent
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

    def retranslateUi(self):
        from i18n import tr
        
        # Top layout
        self.setWindowTitle(tr("尘白MOD管理柒"))
        if hasattr(self, 'lbl_src'): self.lbl_src.setText(tr("源MOD目录："))
        if hasattr(self, 'btn_src'): self.btn_src.setText(tr("选择..."))
        if hasattr(self, 'btn_open_src'): self.btn_open_src.setText(tr("打开"))
        if hasattr(self, 'lbl_tgt'): self.lbl_tgt.setText(tr("目标MOD目录："))
        if hasattr(self, 'btn_tgt'): self.btn_tgt.setText(tr("选择..."))
        if hasattr(self, 'btn_open_tgt'): self.btn_open_tgt.setText(tr("打开"))
        if hasattr(self, 'btn_clear_target'): self.btn_clear_target.setText(tr("清空目标目录"))
        
        # Left Top layout
        if hasattr(self, 'lbl_src_struct'): self.lbl_src_struct.setText(tr("源MOD目录结构"))
        
        # Update toggle button text
        if hasattr(self, 'btn_dnd'):
            if getattr(self, '_dnd_mode_enabled', False):
                self.btn_dnd.setText(tr("免打扰：开"))
            else:
                self.btn_dnd.setText(tr("免打扰：关"))
            
        if hasattr(self, 'combo_sort'):
            self.combo_sort.setItemText(0, tr("按名称排序 (升序)"))
            self.combo_sort.setItemText(1, tr("按名称排序 (降序)"))
            self.combo_sort.setItemText(2, tr("按时间排序 (最新在前)"))
            self.combo_sort.setItemText(3, tr("按时间排序 (最旧在前)"))
        
        if hasattr(self, 'btn_expand'): self.btn_expand.setText(tr("全部展开"))
        if hasattr(self, 'btn_collapse'): self.btn_collapse.setText(tr("全部收起"))
        if hasattr(self, 'btn_new_folder'): self.btn_new_folder.setText(tr("新建文件夹"))
        if hasattr(self, 'btn_disable'): self.btn_disable.setText(tr("禁用"))
        if hasattr(self, 'btn_enable'): self.btn_enable.setText(tr("启用"))
        if hasattr(self, 'btn_refresh'): self.btn_refresh.setText(tr("刷新"))
        
        # Action layout
        if hasattr(self, 'btn_save_state'): self.btn_save_state.setText(tr("记忆当前启用状态"))
        if hasattr(self, 'lbl_saved'): self.lbl_saved.setText(tr("已存记忆："))
        if hasattr(self, 'btn_apply_state'): self.btn_apply_state.setText(tr("应用记忆"))
        if hasattr(self, 'btn_delete_state'): self.btn_delete_state.setText(tr("删除记忆"))
        
        # Right layout
        if hasattr(self, 'lbl_sel_info'): self.lbl_sel_info.setText(tr("选中项信息"))
        if hasattr(self, 'lbl_path'): self.lbl_path.setText(tr("路径："))
        if hasattr(self, 'lbl_preview_title'): self.lbl_preview_title.setText(tr("预览："))
        
        if hasattr(self, 'lbl_preview_img') and (not hasattr(self, "_current_preview_path") or not self._current_preview_path):
            self.lbl_preview_img.setText(tr("可拖拽或粘贴图片到此处设置pak预览图。"))
            
        # Bottom layout
        if hasattr(self, 'btn_help'): self.btn_help.setText(tr("帮助"))
        if hasattr(self, 'btn_exit'): self.btn_exit.setText(tr("退出"))
        
        if getattr(self, "_tree_model", None):
            self._tree_model.retranslate()
        self._update_help_window()

    def _update_help_window(self):
        try:
            if self._help_window:
                self._help_window.setWindowTitle(tr("帮助"))
                self._help_window.set_html(self._build_help_html())
        except Exception:
            self._help_window = None

    def _on_language_changed(self, index: int):
        lang_code = self.combo_lang.itemData(index)
        if lang_code and lang_code != get_language():
            set_language(lang_code)

    def _persist_paths(self):
        self.source_dir = normalize_path(self.src_edit.text())
        self.target_dir = normalize_path(self.tgt_edit.text())
        save_config({
            "source_dir": self.source_dir,
            "target_dir": self.target_dir,
        })

    def _on_target_dir_entered(self):
        self._persist_paths()
        self._vm.set_target_dir(self.target_dir)

    def _choose_source(self):
        path = QFileDialog.getExistingDirectory(self, tr("选择源MOD目录"), self.source_dir)
        if path:
            self.src_edit.setText(normalize_path(path))
            self._persist_paths()
            self.refresh_source_tree()

    def _choose_target(self):
        path = QFileDialog.getExistingDirectory(self, tr("选择目标MOD目录"), self.target_dir)
        if path:
            self.tgt_edit.setText(normalize_path(path))
            self._persist_paths()
            self._vm.set_target_dir(self.target_dir)

    def _open_dir_in_explorer(self, path: str):
        path = normalize_path(path)
        if not path:
            return
        if not os.path.isdir(path):
            return
        self._open_file_with_system(path)

    def _show_ok_dialog(self, icon: QMessageBox.Icon, title: str, text: str):
        box = QMessageBox(self)
        box.setIcon(icon)
        box.setWindowTitle(title)
        box.setText(text)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        ok_btn = box.button(QMessageBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setText(tr("确定"))
        box.exec()

    def _info(self, title: str, text: str):
        self._show_ok_dialog(QMessageBox.Icon.Information, title, text)

    def _warn(self, title: str, text: str):
        self._show_ok_dialog(QMessageBox.Icon.Warning, title, text)

    def _error(self, title: str, text: str):
        self._show_ok_dialog(QMessageBox.Icon.Critical, title, text)

    def _confirm_yes_no(self, title: str, text: str, default_yes: bool = False) -> bool:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(title)
        box.setText(text)
        btn_yes = box.addButton(tr("是"), QMessageBox.ButtonRole.AcceptRole)
        btn_no = box.addButton(tr("否"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(btn_yes if default_yes else btn_no)
        box.exec()
        return box.clickedButton() == btn_yes

    def _input_text(self, title: str, label: str, default: str = "", echo: QLineEdit.EchoMode = QLineEdit.EchoMode.Normal) -> Tuple[str, bool]:
        dlg = QInputDialog(self)
        dlg.setWindowTitle(title)
        dlg.setLabelText(label)
        dlg.setTextEchoMode(echo)
        dlg.setTextValue(default)
        dlg.setOkButtonText(tr("确定"))
        dlg.setCancelButtonText(tr("取消"))
        ok = dlg.exec() == QDialog.DialogCode.Accepted
        return (dlg.textValue() if ok else ""), ok

    def _set_loading(self, is_loading: bool, msg: str):
        self.btn_refresh.setEnabled(not is_loading)

    def refresh_source_tree(self):
        self.source_dir = normalize_path(self.src_edit.text())
        if not self.source_dir or not os.path.isdir(self.source_dir):
            self._warn(tr("提示"), tr("请先设置有效的源MOD目录"))
            return
        
        self._persist_paths()
        
        if self._tree_model is not None:
            self._saved_expanded_paths = self._get_expanded_paths()
        else:
            self._saved_expanded_paths = None

        self.tree_view.setModel(None)
        self._tree_model = None
        self._side_preview_path = None
        self.lbl_preview_img.clear()

        self._vm.set_target_dir(self.target_dir)
        self._vm.refresh(self.source_dir, self._current_sort_mode, self._dnd_mode_enabled)

    def _on_tree_model_ready(self, model: FsTreeModel):
        self._tree_model = model
        self.tree_view.setModel(self._tree_model)
        
        self.tree_view.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree_view.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.tree_view.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.tree_view.header().setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.tree_view.header().setStretchLastSection(False)
        
        cfg = load_config()
        
        self.tree_view.setColumnWidth(1, 60)
        
        col2_width = cfg.get("col2_width", 90)
        if col2_width > 120:
            col2_width = 120
        self.tree_view.setColumnWidth(2, col2_width)
        
        col3_width = cfg.get("col3_width", 150)
        self.tree_view.setColumnWidth(3, col3_width)
        
        self.tree_view.selectionModel().selectionChanged.connect(self._on_tree_select)
        self.tree_view.header().sectionResized.connect(self._on_column_resized)
        
        if self._dnd_mode_enabled:
            if getattr(self, "_saved_expanded_paths", None) is None:
                self.tree_view.expandAll()
                
        saved_paths = getattr(self, "_saved_expanded_paths", None)
        if saved_paths is not None and len(saved_paths) > 0:
            self._restore_expanded_paths(saved_paths)
            self._saved_expanded_paths = None

    def _on_column_resized(self, logicalIndex, oldSize, newSize):
        pass

    def _on_tree_select(self):
        sel_model = self.tree_view.selectionModel()
        if not sel_model:
            self.path_edit.clear()
            self._set_side_preview(None, is_pak=False)
            return
            
        sel = sel_model.selectedIndexes()
        if not sel:
            self.path_edit.clear()
            self._set_side_preview(None, is_pak=False)
            return
        
        idx = [i for i in sel if i.column() == 0]
        if not idx:
            return
            
        node: FsNode = idx[0].internalPointer()
        self.path_edit.setText(node.path)
        
        if node.is_pak and node.preview_path:
            self._set_side_preview(node.preview_path, is_pak=True)
        else:
            self._set_side_preview(node.path, is_pak=node.is_pak)

    def eventFilter(self, obj, event):
        if obj is self.tree_view.viewport():
            if event.type() == QEvent.Type.MouseButtonPress:
                # 点击空白区域时取消选择
                idx = self.tree_view.indexAt(event.pos())
                if not idx.isValid():
                    self.tree_view.clearSelection()
                    self._on_tree_select()
            elif event.type() == QEvent.Type.MouseMove:
                self._handle_tree_hover(event)
            elif event.type() == QEvent.Type.Leave:
                self._on_tree_select()
        return super().eventFilter(obj, event)

    def _handle_tree_hover(self, event):
        idx = self.tree_view.indexAt(event.pos())
        if not idx.isValid():
            self._on_tree_select()
            return
            
        if idx.column() == 1:
            node: FsNode = idx.internalPointer()
            if node.is_pak and node.preview_path:
                self._set_side_preview(node.preview_path, is_pak=True)
                return
        
        self._on_tree_select()

    def _set_side_preview(self, path: Optional[str], is_pak: bool = False):
        if not path or os.path.isdir(path):
            if is_pak:
                self.lbl_preview_img.setText(tr("可拖拽或粘贴图片到此处设置pak预览图。"))
            else:
                self.lbl_preview_img.clear()
            self._current_preview_path = None
            self._cached_full_pixmap = None
            return
            
        ext = os.path.splitext(path)[1].lower()
        if ext not in (".png", ".jpg", ".jpeg", ".bmp", ".webp"):
            if is_pak:
                self.lbl_preview_img.setText(tr("可拖拽或粘贴图片到此处设置pak预览图。"))
            else:
                self.lbl_preview_img.clear()
            self._current_preview_path = None
            self._cached_full_pixmap = None
            return

        size = self.preview_frame.size()
        size = QSize(max(size.width()-4, 1), max(size.height()-4, 1))
        
        try:
            current_path = getattr(self, "_current_preview_path", None)
            if current_path != path or not hasattr(self, "_cached_full_pixmap"):
                self._current_preview_path = path
                self._cached_full_pixmap = load_qpixmap(path, QSize(1920, 1080))
                
            if self._cached_full_pixmap:
                pixmap = self._cached_full_pixmap.scaled(
                    size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.lbl_preview_img.setPixmap(pixmap)
            else:
                self.lbl_preview_img.setText(tr("加载预览失败"))
        except Exception as e:
            self.lbl_preview_img.setText(tr("错误: {e}").format(e=e))

    def _on_splitter_moved(self):
        # 拖拽时直接使用缓存的 pixmap 进行快速缩放刷新，不重新读取图片
        if hasattr(self, "_cached_full_pixmap") and self._cached_full_pixmap:
            size = self.preview_frame.size()
            size = QSize(max(size.width()-4, 1), max(size.height()-4, 1))
            pixmap = self._cached_full_pixmap.scaled(
                size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.lbl_preview_img.setPixmap(pixmap)

    def _refresh_preview_size(self):
        if hasattr(self, "_current_preview_path"):
            self._set_side_preview(self._current_preview_path)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._on_splitter_moved()

    def closeEvent(self, event):
        geometry_hex = self.saveGeometry().toHex().data().decode("ascii")
        sizes = self.splitter.sizes()
        config_update = {
            "window_geometry": geometry_hex,
            "splitter_sizes": sizes
        }
        if self.tree_view.model():
            config_update["col2_width"] = self.tree_view.columnWidth(2)
            config_update["col3_width"] = self.tree_view.columnWidth(3)
            
        save_config(config_update)
        super().closeEvent(event)

    def _show_help(self):
        help_text = self._build_help_html()
        if not self._help_window:
            self._help_window = HelpWindow(self)
            self._help_window.destroyed.connect(lambda _=None: setattr(self, "_help_window", None))
        try:
            self._help_window.setWindowTitle(tr("帮助"))
            self._help_window.set_html(help_text)
            self._help_window.show()
            self._help_window.raise_()
            self._help_window.activateWindow()
        except Exception:
            self._help_window = None

    def _build_help_html(self) -> str:
        return (
            "<div style='line-height: 2em;font-size:14px;'>"
            "<h3 style='margin-bottom: 12px;'>" + tr("尘白MOD管理柒 帮助指南") + "</h3>"
            "<h4 style='margin: 14px 0 8px 0;'>" + tr("快速上手") + "</h4>"
            "<ol style='margin: 0; padding-left: 24px;'>"
            "<li style='margin-bottom: 10px;'>" + tr("<b>1. 设置 MOD 管理文件夹（源MOD目录）</b><br>选择一个用于存放 MOD 文件的文件夹。建议与 MOD 管理器所在的目录保持一致。") + "</li>"
            "<li style='margin-bottom: 10px;'>" + tr("<b>2. 设置游戏 MOD 安装目录（目标MOD目录）</b><br>将此路径指向游戏实际的 MOD 存放位置。默认路径示例：<br><code style='background-color: rgba(128, 128, 128, 0.2); padding: 2px 4px; border-radius: 4px;'>游戏文件夹/Game/Content/Paks/mods</code>") + "</li>"
            "<li style='margin-bottom: 10px;'>" + tr("<b>3. 添加你的 MOD</b><br>解压下载好的 MOD 压缩包，然后将文件复制到第 1 步设置的 MOD 管理文件夹中，可按你的习惯分类整理。<br>📸 <b>预览图</b>：如果你在与 <code>.pak</code> 文件相同的文件夹中放入一个同名的图片文件（png、jpg、bmp 或 webp），它将被自动识别为该 MOD 的预览图。") + "</li>"
            "<li style='margin-bottom: 0px;'>" + tr("<b>4. 刷新并开始管理</b><br>点击管理器上的“刷新”按钮。就这样 —— 你现在可以随时启用、禁用并整理你的 MOD 了。") + "</li>"
            "</ol>"
            "<h4 style='margin: 14px 0 8px 0;'>" + tr("操作指南") + "</h4>"
            "<ul style='margin: 0; padding-left: 24px;'>"
            "<li style='margin-bottom: 10px;'>" + tr("<b>源MOD目录：</b>你的 MOD 管理文件夹，用于存放所有 MOD 文件（建议自行分类整理）。可点击“选择...”选择文件夹，或点击“打开”在资源管理器中打开。") + "</li>"
            "<li style='margin-bottom: 10px;'>" + tr("<b>目标MOD目录：</b>游戏读取 MOD 的目录，通常为 <code style='background-color: rgba(128, 128, 128, 0.2); padding: 2px 4px; border-radius: 4px;'>游戏文件夹/Game/Content/Paks/mods</code>。如果没有 mods 目录，需要手动创建。可点击“选择...”设置路径，或点击“打开”快速定位目录。") + "</li>"
            "<li style='margin-bottom: 10px;'>" + tr("<b>清空目标目录：</b>点击“清空目标目录”可从游戏 MOD 安装目录中移除所有已安装的 MOD。") + "</li>"
            "<li style='margin-bottom: 10px;'>" + tr("<b>免打扰模式：</b>开启后，会隐藏不包含 .pak 的无关项，让列表更清爽。") + "</li>"
            "<li style='margin-bottom: 10px;'>" + tr("<b>排序：</b>支持按名称/时间的升序与降序排序，并会尽量保留你当前展开的目录状态。") + "</li>"
            "<li style='margin-bottom: 10px;'>" + tr("<b>全部展开/全部收起：</b>若当前选中了某个目录，将只对该目录递归展开/收起；否则对整个列表展开/收起。") + "</li>"
            "<li style='margin-bottom: 10px;'>" + tr("<b>新建文件夹：</b>在左侧选中一个目录后点击“新建文件夹”，会在该目录下创建子目录；若选中的是文件，则在其同级创建；未选中任何项则默认在源MOD目录下创建。") + "</li>"
            "<li style='margin-bottom: 10px;'>" + tr("<b>启用/禁用：</b>勾选 .pak 文件后点击“启用/禁用”。支持勾选文件夹进行批量选择；也可<b>双击 .pak 文件</b>快速切换，或在列表上<b>右键</b>使用菜单快捷启用/禁用。") + "</li>"
            "<li style='margin-bottom: 10px;'>" + tr("<b>刷新：</b>当你新增/移动/删除 MOD 文件后，点击“刷新”重新读取源目录结构，并更新启用状态与预览信息。") + "</li>"
            "<li style='margin-bottom: 10px;'>" + tr("<b>记忆启用状态：</b>底部按钮栏可“记忆当前启用状态”保存一套启用/禁用配置；之后可从下拉框选择并“应用记忆”，也可“删除记忆”。") + "</li>"
            "<li style='margin-bottom: 10px;'>" + tr("<b>预览图操作：</b>右侧预览区支持拖拽本地图片、从网页拖拽图片/链接（自动下载并关联），也支持直接粘贴剪贴板图片。双击右侧预览图可用系统图片查看器打开；在左侧列表对图片文件右键可删除。") + "</li>"
            "<li style='margin-bottom: 10px;'>" + tr("<b>粘贴（Ctrl+V）：</b>在左侧选中目标目录（或任意文件），按 Ctrl+V 可将剪贴板中的文件/文件夹粘贴到该目录；支持资源管理器复制，也支持从系统 zip / WinRAR 复制（保留目录结构）。") + "</li>"
            "<li style='margin-bottom: 10px;'>" + tr("<b>打开文件：</b>双击文本/图片文件会调用系统默认程序打开查看内容。") + "</li>"
            "<li style='margin-bottom: 10px;'>" + tr("<b>表格调整：</b>可拖动列分隔线调整列宽，列宽会自动记忆。") + "</li>"
            "<li style='margin-bottom: 0px;'>" + tr("<b>语言：</b>右下角可切换界面语言。") + "</li>"
            "</ul>"
            "</div>"
        )

    def _get_expanded_paths(self) -> set:
        expanded_paths = set()
        if not self._tree_model or not self.tree_view.model():
            return expanded_paths
            
        def record_expanded(index: QModelIndex):
            if self.tree_view.isExpanded(index):
                node = index.internalPointer()
                if node:
                    expanded_paths.add(node.path)
                model = self.tree_view.model()
                for i in range(model.rowCount(index)):
                    child_idx = model.index(i, 0, index)
                    record_expanded(child_idx)
                    
        model = self.tree_view.model()
        for i in range(model.rowCount()):
            root_idx = model.index(i, 0)
            record_expanded(root_idx)
            
        return expanded_paths

    def _restore_expanded_paths(self, expanded_paths: set):
        if not expanded_paths or not self._tree_model or not self.tree_view.model():
            return
            
        def restore_expanded(index: QModelIndex):
            node = index.internalPointer()
            if node and node.path in expanded_paths:
                self.tree_view.expand(index)
            
            model = self.tree_view.model()
            for i in range(model.rowCount(index)):
                child_idx = model.index(i, 0, index)
                restore_expanded(child_idx)
                
        model = self.tree_view.model()
        for i in range(model.rowCount()):
            root_idx = model.index(i, 0)
            restore_expanded(root_idx)

    def _on_sort_changed(self, index: int):
        sort_mode = self.combo_sort.itemData(index)
        if sort_mode:
            self._current_sort_mode = sort_mode
            if self._tree_model:
                expanded_paths = self._get_expanded_paths()
                self._vm.set_sort_mode(sort_mode)
                self._restore_expanded_paths(expanded_paths)

    def _toggle_dnd_mode(self, checked: bool):
        self._dnd_mode_enabled = checked
        if checked:
            self.btn_dnd.setText(tr("免打扰：开"))
        else:
            self.btn_dnd.setText(tr("免打扰：关"))
            
        if self._tree_model:
            expanded_paths = self._get_expanded_paths()
            self._vm.set_dnd_mode(checked)
            self._restore_expanded_paths(expanded_paths)
            
    def _expand_all(self):
        sel_model = self.tree_view.selectionModel()
        if sel_model and sel_model.hasSelection():
            idx = sel_model.selectedRows()[0]
            node = idx.internalPointer()
            if getattr(node, 'is_dir', False):
                self.tree_view.expandRecursively(idx)
        else:
            self.tree_view.expandAll()

    def _collapse_all(self):
        sel_model = self.tree_view.selectionModel()
        if sel_model and sel_model.hasSelection():
            idx = sel_model.selectedRows()[0]
            node = idx.internalPointer()
            if getattr(node, 'is_dir', False):
                self._collapse_recursively(idx)
        else:
            self.tree_view.collapseAll()

    def _on_new_folder(self):
        self.source_dir = normalize_path(self.src_edit.text())
        if not self.source_dir or not os.path.isdir(self.source_dir):
            self._warn(tr("提示"), tr("请先设置有效的源MOD目录"))
            return
        sel_model = self.tree_view.selectionModel()
        if sel_model and sel_model.hasSelection():
            idx = sel_model.selectedRows()[0]
            node: FsNode = idx.internalPointer()
            if getattr(node, "is_dir", False):
                self._create_new_directory(node, False)
            else:
                self._create_new_directory(node, True)
            return
        root_node = FsNode(os.path.basename(self.source_dir) or self.source_dir, self.source_dir, True)
        self._create_new_directory(root_node, False)
            
    def _collapse_recursively(self, index: QModelIndex):
        self.tree_view.collapse(index)
        model = self.tree_view.model()
        for i in range(model.rowCount(index)):
            child_idx = model.index(i, 0, index)
            node = child_idx.internalPointer()
            if getattr(node, 'is_dir', False):
                self._collapse_recursively(child_idx)

    def _show_tree_context_menu(self, pos: QPoint):
        idx = self.tree_view.indexAt(pos)
        if not idx.isValid():
            return
            
        node: FsNode = idx.internalPointer()
        menu = QMenu(self.tree_view)

        if node.is_dir or node.is_pak:
            is_fully_enabled = False
            is_fully_disabled = False
            
            if node.is_pak:
                if node.pak_enabled:
                    is_fully_enabled = True
                else:
                    is_fully_disabled = True
            elif node.is_dir:
                if node.dir_state == "enabled":
                    is_fully_enabled = True
                elif node.dir_state is None:
                    is_fully_disabled = True
                    
            if is_fully_enabled:
                action_disable = menu.addAction(tr("禁用"))
                action_disable.triggered.connect(lambda: self._execute_node_action(node, "disable"))
            elif is_fully_disabled:
                action_enable = menu.addAction(tr("启用"))
                action_enable.triggered.connect(lambda: self._execute_node_action(node, "enable"))
            else:
                action_enable = menu.addAction(tr("启用"))
                action_enable.triggered.connect(lambda: self._execute_node_action(node, "enable"))
                action_disable = menu.addAction(tr("禁用"))
                action_disable.triggered.connect(lambda: self._execute_node_action(node, "disable"))

        # 原来的删除图片逻辑被通用的删除逻辑替代
        if node.path != self.source_dir:
            action_rename = menu.addAction(tr("重命名"))
            action_rename.triggered.connect(lambda: self._rename_node(node))

        # 新增目录逻辑
        menu.addSeparator()
        if node.path != self.source_dir:
            action_new_sibling = menu.addAction(tr("新增同级目录"))
            action_new_sibling.triggered.connect(lambda: self._create_new_directory(node, True))
            
        if getattr(node, 'is_dir', False):
            action_new_child = menu.addAction(tr("新增子目录"))
            action_new_child.triggered.connect(lambda: self._create_new_directory(node, False))

        if node.path != self.source_dir:
            menu.addSeparator()
            action_delete = menu.addAction(tr("删除"))
            action_delete.triggered.connect(lambda: self._delete_node(node))

        menu.exec(self.tree_view.viewport().mapToGlobal(pos))

    def _delete_node(self, node: FsNode):
        if node.path == self.source_dir:
            self._warn(tr("提示"), tr("无法删除源MOD根目录。"))
            return
            
        is_dir = node.is_dir
        type_str = tr("文件夹及其所有内容") if is_dir else tr("文件")
        
        if self._confirm_yes_no(
            tr("确认删除"),
            tr("确定要永久删除该{type_str}吗？此操作不可恢复！\n\n{node.name}").format(type_str=type_str, node=node),
            default_yes=False
        ):
            try:
                if is_dir:
                    shutil.rmtree(node.path, ignore_errors=True)
                else:
                    if os.path.isfile(node.path):
                        os.chmod(node.path, stat.S_IWRITE)
                        os.remove(node.path)
                    
                    # 如果当前正在预览该图片，清除预览
                    if hasattr(self, "_current_preview_path") and self._current_preview_path == node.path:
                        self.lbl_preview_img.setText(tr("可拖拽或粘贴图片到此处设置pak预览图。"))
                        self._current_preview_path = None
                        self._cached_full_pixmap = None

                self.refresh_source_tree()
            except Exception as e:
                self._error(tr("删除失败"), tr("删除失败：\n{e}").format(e=e))

    def _rename_node(self, node: FsNode):
        if node.path == self.source_dir:
            self._warn(tr("提示"), tr("无法重命名源MOD根目录。"))
            return
            
        old_name = node.name
        base_dir = os.path.dirname(node.path)
        
        new_name, ok = self._input_text(tr("重命名"), tr("请输入新名称："), old_name, QLineEdit.EchoMode.Normal)
        if not ok or not new_name.strip() or new_name.strip() == old_name:
            return
            
        new_name = new_name.strip()
        new_path = os.path.join(base_dir, new_name)
        
        if os.path.exists(new_path):
            if os.path.abspath(node.path).lower() != os.path.abspath(new_path).lower():
                self._warn(tr("错误"), tr("名称 '{new_name}' 已存在！").format(new_name=new_name))
                return
                
        try:
            os.rename(node.path, new_path)
            
            # 如果当前正在预览该图片，清除预览或更新路径
            if hasattr(self, "_current_preview_path") and self._current_preview_path == node.path:
                self._current_preview_path = new_path
                
            # 更新配置文件中相关的路径（包括备注和记忆状态）
            try:
                old_rel = os.path.relpath(node.path, self.source_dir)
                new_rel = os.path.relpath(new_path, self.source_dir)
                
                cfg = load_config()
                changed = False
                
                # 1. 更新备注
                comments = cfg.get("comments", {})
                new_comments = {}
                for p, c in comments.items():
                    if p == old_rel:
                        new_comments[new_rel] = c
                        changed = True
                    elif p.startswith(old_rel + os.sep):
                        new_p = new_rel + p[len(old_rel):]
                        new_comments[new_p] = c
                        changed = True
                    else:
                        new_comments[p] = c
                if changed:
                    cfg["comments"] = new_comments
                
                # 2. 更新记忆状态
                saved_states = cfg.get("saved_enabled_mods_dict", {})
                states_changed = False
                for state_name, paths in saved_states.items():
                    new_paths = []
                    for p in paths:
                        if p == old_rel:
                            new_paths.append(new_rel)
                            states_changed = True
                        elif p.startswith(old_rel + os.sep):
                            new_p = new_rel + p[len(old_rel):]
                            new_paths.append(new_p)
                            states_changed = True
                        else:
                            new_paths.append(p)
                    saved_states[state_name] = new_paths
                if states_changed:
                    cfg["saved_enabled_mods_dict"] = saved_states
                    changed = True
                    
                # 3. 更新旧版记忆状态
                legacy_saved = cfg.get("saved_enabled_mods")
                if legacy_saved:
                    new_legacy = []
                    legacy_changed = False
                    for p in legacy_saved:
                        if p == old_rel:
                            new_legacy.append(new_rel)
                            legacy_changed = True
                        elif p.startswith(old_rel + os.sep):
                            new_p = new_rel + p[len(old_rel):]
                            new_legacy.append(new_p)
                            legacy_changed = True
                        else:
                            new_legacy.append(p)
                    if legacy_changed:
                        cfg["saved_enabled_mods"] = new_legacy
                        changed = True
                        
                if changed:
                    save_config(cfg)
            except Exception:
                pass
                
            self.refresh_source_tree()
        except Exception as e:
            self._error(tr("重命名失败"), tr("无法重命名：\n{e}").format(e=e))

    def _create_new_directory(self, node: FsNode, is_sibling: bool):
        if is_sibling:
            # 如果是源MOD根目录，它的同级也是在上一层，但在这里通常不允许在源目录之外创建
            if node.path == self.source_dir:
                self._warn(tr("提示"), tr("无法在源MOD根目录的同级创建文件夹，请使用新增子目录。"))
                return
            base_dir = os.path.dirname(node.path)
        else:
            base_dir = node.path
            
        name, ok = self._input_text(tr("新建文件夹"), tr("请输入文件夹名称："))
        if not ok or not name.strip():
            return
            
        name = name.strip()
        new_dir_path = os.path.join(base_dir, name)
        
        if os.path.exists(new_dir_path):
            self._warn(tr("错误"), tr("文件夹或文件 '{name}' 已存在！").format(name=name))
            return
            
        try:
            os.makedirs(new_dir_path)
            self.refresh_source_tree()
        except Exception as e:
            self._error(tr("创建失败"), tr("无法创建文件夹：\n{e}").format(e=e))

    def _on_tree_double_click(self, index: QModelIndex):
        if not index.isValid():
            return
            
        node: FsNode = index.internalPointer()
        
        if index.column() == 3:
            old_comment = node.comment
            new_comment, ok = self._input_text(tr("编辑备注"), tr("请输入备注信息："), old_comment, QLineEdit.EchoMode.Normal)
            if ok and new_comment != old_comment:
                node.comment = new_comment
                if self._tree_model:
                    self._tree_model.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole])
                
                try:
                    rel_path = os.path.relpath(node.path, self.source_dir)
                    cfg = load_config()
                    comments = cfg.get("comments", {})
                    if new_comment:
                        comments[rel_path] = new_comment
                    else:
                        comments.pop(rel_path, None)
                    save_config({"comments": comments})
                except Exception:
                    pass
            return
            
        if not node.is_dir:
            ext = os.path.splitext(node.path)[1].lower()
            if ext in (".txt", ".md", ".png", ".jpg", ".jpeg", ".bmp", ".webp"):
                self._open_file_with_system(node.path)
                return
                
            if node.is_pak:
                if node.pak_enabled:
                    self._execute_node_action(node, "disable")
                else:
                    self._execute_node_action(node, "enable")

    def _on_preview_double_click(self):
        if hasattr(self, "_current_preview_path") and self._current_preview_path:
            self._open_file_with_system(self._current_preview_path)

    def _on_image_dropped(self, image_path: str):
        sel_model = self.tree_view.selectionModel()
        if not sel_model: return
        sel = sel_model.selectedIndexes()
        if not sel: return
        
        idx = [i for i in sel if i.column() == 0]
        if not idx: return
        
        node: FsNode = idx[0].internalPointer()
        if not node.is_pak:
            self._info(tr("提示"), tr("请先选中一个 .pak 文件，再拖拽图片进行关联。"))
            return
            
        pak_path = node.path
        pak_dir = os.path.dirname(pak_path)
        pak_name = os.path.splitext(os.path.basename(pak_path))[0]
        ext = os.path.splitext(image_path)[1].lower()
        target_path = os.path.join(pak_dir, f"{pak_name}{ext}")
        
        if os.path.abspath(image_path).lower() == os.path.abspath(target_path).lower():
            return

        self.lbl_preview_img.setText(tr("可拖拽或粘贴图片到此处设置pak预览图。"))
        if hasattr(self, "_cached_full_pixmap"):
            self._cached_full_pixmap = None

        exts = (".png", ".jpg", ".jpeg", ".bmp", ".webp")
        for e in exts:
            existing_candidate = os.path.join(pak_dir, pak_name + e)
            if os.path.isfile(existing_candidate):
                try:
                    os.chmod(existing_candidate, stat.S_IWRITE)
                    os.remove(existing_candidate)
                except Exception:
                    pass
                    
        try:
            shutil.copy2(image_path, target_path)
            node.preview_path = target_path
            self._set_side_preview(target_path, is_pak=True)
            
            pixmap = load_qpixmap(target_path, QSize(40, 40))
            if pixmap and not pixmap.isNull():
                self._tree_model.set_node_thumb(node, pixmap)
                
            self._tree_model.layoutChanged.emit()
        except Exception as e:
            self._error(tr("错误"), tr("保存预览图失败：\n{e}").format(e=e))

    def _on_image_url_dropped(self, url: str):
        tmp_path = None
        try:
            tmp_path, err = RemoteImageFetcher.fetch_to_temp(url)
            if err:
                self._error(tr("错误"), err)
                return
            if not tmp_path or not os.path.isfile(tmp_path):
                self._error(tr("错误"), tr("下载图片失败"))
                return
            self._on_image_dropped(tmp_path)
        finally:
            if tmp_path and os.path.isfile(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    def _on_image_pasted(self, image: QImage):
        sel_model = self.tree_view.selectionModel()
        if not sel_model: return
        sel = sel_model.selectedIndexes()
        if not sel: return
        
        idx = [i for i in sel if i.column() == 0]
        if not idx: return
        
        node: FsNode = idx[0].internalPointer()
        if not node.is_pak:
            self._info(tr("提示"), tr("请先选中一个 .pak 文件，再粘贴图片进行关联。"))
            return
            
        pak_path = node.path
        pak_dir = os.path.dirname(pak_path)
        pak_name = os.path.splitext(os.path.basename(pak_path))[0]
        ext = ".png"
        target_path = os.path.join(pak_dir, f"{pak_name}{ext}")
        
        self.lbl_preview_img.setText(tr("可拖拽或粘贴图片到此处设置pak预览图。"))
        if hasattr(self, "_cached_full_pixmap"):
            self._cached_full_pixmap = None

        exts = (".png", ".jpg", ".jpeg", ".bmp", ".webp")
        for e in exts:
            existing_candidate = os.path.join(pak_dir, pak_name + e)
            if os.path.isfile(existing_candidate):
                try:
                    os.chmod(existing_candidate, stat.S_IWRITE)
                    os.remove(existing_candidate)
                except Exception:
                    pass
                    
        try:
            image.save(target_path, "PNG")
            node.preview_path = target_path
            self._set_side_preview(target_path, is_pak=True)
            
            pixmap = load_qpixmap(target_path, QSize(40, 40))
            if pixmap and not pixmap.isNull():
                self._tree_model.set_node_thumb(node, pixmap)
                
            self._tree_model.layoutChanged.emit()
        except Exception as e:
            self._error(tr("错误"), tr("保存粘贴的预览图失败：\n{e}").format(e=e))

    def _on_tree_paste(self):
        sel_model = self.tree_view.selectionModel()
        if not sel_model: return
        sel = sel_model.selectedIndexes()
        if not sel: return
        
        idx = [i for i in sel if i.column() == 0]
        if not idx: return
        
        node: FsNode = idx[0].internalPointer()
        if node.is_dir:
            target_dir = node.path
        else:
            target_dir = os.path.dirname(node.path)
            
        clipboard = QApplication.clipboard()
        copied, errors = ClipboardFilePasteHelper.paste_to_directory(target_dir, clipboard.mimeData())
                        
        if copied > 0 or errors:
            if errors:
                self._warn("粘贴完成（有错误）", f"成功粘贴 {copied} 个项，失败 {len(errors)} 个:\n" + "\n".join(errors[:10]))
                
            self.refresh_source_tree()

    def _open_file_with_system(self, path: str):
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", path])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            pass

    def _execute_node_action(self, node: FsNode, action: str):
        original_states = {}
        def save_states(n: FsNode):
            original_states[n] = n.checked
            for c in n.children:
                save_states(c)
        
        if self._tree_model:
            save_states(self._tree_model._root)
            
        def uncheck_all(n: FsNode):
            n.checked = False
            for c in n.children:
                uncheck_all(c)
                
        if self._tree_model:
            uncheck_all(self._tree_model._root)
            
        node.checked = True
        
        if action == "enable":
            self._enable_checked()
        elif action == "disable":
            self._disable_checked()
            
        def restore_states(n: FsNode):
            n.checked = original_states.get(n, False)
            for c in n.children:
                restore_states(c)
                
        if self._tree_model:
            restore_states(self._tree_model._root)
            
        if self._tree_model:
            self._tree_model.dataChanged.emit(
                self._tree_model.index(0, 0),
                self._tree_model.index(self._tree_model.rowCount()-1, 0),
                [Qt.ItemDataRole.CheckStateRole]
            )

    def _get_checked_nodes(self, node: FsNode, out: list[FsNode]):
        if node.checked and (node.is_dir or node.is_pak):
            out.append(node)
        for c in node.children:
            self._get_checked_nodes(c, out)

    def _enable_checked(self):
        self.source_dir = normalize_path(self.src_edit.text())
        self.target_dir = normalize_path(self.tgt_edit.text())
        if not self.source_dir or not os.path.isdir(self.source_dir):
            self._warn(tr("提示"), tr("请先设置有效的源MOD目录"))
            return
        if not self.target_dir:
            self._warn(tr("提示"), "请先设置目标MOD目录")
            return
        
        if not self._tree_model:
            return
            
        checked_nodes = []
        self._get_checked_nodes(self._tree_model._root, checked_nodes)
        
        if not checked_nodes:
            self._info(tr("提示"), "请先勾选要启用的目录或.pak")
            return
            
        checked_paths = [n.path for n in checked_nodes]
        dirs = sorted([p for p in checked_paths if os.path.isdir(p)], key=lambda s: len(s))
        paks = [p for p in checked_paths if is_pak_file(p)]
        
        def is_within(child: str, parent: str) -> bool:
            try:
                return normalize_path(os.path.commonpath([child, parent])) == normalize_path(parent)
            except Exception:
                return False

        top_dirs = []
        for d in dirs:
            if any(is_within(d, td) for td in top_dirs):
                continue
            top_dirs.append(d)
        paks = [p for p in paks if not any(is_within(p, d) for d in top_dirs)]
        
        os.makedirs(self.target_dir, exist_ok=True)
        copied = 0
        errors = []
        
        def copy_pak(src: str):
            nonlocal copied
            try:
                rel = os.path.relpath(src, self.source_dir)
                dst = normalize_path(os.path.join(self.target_dir, rel))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                copied += 1
            except Exception as e:
                errors.append(f"{os.path.basename(src)}: {e}")
                
        for d in top_dirs:
            for root, _, filenames in os.walk(d):
                for fn in filenames:
                    if fn.lower().endswith(".pak"):
                        copy_pak(os.path.join(root, fn))
                        
        for p in paks:
            copy_pak(p)
            
        self._vm.update_enabled_marks()
        if errors:
            self._warn("启用完成（有失败）", "\n".join(errors[:20]))

    def _disable_checked(self):
        self.source_dir = normalize_path(self.src_edit.text())
        self.target_dir = normalize_path(self.tgt_edit.text())
        if not self.source_dir or not os.path.isdir(self.source_dir):
            return
        if not self.target_dir or not os.path.isdir(self.target_dir):
            return
            
        if not self._tree_model:
            return
            
        checked_nodes = []
        self._get_checked_nodes(self._tree_model._root, checked_nodes)
        if not checked_nodes:
            self._info(tr("提示"), "请先勾选要禁用的目录或.pak")
            return
            
        checked_paths = [n.path for n in checked_nodes]
        dirs = sorted([p for p in checked_paths if os.path.isdir(p)], key=lambda s: len(s))
        paks = [p for p in checked_paths if is_pak_file(p)]
        
        def is_within(child: str, parent: str) -> bool:
            try:
                return normalize_path(os.path.commonpath([child, parent])) == normalize_path(parent)
            except Exception:
                return False

        top_dirs = []
        for d in dirs:
            if any(is_within(d, td) for td in top_dirs):
                continue
            top_dirs.append(d)
        paks = [p for p in paks if not any(is_within(p, d) for d in top_dirs)]
        
        removed = 0
        errors = []
        
        def prune_empty(start_dir: str):
            cur = normalize_path(start_dir)
            stop = normalize_path(self.target_dir)
            while cur and cur != stop:
                try:
                    if not os.listdir(cur):
                        os.rmdir(cur)
                    else:
                        break
                except Exception:
                    break
                cur = normalize_path(os.path.dirname(cur))

        def remove_pak(src: str):
            nonlocal removed
            try:
                rel = os.path.relpath(src, self.source_dir)
                dst = normalize_path(os.path.join(self.target_dir, rel))
                if os.path.isfile(dst):
                    os.remove(dst)
                    removed += 1
                    prune_empty(os.path.dirname(dst))
            except Exception as e:
                errors.append(f"{os.path.basename(src)}: {e}")
                
        for d in top_dirs:
            try:
                rel_dir = os.path.relpath(d, self.source_dir)
                dst_dir = normalize_path(os.path.join(self.target_dir, rel_dir))
                if os.path.isdir(dst_dir):
                    for root, _, filenames in os.walk(dst_dir, topdown=False):
                        for fn in filenames:
                            if fn.lower().endswith(".pak"):
                                try:
                                    os.remove(os.path.join(root, fn))
                                    removed += 1
                                except Exception as e:
                                    errors.append(f"{fn}: {e}")
                        try:
                            if not os.listdir(root):
                                os.rmdir(root)
                        except Exception:
                            pass
                    prune_empty(os.path.dirname(dst_dir))
            except Exception as e:
                errors.append(f"{os.path.basename(d)}: {e}")
                
        for p in paks:
            remove_pak(p)
            
        self._vm.update_enabled_marks()
        if errors:
            self._warn("禁用完成（有失败）", "\n".join(errors[:20]))

    def _refresh_saved_states_combo(self):
        cfg = load_config()
        saved_states = cfg.get("saved_enabled_mods_dict", {})
        if not isinstance(saved_states, dict):
            saved_states = {}
            
        old_saved = cfg.get("saved_enabled_mods")
        if old_saved and "default" not in saved_states:
            saved_states["default"] = old_saved
            
        self.combo_saved_states.clear()
        names = list(saved_states.keys())
        if names:
            self.combo_saved_states.addItems(names)
        else:
            self.combo_saved_states.addItem("无")
            self.combo_saved_states.setEnabled(False)
            return
            
        self.combo_saved_states.setEnabled(True)

    def _save_enabled_state(self):
        if not self._tree_model:
            self._warn(tr("提示"), "请先加载源MOD目录")
            return
            
        cfg = load_config()
        saved_states = cfg.get("saved_enabled_mods_dict", {})
        if not isinstance(saved_states, dict):
            saved_states = {}
            
        # 兼容旧版本的数据，如果存在则将其合并到 "default" 中
        old_saved = cfg.get("saved_enabled_mods")
        if old_saved and "default" not in saved_states:
            saved_states["default"] = old_saved

        if self.combo_saved_states.isEnabled() and self.combo_saved_states.currentText() != "无":
            current_name = self.combo_saved_states.currentText()
            msgBox = QMessageBox(self)
            msgBox.setWindowTitle(tr("保存记忆"))
            msgBox.setText(tr("您要覆盖当前选中的记忆，还是创建新的记忆？\n当前选中：") + current_name)
            msgBox.setIcon(QMessageBox.Icon.Question)
            
            btn_overwrite = msgBox.addButton(tr("覆盖当前"), QMessageBox.ButtonRole.AcceptRole)
            btn_new = msgBox.addButton(tr("新建记忆"), QMessageBox.ButtonRole.ActionRole)
            btn_cancel = msgBox.addButton(tr("取消"), QMessageBox.ButtonRole.RejectRole)
            
            msgBox.exec()
            
            clicked_btn = msgBox.clickedButton()
            if clicked_btn == btn_cancel:
                return
            elif clicked_btn == btn_overwrite:
                name = current_name
            else: # btn_new
                name, ok = self._input_text(tr("新建记忆"), tr("请输入要保存的记忆名称："))
                if not ok or not name.strip():
                    return
                name = name.strip()
        else:
            name, ok = self._input_text(tr("保存记忆"), tr("请输入要保存的记忆名称："))
            if not ok or not name.strip():
                return
            name = name.strip()
        
        enabled_paks = []
        def walk(node: FsNode):
            if node.is_pak and node.pak_enabled:
                try:
                    rel = os.path.relpath(node.path, self.source_dir)
                    enabled_paks.append(rel)
                except Exception:
                    pass
            for c in node.children:
                walk(c)
        walk(self._tree_model._root)
        
        # 如果是新建或者用户手输的名字与已有的冲突，仍然做一次覆盖确认
        if name in saved_states and (not self.combo_saved_states.isEnabled() or name != self.combo_saved_states.currentText() or clicked_btn == btn_new):
            if not self._confirm_yes_no(
                tr("确认覆盖"),
                tr("记忆名称 '{name}' 已存在，是否覆盖？").format(name=name),
                default_yes=False
            ):
                return
                
        saved_states[name] = enabled_paks
        
        save_config({"saved_enabled_mods_dict": saved_states})
        self._refresh_saved_states_combo()
        
        # 选中刚刚保存的记忆
        index = self.combo_saved_states.findText(name)
        if index >= 0:
            self.combo_saved_states.setCurrentIndex(index)
            
        self._info(tr("记忆成功"), tr("成功记住了 {count} 个启用的MOD。\n已保存为：{name}").format(count=len(enabled_paks), name=name))

    def _apply_saved_state(self):
        if not self.source_dir or not os.path.isdir(self.source_dir):
            self._warn(tr("提示"), tr("请先设置有效的源MOD目录"))
            return
        if not self.target_dir:
            self._warn(tr("提示"), "请先设置目标MOD目录")
            return
            
        if not self.combo_saved_states.isEnabled():
            self._info(tr("提示"), "未找到已记忆的MOD状态。请先点击“记忆当前启用状态”。")
            return
            
        name = self.combo_saved_states.currentText()
        if not name or name == "无":
            return
            
        cfg = load_config()
        saved_states = cfg.get("saved_enabled_mods_dict", {})
        if not isinstance(saved_states, dict):
            saved_states = {}
            
        old_saved = cfg.get("saved_enabled_mods")
        if old_saved and "default" not in saved_states:
            saved_states["default"] = old_saved
            
        saved_paks = saved_states.get(name, [])
        if not saved_paks:
            self._info(tr("提示"), f"记忆 '{name}' 为空。")
            return
            
        if not self._confirm_yes_no(
            "确认应用",
            f"将要应用记忆 '{name}' 中的 {len(saved_paks)} 个MOD状态。\n建议在应用前先“清空目标目录”，是否继续？",
            default_yes=True
        ):
            return
            
        os.makedirs(self.target_dir, exist_ok=True)
        copied = 0
        errors = []
        
        for rel_path in saved_paks:
            src = normalize_path(os.path.join(self.source_dir, rel_path))
            if is_pak_file(src):
                try:
                    dst = normalize_path(os.path.join(self.target_dir, rel_path))
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
                    copied += 1
                except Exception as e:
                    errors.append(f"{os.path.basename(src)}: {e}")
                    
        self._vm.update_enabled_marks()
        if errors:
            self._warn("应用完成（有失败）", "\n".join(errors[:20]))
        else:
            self._info("应用成功", f"成功应用了记忆 '{name}' 中的 {copied} 个MOD。")

    def _delete_saved_state(self):
        if not self.combo_saved_states.isEnabled():
            self._info(tr("提示"), "未找到已记忆的MOD状态。")
            return
            
        name = self.combo_saved_states.currentText()
        if not name or name == "无":
            return
            
        if not self._confirm_yes_no(
            tr("确认删除"),
            f"确定要删除记忆 '{name}' 吗？\n删除后将无法通过该名称恢复状态。",
            default_yes=False
        ):
            return
            
        cfg = load_config()
        saved_states = cfg.get("saved_enabled_mods_dict", {})
        if not isinstance(saved_states, dict):
            saved_states = {}
            
        if name in saved_states:
            del saved_states[name]
            save_config({"saved_enabled_mods_dict": saved_states})
            
            # 如果删除了 default，也要把旧版的 saved_enabled_mods 删掉以防重新加载
            if name == "default" and "saved_enabled_mods" in cfg:
                del cfg["saved_enabled_mods"]
                save_config({"saved_enabled_mods": None})
                
            self._refresh_saved_states_combo()
        else:
            self._warn(tr("错误"), f"找不到名为 '{name}' 的记忆。")

    def _clear_target_directory(self):
        if not self.target_dir or not os.path.isdir(self.target_dir):
            self._info(tr("提示"), "目标MOD目录不存在或为空。")
            return
            
        if not self._confirm_yes_no(
            "确认清空",
            f"确定要清空目标MOD目录吗？\n所有已启用的MOD将被禁用！\n目标目录：\n{self.target_dir}",
            default_yes=False
        ):
            return
            
        removed = 0
        errors = []
        
        for root, dirs, files in os.walk(self.target_dir, topdown=False):
            for name in files:
                try:
                    filepath = os.path.join(root, name)
                    os.chmod(filepath, stat.S_IWRITE)
                    os.remove(filepath)
                    if name.lower().endswith(".pak"):
                        removed += 1
                except Exception as e:
                    errors.append(f"{name}: {e}")
            for name in dirs:
                try:
                    os.rmdir(os.path.join(root, name))
                except Exception:
                    pass
                    
        self._vm.update_enabled_marks()
        
        if errors:
            self._warn("清空完成（有失败）", "部分文件无法删除，可能被占用：\n" + "\n".join(errors[:20]))
        else:
            self._info("清空成功", "目标MOD目录已清空，所有MOD已恢复为禁用状态。")

