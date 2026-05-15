import os
from typing import Optional

from PyQt6.QtCore import Qt, QAbstractItemModel, QModelIndex, QSize, QTimer
from PyQt6.QtGui import QColor, QPixmap, QPainter, QIcon, QFont, QPen
from PyQt6.QtWidgets import QApplication, QStyle, QStyledItemDelegate, QStyleOptionViewItem

from utils import is_pak_file, find_preview_image_for_pak
from i18n import tr

class FsNode:
    def __init__(self, name: str, path: str, is_dir: bool, parent: Optional["FsNode"] = None, mtime: float = 0.0):
        self.name = name
        self.path = path
        self.is_dir = is_dir
        self.parent = parent
        self.mtime = mtime
        self.children: list["FsNode"] = []
        
        # UI State
        self.checked = False
        self._check_state = Qt.CheckState.Unchecked
        self.is_pak = (not is_dir) and is_pak_file(path)
        self.preview_path = find_preview_image_for_pak(path) if self.is_pak else None
        self.thumb_pixmap: Optional[QPixmap] = None
        self.comment: str = ""
        
        # Computed State
        self.pak_enabled = False
        self.link_mode: Optional[str] = None  # "link", "copy", or None
        self.dir_state: Optional[str] = None  # "enabled", "partial", None

    def row(self) -> int:
        if self.parent:
            try:
                # We need to return row in original children to not break row() when filtered
                return self.parent.children.index(self)
            except ValueError:
                return 0
        return 0

class FsTreeModel(QAbstractItemModel):
    def __init__(self, root_node: FsNode, parent=None):
        super().__init__(parent)
        self._root = root_node
        self._headers = [tr("名称"), tr("预览"), tr("状态"), tr("备注")]
        self._sort_mode = "name_asc" # default sort mode
        self._dnd_mode = False
        self._pak_icon: Optional[QIcon] = None
        self._thumb_dirty_rows: dict[FsNode, set[int]] = {}
        self._thumb_flush_timer = QTimer(self)
        self._thumb_flush_timer.setSingleShot(True)
        self._thumb_flush_timer.timeout.connect(self._flush_thumb_updates)
        self._sort_tree(self._root)
        self._rebuild_all_dir_check_states()

    def _get_pak_icon(self) -> QIcon:
        if self._pak_icon is not None:
            return self._pak_icon
        size = 16
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = pixmap.rect().adjusted(1, 1, -1, -1)
        painter.setPen(QPen(QColor("#4a148c")))
        painter.setBrush(QColor("#7b1fa2"))
        painter.drawRoundedRect(rect, 3, 3)
        font = QFont()
        font.setBold(True)
        font.setPixelSize(11)
        painter.setFont(font)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), "M")
        painter.end()
        self._pak_icon = QIcon(pixmap)
        return self._pak_icon

    def retranslate(self):
        self._headers = [tr("名称"), tr("预览"), tr("状态"), tr("备注")]
        self.headerDataChanged.emit(Qt.Orientation.Horizontal, 0, len(self._headers) - 1)
        self.beginResetModel()
        self.endResetModel()

    def set_sort_mode(self, mode: str):
        if self._sort_mode != mode:
            self._sort_mode = mode
            self._sort_tree(self._root)
            self.apply_filter(self._dnd_mode)

    def _sort_tree(self, node: FsNode):
        if self._sort_mode == "name_asc":
            node.children.sort(key=lambda n: (not n.is_dir, n.name.casefold()))
        elif self._sort_mode == "name_desc":
            node.children.sort(key=lambda n: n.name.casefold(), reverse=True)
            node.children.sort(key=lambda n: not n.is_dir)
        elif self._sort_mode == "mtime_desc":
            node.children.sort(key=lambda n: (not n.is_dir, -n.mtime, n.name.casefold()))
        elif self._sort_mode == "mtime_asc":
            node.children.sort(key=lambda n: (not n.is_dir, n.mtime, n.name.casefold()))
            
        if hasattr(node, "_filtered_children"):
            if self._sort_mode == "name_asc":
                node._filtered_children.sort(key=lambda n: (not n.is_dir, n.name.casefold()))
            elif self._sort_mode == "name_desc":
                node._filtered_children.sort(key=lambda n: n.name.casefold(), reverse=True)
                node._filtered_children.sort(key=lambda n: not n.is_dir)
            elif self._sort_mode == "mtime_desc":
                node._filtered_children.sort(key=lambda n: (not n.is_dir, -n.mtime, n.name.casefold()))
            elif self._sort_mode == "mtime_asc":
                node._filtered_children.sort(key=lambda n: (not n.is_dir, n.mtime, n.name.casefold()))

        for c in node.children:
            self._sort_tree(c)

    def headerData(self, section, orientation, role):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if 0 <= section < len(self._headers):
                return self._headers[section]
        return None

    def columnCount(self, parent=QModelIndex()):
        return len(self._headers)

    def rowCount(self, parent=QModelIndex()):
        if parent.column() > 0:
            return 0
        if not parent.isValid():
            node = self._root
        else:
            node = parent.internalPointer()
            
        return len(getattr(node, "_filtered_children", node.children))

    def index(self, row, column, parent=QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        if not parent.isValid():
            parent_node = self._root
        else:
            parent_node = parent.internalPointer()
        
        children = getattr(parent_node, "_filtered_children", parent_node.children)
        if 0 <= row < len(children):
            return self.createIndex(row, column, children[row])
        return QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()
        child_node = index.internalPointer()
        parent_node = child_node.parent
        if parent_node is None or parent_node == self._root:
            return QModelIndex()
        
        grandparent = parent_node.parent
        if grandparent:
            gp_children = getattr(grandparent, "_filtered_children", grandparent.children)
            try:
                row = gp_children.index(parent_node)
            except ValueError:
                row = 0
        else:
            row = 0
            
        return self.createIndex(row, 0, parent_node)

    def apply_filter(self, dnd_mode: bool):
        self._dnd_mode = dnd_mode
        def filter_node(node: FsNode) -> bool:
            if not dnd_mode:
                if hasattr(node, "_filtered_children"):
                    del node._filtered_children
                for c in node.children:
                    filter_node(c)
                return True
                
            filtered = []
            has_pak_descendant = False
            
            for c in node.children:
                if c.is_pak:
                    filtered.append(c)
                    has_pak_descendant = True
                elif c.is_dir:
                    # 对于目录，即使 filter_node 返回 False（即没有包含 pak 文件），我们也将其保留
                    filter_node(c)
                    filtered.append(c)
                    has_pak_descendant = True
                        
            node._filtered_children = filtered
            return has_pak_descendant
            
        self.beginResetModel()
        filter_node(self._root)
        self._rebuild_all_dir_check_states()
        self.endResetModel()

    def data(self, index, role):
        if not index.isValid():
            return None
        node: FsNode = index.internalPointer()
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return node.name
            elif col == 2:
                if node.is_pak:
                    if node.pak_enabled:
                        if node.link_mode == "link":
                            return tr("已启用 · 链接")
                        elif node.link_mode == "copy":
                            return tr("已启用 · 拷贝")
                        return tr("已启用")
                    return ""
                else:
                    if node.dir_state == "enabled":
                        return tr("已启用")
                    elif node.dir_state == "partial":
                        return tr("部分启用")
                    return ""
            elif col == 3:
                return node.comment
        elif role == Qt.ItemDataRole.DecorationRole and col == 0:
            if node.is_dir:
                return QApplication.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)
            if node.is_pak:
                return self._get_pak_icon()
            return None
        elif role == Qt.ItemDataRole.CheckStateRole and col == 0:
            if node.is_pak:
                return Qt.CheckState.Checked if node.checked else Qt.CheckState.Unchecked
            if node.is_dir:
                return getattr(node, "_check_state", Qt.CheckState.Checked if node.checked else Qt.CheckState.Unchecked)
            return None
        elif role == Qt.ItemDataRole.ForegroundRole and col == 2:
            if node.is_pak and node.pak_enabled:
                return QColor("#2e7d32")
            if not node.is_pak:
                if node.dir_state == "enabled":
                    return QColor("#2e7d32")
                elif node.dir_state == "partial":
                    return QColor("#ef6c00")
        elif role == Qt.ItemDataRole.UserRole:
            return node

        return None

    def setData(self, index, value, role):
        if not index.isValid():
            return False
        node: FsNode = index.internalPointer()
        if role == Qt.ItemDataRole.CheckStateRole and index.column() == 0:
            if node.is_dir or node.is_pak:
                try:
                    v = Qt.CheckState(value)
                except Exception:
                    try:
                        v = Qt.CheckState(int(value))
                    except Exception:
                        v = Qt.CheckState.Unchecked

                target_checked = v != Qt.CheckState.Unchecked

                if node.is_pak:
                    node.checked = target_checked
                    node._check_state = Qt.CheckState.Checked if target_checked else Qt.CheckState.Unchecked
                    self._update_parent_checked_states(node.parent)
                elif node.is_dir:
                    node.checked = target_checked
                    node._check_state = Qt.CheckState.Checked if target_checked else Qt.CheckState.Unchecked
                    self._set_descendants_checked(node, target_checked)
                    self._update_parent_checked_states(node.parent)

                self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
                self.layoutChanged.emit()
                return True
        return False

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        node: FsNode = index.internalPointer()
        default_flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.column() == 0 and (node.is_dir or node.is_pak):
            default_flags |= Qt.ItemFlag.ItemIsUserCheckable
            if node.is_dir:
                tristate_flag = getattr(Qt.ItemFlag, "ItemIsAutoTristate", None) or getattr(Qt.ItemFlag, "ItemIsTristate", None)
                if tristate_flag is not None:
                    default_flags |= tristate_flag
        return default_flags

    def _compute_dir_check_state(self, node: FsNode) -> Qt.CheckState:
        return self._compute_dir_check_state_from_children(node)

    def _child_check_state(self, node: FsNode) -> Qt.CheckState:
        if node.is_pak:
            return Qt.CheckState.Checked if node.checked else Qt.CheckState.Unchecked
        if node.is_dir:
            return getattr(node, "_check_state", Qt.CheckState.Checked if node.checked else Qt.CheckState.Unchecked)
        return Qt.CheckState.Unchecked

    def _compute_dir_check_state_from_children(self, node: FsNode) -> Qt.CheckState:
        children = getattr(node, "_filtered_children", node.children)
        has_any = False
        all_checked = True
        all_unchecked = True
        for c in children:
            if not (c.is_dir or c.is_pak):
                continue
            has_any = True
            s = self._child_check_state(c)
            if s != Qt.CheckState.Checked:
                all_checked = False
            if s != Qt.CheckState.Unchecked:
                all_unchecked = False
            if not all_checked and not all_unchecked:
                return Qt.CheckState.PartiallyChecked
        if not has_any:
            return Qt.CheckState.Unchecked
        if all_checked:
            return Qt.CheckState.Checked
        if all_unchecked:
            return Qt.CheckState.Unchecked
        return Qt.CheckState.PartiallyChecked

    def _rebuild_all_dir_check_states(self) -> None:
        def walk(n: FsNode) -> Qt.CheckState:
            if n.is_pak:
                n._check_state = Qt.CheckState.Checked if n.checked else Qt.CheckState.Unchecked
                return n._check_state
            if n.is_dir:
                for c in n.children:
                    walk(c)
                state = self._compute_dir_check_state_from_children(n)
                n._check_state = state
                n.checked = (state == Qt.CheckState.Checked)
                return state
            n._check_state = Qt.CheckState.Unchecked
            return n._check_state
        walk(self._root)

    def _set_descendants_checked(self, node: FsNode, checked: bool) -> None:
        for c in node.children:
            if c.is_dir or c.is_pak:
                c.checked = checked
                c._check_state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
                if c.is_dir and c.children:
                    self._set_descendants_checked(c, checked)

    def _update_parent_checked_states(self, node: Optional[FsNode]) -> None:
        cur = node
        while cur is not None and cur != self._root:
            if cur.is_dir:
                state = self._compute_dir_check_state_from_children(cur)
                cur._check_state = state
                cur.checked = (state == Qt.CheckState.Checked)
            cur = cur.parent

    def set_node_thumb(self, node: FsNode, pixmap: QPixmap):
        node.thumb_pixmap = pixmap
        if not node.parent:
            return
        parent = node.parent
        children = getattr(parent, "_filtered_children", parent.children)
        try:
            row = children.index(node)
        except ValueError:
            return
        rows = self._thumb_dirty_rows.get(parent)
        if rows is None:
            rows = set()
            self._thumb_dirty_rows[parent] = rows
        rows.add(row)
        if not self._thumb_flush_timer.isActive():
            self._thumb_flush_timer.start(33)

    def _flush_thumb_updates(self) -> None:
        if not self._thumb_dirty_rows:
            return
        pending = self._thumb_dirty_rows
        self._thumb_dirty_rows = {}

        for parent, rows in pending.items():
            children = getattr(parent, "_filtered_children", parent.children)
            if not children:
                continue
            valid_rows = [r for r in rows if 0 <= r < len(children)]
            if not valid_rows:
                continue
            valid_rows.sort()

            start = valid_rows[0]
            end = start
            for r in valid_rows[1:]:
                if r == end + 1:
                    end = r
                    continue
                idx1 = self.createIndex(start, 1, children[start])
                idx2 = self.createIndex(end, 1, children[end])
                self.dataChanged.emit(idx1, idx2, [Qt.ItemDataRole.DecorationRole])
                start = r
                end = r

            idx1 = self.createIndex(start, 1, children[start])
            idx2 = self.createIndex(end, 1, children[end])
            self.dataChanged.emit(idx1, idx2, [Qt.ItemDataRole.DecorationRole])

    def refresh_state_ui(self):
        self.dataChanged.emit(self.index(0, 2), self.index(self.rowCount()-1, 2), [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ForegroundRole])

class TreeItemDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        # 绘制通用的 Hover 背景层 (未选中时)
        if option.state & QStyle.StateFlag.State_MouseOver and not (option.state & QStyle.StateFlag.State_Selected):
            painter.fillRect(option.rect, QColor(128, 128, 128, 30))

        col = index.column()
        if col == 1:
            node: FsNode = index.internalPointer()
            if node.thumb_pixmap and not node.thumb_pixmap.isNull():
                painter.save()
                if option.state & QStyle.StateFlag.State_Selected:
                    painter.fillRect(option.rect, option.palette.highlight())
                
                rect = option.rect
                img_w = node.thumb_pixmap.width()
                img_h = node.thumb_pixmap.height()
                x = rect.x() + (rect.width() - img_w) // 2
                y = rect.y() + (rect.height() - img_h) // 2
                painter.drawPixmap(x, y, node.thumb_pixmap)
                painter.restore()
                return
        
        # 移除 option 中的 Hover 状态，避免部分系统默认样式重复绘制导致冲突
        opt = QStyleOptionViewItem(option)
        opt.state &= ~QStyle.StateFlag.State_MouseOver
        super().paint(painter, opt, index)

        if col == 0:
            state = index.data(Qt.ItemDataRole.CheckStateRole)
            if state == Qt.CheckState.Checked:
                opt2 = QStyleOptionViewItem(option)
                self.initStyleOption(opt2, index)
                opt2.state &= ~QStyle.StateFlag.State_MouseOver

                widget = opt2.widget or self.parent()
                style = widget.style() if widget else QApplication.style()
                indicator = style.subElementRect(QStyle.SubElement.SE_ItemViewItemCheckIndicator, opt2, widget)
                indicator = indicator.adjusted(2, 2, -2, -2)
                if indicator.isValid() and indicator.width() > 0 and indicator.height() > 0:
                    painter.save()
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                    pen = painter.pen()
                    pen.setColor(QColor("#FFFFFF"))
                    pen.setWidth(2)
                    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    painter.setPen(pen)

                    x1 = int(indicator.left() + indicator.width() * 0.20)
                    y1 = int(indicator.top() + indicator.height() * 0.55)
                    x2 = int(indicator.left() + indicator.width() * 0.42)
                    y2 = int(indicator.top() + indicator.height() * 0.78)
                    x3 = int(indicator.left() + indicator.width() * 0.80)
                    y3 = int(indicator.top() + indicator.height() * 0.25)

                    painter.drawLine(x1, y1, x2, y2)
                    painter.drawLine(x2, y2, x3, y3)
                    painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex):
        size = super().sizeHint(option, index)
        return QSize(size.width(), 42)
