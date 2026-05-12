import re

def main():
    with open("ui.py", "r", encoding="utf-8") as f:
        content = f.read()
        
    replacements = [
        # Top layout
        ("top_layout.addWidget(QLabel(tr(\"源MOD目录：\")))", 
         "self.lbl_src = QLabel(tr(\"源MOD目录：\"))\n        top_layout.addWidget(self.lbl_src)"),
        ("btn_src = QPushButton(tr(\"选择...\"))", "self.btn_src = QPushButton(tr(\"选择...\"))"),
        ("btn_src.", "self.btn_src."),
        ("top_layout.addWidget(btn_src)", "top_layout.addWidget(self.btn_src)"),
        
        ("top_layout.addWidget(QLabel(tr(\"目标MOD目录：\")))", 
         "self.lbl_tgt = QLabel(tr(\"目标MOD目录：\"))\n        top_layout.addWidget(self.lbl_tgt)"),
        ("btn_tgt = QPushButton(tr(\"选择...\"))", "self.btn_tgt = QPushButton(tr(\"选择...\"))"),
        ("btn_tgt.", "self.btn_tgt."),
        ("top_layout.addWidget(btn_tgt)", "top_layout.addWidget(self.btn_tgt)"),
        
        ("btn_clear_target = QPushButton(tr(\"清空目标目录\"))", "self.btn_clear_target = QPushButton(tr(\"清空目标目录\"))"),
        ("btn_clear_target.", "self.btn_clear_target."),
        ("top_layout.addWidget(btn_clear_target)", "top_layout.addWidget(self.btn_clear_target)"),
        
        # Left Top
        ("left_top.addWidget(QLabel(tr(\"源MOD目录结构\")))",
         "self.lbl_src_struct = QLabel(tr(\"源MOD目录结构\"))\n        left_top.addWidget(self.lbl_src_struct)"),
        
        ("btn_expand = QPushButton(tr(\"全部展开\"))", "self.btn_expand = QPushButton(tr(\"全部展开\"))"),
        ("btn_expand.", "self.btn_expand."),
        ("left_top.addWidget(btn_expand)", "left_top.addWidget(self.btn_expand)"),
        
        ("btn_collapse = QPushButton(tr(\"全部收起\"))", "self.btn_collapse = QPushButton(tr(\"全部收起\"))"),
        ("btn_collapse.", "self.btn_collapse."),
        ("left_top.addWidget(btn_collapse)", "left_top.addWidget(self.btn_collapse)"),
        
        ("btn_disable = QPushButton(tr(\"禁用\"))", "self.btn_disable = QPushButton(tr(\"禁用\"))"),
        ("btn_disable.", "self.btn_disable."),
        ("left_top.addWidget(btn_disable)", "left_top.addWidget(self.btn_disable)"),
        
        ("btn_enable = QPushButton(tr(\"启用\"))", "self.btn_enable = QPushButton(tr(\"启用\"))"),
        ("btn_enable.", "self.btn_enable."),
        ("left_top.addWidget(btn_enable)", "left_top.addWidget(self.btn_enable)"),
        
        # Action Layout
        ("btn_save_state = QPushButton(tr(\"记忆当前启用状态\"))", "self.btn_save_state = QPushButton(tr(\"记忆当前启用状态\"))"),
        ("btn_save_state.", "self.btn_save_state."),
        ("action_layout.addWidget(btn_save_state)", "action_layout.addWidget(self.btn_save_state)"),
        
        ("action_layout.addWidget(QLabel(tr(\"已存记忆：\")))",
         "self.lbl_saved = QLabel(tr(\"已存记忆：\"))\n        action_layout.addWidget(self.lbl_saved)"),
         
        ("btn_apply_state = QPushButton(tr(\"应用记忆\"))", "self.btn_apply_state = QPushButton(tr(\"应用记忆\"))"),
        ("btn_apply_state.", "self.btn_apply_state."),
        ("action_layout.addWidget(btn_apply_state)", "action_layout.addWidget(self.btn_apply_state)"),
        
        ("btn_delete_state = QPushButton(tr(\"删除记忆\"))", "self.btn_delete_state = QPushButton(tr(\"删除记忆\"))"),
        ("btn_delete_state.", "self.btn_delete_state."),
        ("action_layout.addWidget(btn_delete_state)", "action_layout.addWidget(self.btn_delete_state)"),
        
        # Right Layout
        ("right_layout.addWidget(QLabel(tr(\"选中项信息\")))",
         "self.lbl_sel_info = QLabel(tr(\"选中项信息\"))\n        right_layout.addWidget(self.lbl_sel_info)"),
        ("path_layout.addWidget(QLabel(tr(\"路径：\")))",
         "self.lbl_path = QLabel(tr(\"路径：\"))\n        path_layout.addWidget(self.lbl_path)"),
        
        # Bottom Layout
        ("btn_help = QPushButton(tr(\"帮助\"))", "self.btn_help = QPushButton(tr(\"帮助\"))"),
        ("btn_help.", "self.btn_help."),
        ("bottom_layout.addWidget(btn_help)", "bottom_layout.addWidget(self.btn_help)"),
        
        ("btn_exit = QPushButton(tr(\"退出\"))", "self.btn_exit = QPushButton(tr(\"退出\"))"),
        ("btn_exit.", "self.btn_exit."),
        ("bottom_layout.addWidget(btn_exit)", "bottom_layout.addWidget(self.btn_exit)"),
    ]
    
    for old, new in replacements:
        content = content.replace(old, new)
        
    # Inject retranslateUi and changeEvent
    retranslate_code = """
    def changeEvent(self, event):
        from PyQt6.QtCore import QEvent
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

    def retranslateUi(self):
        from i18n import tr
        self.setWindowTitle(tr("尘白MOD管理柒"))
        self.lbl_src.setText(tr("源MOD目录："))
        self.btn_src.setText(tr("选择..."))
        self.lbl_tgt.setText(tr("目标MOD目录："))
        self.btn_tgt.setText(tr("选择..."))
        self.btn_clear_target.setText(tr("清空目标目录"))
        self.lbl_src_struct.setText(tr("源MOD目录结构"))
        
        # Update toggle button text
        if getattr(self, '_dnd_mode', False):
            self.btn_dnd.setText(tr("免打扰：开"))
        else:
            self.btn_dnd.setText(tr("免打扰：关"))
            
        self.combo_sort.setItemText(0, tr("按名称排序 (升序)"))
        self.combo_sort.setItemText(1, tr("按名称排序 (降序)"))
        self.combo_sort.setItemText(2, tr("按时间排序 (最新在前)"))
        self.combo_sort.setItemText(3, tr("按时间排序 (最旧在前)"))
        
        self.btn_expand.setText(tr("全部展开"))
        self.btn_collapse.setText(tr("全部收起"))
        self.btn_disable.setText(tr("禁用"))
        self.btn_enable.setText(tr("启用"))
        self.btn_refresh.setText(tr("刷新"))
        
        self.btn_save_state.setText(tr("记忆当前启用状态"))
        self.lbl_saved.setText(tr("已存记忆："))
        self.btn_apply_state.setText(tr("应用记忆"))
        self.btn_delete_state.setText(tr("删除记忆"))
        
        self.lbl_sel_info.setText(tr("选中项信息"))
        self.lbl_path.setText(tr("路径："))
        self.lbl_preview_title.setText(tr("预览："))
        
        if not hasattr(self, "_current_preview_path") or not self._current_preview_path:
            self.lbl_preview_img.setText(tr("可拖拽或粘贴图片到此处设置pak预览图。"))
            
        self.btn_help.setText(tr("帮助"))
        self.btn_exit.setText(tr("退出"))
        
        if self._tree_model:
            self._tree_model.retranslate()
"""
    
    if "def changeEvent(" not in content:
        # Insert after _build_ui
        idx = content.find("def _on_language_changed(self, index: int):")
        if idx != -1:
            content = content[:idx] + retranslate_code + "\n    " + content[idx:]
            
    with open("ui.py", "w", encoding="utf-8") as f:
        f.write(content)
        
if __name__ == "__main__":
    main()
