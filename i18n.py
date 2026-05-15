import json
import os
from config import load_config, save_config
from PyQt6.QtCore import QTranslator, QCoreApplication

_current_lang = "zh_CN"

_LANGUAGES = {
    "zh_CN": "简体中文",
    "en_US": "English"
}

_translations = {
    "zh_CN": {},
    "en_US": {
        "免责声明": "Disclaimer",
        "<b>免责声明</b><br><br>1. 使用本工具所造成的任何直接或间接损失由使用者自行负责。<br>2. 因使用MOD对游戏账号造成的任何损失（包括但不限于封号）由使用者自行负责。<br><br>点击“同意”即代表您已知晓并接受以上条款。如果不同意，请点击“退出”。": "<b>Disclaimer</b><br><br>1. The user is responsible for any direct or indirect losses caused by using this tool.<br>2. The user is responsible for any losses caused to the game account by using MODs (including but not limited to account bans).<br><br>Click \"Agree\" to indicate that you have read and accepted the above terms. If you do not agree, please click \"Exit\".",
        "同意": "Agree",
        "退出": "Exit",
        "确定": "OK",
        "取消": "Cancel",
        "是": "Yes",
        "否": "No",
        "PAK通用MOD管理柒": "PAK Universal MOD Manager",
        "源MOD目录：": "Source MOD Directory:",
        "选择...": "Browse...",
        "目标MOD目录：": "Target MOD Directory:",
        "清空目标目录": "Clear Target Directory",
        "源MOD目录结构": "Source MOD Directory Structure",
        "免打扰：关": "DND: Off",
        "免打扰：开": "DND: On",
        "按名称排序 (升序)": "Sort by Name (Ascending)",
        "按名称排序 (降序)": "Sort by Name (Descending)",
        "按时间排序 (最新在前)": "Sort by Time (Newest First)",
        "按时间排序 (最旧在前)": "Sort by Time (Oldest First)",
        "全部展开": "Expand All",
        "全部收起": "Collapse All",
        "禁用": "Disable",
        "启用": "Enable",
        "刷新": "Refresh",
        "记忆当前启用状态": "Save Enabled State",
        "已存记忆：": "Saved States:",
        "应用记忆": "Apply State",
        "删除记忆": "Delete State",
        "选中项信息": "Selected Item Info",
        "路径：": "Path:",
        "预览：": "Preview:",
        "可拖拽或粘贴图片到此处设置pak预览图。": "Drag or paste an image here to set the pak preview.",
        "就绪（Pillow：不可用）": "Ready (Pillow: Unavailable)",
        "就绪（Pillow：已启用，WebP：支持）": "Ready (Pillow: Enabled, WebP: Supported)",
        "就绪（Pillow：已启用，WebP：不支持）": "Ready (Pillow: Enabled, WebP: Unsupported)",
        "就绪（Pillow：已启用，WebP：无法检测）": "Ready (Pillow: Enabled, WebP: Unknown)",
        "加载预览失败": "Failed to load preview",
        "错误: {e}": "Error: {e}",
        "复制": "Copy",
        "诊断": "Diagnose",
        "帮助": "Help",
        "选择源MOD目录": "Select Source MOD Directory",
        "选择目标MOD目录": "Select Target MOD Directory",
        "打开": "Open",
        "正在读取源MOD目录结构...": "Reading Source MOD Directory Structure...",
        "就绪": "Ready",
        "提示": "Notice",
        "请先设置有效的源MOD目录": "Please set a valid Source MOD Directory first",
        "读取失败": "Read Failed",
        "错误": "Error",
        "备注": "Comment",
        "编辑备注": "Edit Comment",
        "请输入备注信息：": "Please enter comment:",
        "保存预览图失败：\n{e}": "Failed to save preview image:\n{e}",
        "成功将预览图关联到 {node.name}": "Successfully linked preview image to {node.name}",
        "请先选中一个 .pak 文件，再拖拽图片进行关联。": "Please select a .pak file first before dragging an image to link.",
        "保存粘贴的预览图失败：\n{e}": "Failed to save pasted preview image:\n{e}",
        "成功将剪贴板图片关联到 {node.name}": "Successfully linked clipboard image to {node.name}",
        "请先选中一个 .pak 文件，再粘贴图片进行关联。": "Please select a .pak file first before pasting an image to link.",
        "无法删除源MOD根目录。": "Cannot delete Source MOD root directory.",
        "文件夹及其所有内容": "Folder and all its contents",
        "文件": "File",
        "确认删除": "Confirm Deletion",
        "确定要永久删除该{type_str}吗？此操作不可恢复！\n\n{node.name}": "Are you sure you want to permanently delete this {type_str}? This action cannot be undone!\n\n{node.name}",
        "已删除: {node.name}": "Deleted: {node.name}",
        "删除失败": "Delete Failed",
        "删除失败：\n{e}": "Delete failed:\n{e}",
        "无法重命名源MOD根目录。": "Cannot rename Source MOD root directory.",
        "重命名": "Rename",
        "请输入新名称：": "Please enter a new name:",
        "名称 '{new_name}' 已存在！": "Name '{new_name}' already exists!",
        "重命名成功: {old_name} -> {new_name}": "Rename successful: {old_name} -> {new_name}",
        "重命名失败": "Rename Failed",
        "无法重命名：\n{e}": "Cannot rename:\n{e}",
        "新建文件夹": "New Folder",
        "请输入文件夹名称：": "Please enter folder name:",
        "文件夹或文件 '{name}' 已存在！": "Folder or file '{name}' already exists!",
        "成功创建文件夹: {name}": "Successfully created folder: {name}",
        "创建失败": "Create Failed",
        "无法创建文件夹：\n{e}": "Cannot create folder:\n{e}",
        "新增同级目录": "New Sibling Folder",
        "新增子目录": "New Subfolder",
        "无法在源MOD根目录的同级创建文件夹，请使用新增子目录。": "Cannot create a folder at the same level as the Source MOD root directory. Please use New Subfolder.",
        "删除": "Delete",
        "Qt版本暂未完整移植诊断逻辑。": "The Qt version has not fully ported the diagnostic logic yet.",
        "PAK通用MOD管理柒 帮助指南": "PAK Universal MOD Manager Help Guide",
        "快速上手": "Quick Start",
        "操作指南": "How to Use",
        "<b>1. 设置 MOD 管理文件夹（源MOD目录）</b><br>选择一个用于存放 MOD 文件的文件夹。建议与 MOD 管理器所在的目录保持一致。": "<b>1. Set MOD library folder (Source MOD Directory)</b><br>Choose a folder to store your MOD files. It is recommended to keep it in the same directory as the MOD manager.",
        "<b>2. 设置游戏 MOD 安装目录（目标MOD目录）</b><br>将此路径指向游戏实际的 MOD 存放位置。默认路径示例：<br><code style='background-color: rgba(128, 128, 128, 0.2); padding: 2px 4px; border-radius: 4px;'>游戏文件夹/Game/Content/Paks/mods</code>": "<b>2. Set game MOD install folder (Target MOD Directory)</b><br>Point this path to where the game actually loads MODs. Default example:<br><code style='background-color: rgba(128, 128, 128, 0.2); padding: 2px 4px; border-radius: 4px;'>GameDir/Game/Content/Paks/mods</code>",
        "<b>3. 添加你的 MOD</b><br>解压下载好的 MOD 压缩包，然后将文件复制到第 1 步设置的 MOD 管理文件夹中，可按你的习惯分类整理。<br>📸 <b>预览图</b>：如果你在与 <code>.pak</code> 文件相同的文件夹中放入一个同名的图片文件（png、jpg、bmp 或 webp），它将被自动识别为该 MOD 的预览图。": "<b>3. Add your MODs</b><br>Extract the downloaded MOD archive, then copy the files into the MOD library folder from step 1. You can organize them into subfolders as you like.<br>📸 <b>Preview image</b>: Put an image file with the same name (png, jpg, bmp, or webp) in the same folder as the <code>.pak</code> file, and it will be detected as the MOD preview.",
        "<b>4. 刷新并开始管理</b><br>点击管理器上的“刷新”按钮。就这样 —— 你现在可以随时启用、禁用并整理你的 MOD 了。": "<b>4. Refresh and start managing</b><br>Click the \"Refresh\" button. That's it — you can now enable/disable and organize your MODs anytime.",
        "<b>源MOD目录：</b>你的 MOD 管理文件夹，用于存放所有 MOD 文件（建议自行分类整理）。": "<b>Source MOD Directory:</b> Your MOD library folder that stores all MOD files (you can organize them into subfolders).",
        "<b>目标MOD目录：</b>游戏读取 MOD 的目录，通常为 <code style='background-color: rgba(128, 128, 128, 0.2); padding: 2px 4px; border-radius: 4px;'>游戏文件夹/Game/Content/Paks/mods</code>。如果没有 mods 目录，需要手动创建。": "<b>Target MOD Directory:</b> The folder where the game loads MODs, usually <code style='background-color: rgba(128, 128, 128, 0.2); padding: 2px 4px; border-radius: 4px;'>GameDir/Game/Content/Paks/mods</code>. If the mods folder does not exist, create it manually.",
        "<b>刷新：</b>当你新增/移动/删除 MOD 文件后，点击“刷新”重新读取源目录结构，并更新启用状态与预览信息。": "<b>Refresh:</b> After adding/moving/deleting MOD files, click \"Refresh\" to rescan the source folder and update enabled status and preview info.",
        "<b>启用/禁用：</b>勾选 .pak 文件后点击“启用/禁用”。支持勾选文件夹进行批量选择；也可<b>双击 .pak 文件</b>快速切换，或在列表上<b>右键</b>使用菜单快捷启用/禁用。": "<b>Enable/Disable:</b> Check .pak files and click \"Enable/Disable\". You can also check folders for batch selection; double-click a <b>.pak</b> to toggle quickly, or use the <b>right-click</b> menu.",
        "<b>免打扰模式：</b>开启后，会隐藏不包含 .pak 的无关项，让列表更清爽。": "<b>DND mode:</b> When enabled, hides items that don't contain .pak files to keep the list clean.",
        "<b>排序：</b>支持按名称/时间的升序与降序排序，并会尽量保留你当前展开的目录状态。": "<b>Sorting:</b> Sort by name/time (ascending/descending), while trying to preserve your current expanded folders.",
        "<b>全部展开/全部收起：</b>若当前选中了某个目录，将只对该目录递归展开/收起；否则对整个列表展开/收起。": "<b>Expand All/Collapse All:</b> If a folder is selected, it expands/collapses that folder recursively; otherwise it expands/collapses the whole list.",
        "<b>记忆启用状态：</b>底部按钮栏可“记忆当前启用状态”保存一套启用/禁用配置；之后可从下拉框选择并“应用记忆”，也可“删除记忆”。": "<b>Save enabled state:</b> In the bottom bar, \"Save Enabled State\" stores a set of enabled/disabled mods. Later you can pick one from the dropdown to \"Apply State\", or \"Delete State\".",
        "<b>清空目标目录：</b>点击“清空目标目录”可从游戏 MOD 安装目录中移除所有已安装的 MOD。": "<b>Clear target directory:</b> Click \"Clear Target Directory\" to remove all installed mods from the game's MOD folder.",
        "<b>应用模式：</b>底部栏的滑动开关可在“链接”与“拷贝”模式间切换。<b>链接模式</b>通过创建符号链接启用MOD，无需复制文件，节省磁盘空间且操作更快；<b>拷贝模式</b>则将文件复制到目标目录。切换至链接模式时需要管理员权限，若无权限将弹窗确认后以管理员身份重启。启用后，状态列会标注“已启用 · 链接”或“已启用 · 拷贝”。": "<b>Application Mode:</b> The toggle at the bottom bar switches between <b>Link</b> and <b>Copy</b> modes. <b>Link mode</b> uses symbolic links to enable MODs without copying files, saving disk space; <b>Copy mode</b> copies files to the target directory. Switching to Link mode requires administrator privileges; if unavailable, a confirmation dialog will appear to restart as administrator. The status column will display \"Enabled · Link\" or \"Enabled · Copy\".",
        "<b>预览图操作：</b>右侧预览区支持拖拽本地图片、从网页拖拽图片/链接（自动下载并关联），也支持直接粘贴剪贴板图片。双击右侧预览图可用系统图片查看器打开；在左侧列表对图片文件右键可删除。": "<b>Preview images:</b> The right preview area supports dragging local images, dragging images/links from web pages (auto-download & link), and pasting images from the clipboard. Double-click the preview to open it; right-click image files in the list to delete.",
        "<b>粘贴（Ctrl+V）：</b>在左侧选中目标目录（或任意文件），按 Ctrl+V 可将剪贴板中的文件/文件夹粘贴到该目录；支持资源管理器复制，也支持从系统 zip / WinRAR 复制（保留目录结构）。": "<b>Paste (Ctrl+V):</b> Select a target folder (or any file) in the left list and press Ctrl+V to paste files/folders from the clipboard. Supports Explorer copy and system ZIP/WinRAR copy (keeps folder structure).",
        "<b>打开文件：</b>双击文本/图片文件会调用系统默认程序打开查看内容。": "<b>Open files:</b> Double-click text/image files to open them with the system default app.",
        "<b>表格调整：</b>可拖动列分隔线调整列宽，列宽会自动记忆。": "<b>Table adjustment:</b> Drag column separators to resize columns. Widths are remembered automatically.",
        "<b>源MOD目录：</b>你的 MOD 管理文件夹，用于存放所有 MOD 文件（建议自行分类整理）。可点击“选择...”选择文件夹，或点击“打开”在资源管理器中打开。": "<b>Source MOD Directory:</b> Your MOD library folder that stores all MOD files (you can organize them into subfolders). Click \"Browse...\" to pick a folder, or click \"Open\" to open it in Explorer.",
        "<b>目标MOD目录：</b>游戏读取 MOD 的目录，通常为 <code style='background-color: rgba(128, 128, 128, 0.2); padding: 2px 4px; border-radius: 4px;'>游戏文件夹/Game/Content/Paks/mods</code>。如果没有 mods 目录，需要手动创建。可点击“选择...”设置路径，或点击“打开”快速定位目录。": "<b>Target MOD Directory:</b> The folder where the game loads MODs, usually <code style='background-color: rgba(128, 128, 128, 0.2); padding: 2px 4px; border-radius: 4px;'>GameDir/Game/Content/Paks/mods</code>. If the mods folder does not exist, create it manually. Click \"Browse...\" to set the path, or click \"Open\" to locate it quickly.",
        "<b>新建文件夹：</b>在左侧选中一个目录后点击“新建文件夹”，会在该目录下创建子目录；若选中的是文件，则在其同级创建；未选中任何项则默认在源MOD目录下创建。": "<b>New Folder:</b> With a folder selected on the left, \"New Folder\" creates a subfolder inside it; if a file is selected, it creates a sibling folder; if nothing is selected, it creates the folder under the Source MOD Directory.",
        "<b>语言：</b>右下角可切换界面语言。": "<b>Language:</b> Switch the UI language from the bottom-right dropdown.",
        "<b>源MOD目录：</b>存放所有下载的 MOD 文件的主目录。": "<b>Source MOD Directory:</b> The main directory where all downloaded MOD files are stored.",
        "<b>目标MOD目录：</b>游戏读取 MOD 的目录，通常为 <code style='background-color: rgba(128, 128, 128, 0.2); padding: 2px 4px; border-radius: 4px;'>游戏目录/Game/Content/Paks/mods</code>。如果没有mods目录，需要手动创建。": "<b>Target MOD Directory:</b> The directory where the game reads MODs, usually <code style='background-color: rgba(128, 128, 128, 0.2); padding: 2px 4px; border-radius: 4px;'>GameDir/Game/Content/Paks/mods</code>. If the mods directory does not exist, you need to create it manually.",
        "<b>启用/禁用：</b>勾选列表中的复选框后点击“启用/禁用”按钮。支持直接勾选文件夹进行批量操作。": "<b>Enable/Disable:</b> Check the checkboxes in the list and click the 'Enable/Disable' button. Supports checking folders for batch operations.",
        "<b>记忆/清空：</b>使用“记忆当前启用状态”保存目前启用的模组，随后可以“一键应用已记状态”。清空目标目录可直接卸载所有模组。": "<b>Save/Clear:</b> Use 'Save Enabled State' to save currently enabled mods, and you can 'Apply State' later. Clearing the target directory will directly uninstall all mods.",
        "<b>快捷操作：</b>": "<b>Quick Actions:</b>",
        "<b>双击 .pak 文件</b>：快捷切换启用/禁用状态。": "<b>Double-click .pak file</b>: Quick toggle enable/disable status.",
        "<b>双击文本/图片文件</b>：调用系统默认应用打开查看内容。": "<b>Double-click text/image file</b>: Open to view contents using system default application.",
        "<b>双击右侧预览图</b>：调用系统默认图片查看器查看原图。": "<b>Double-click right preview</b>: Open the original image using system default image viewer.",
        "<b>生成预览图</b>：先在左侧选中某个.pak文件，然后将图片文件拖入或将剪贴板的图片直接粘贴到右侧的预览图区域。": "<b>Generate Preview</b>: First select a .pak file on the left, then drag an image file or paste an image from the clipboard into the preview area on the right.",
        "<b>粘贴文件/目录（Ctrl+V）</b>：在左侧列表选中目标目录（或任意文件），按 Ctrl+V 可将剪贴板内容粘贴到该目录。支持资源管理器复制的文件/文件夹，也支持从系统 zip / WinRAR 中复制的内容（保留目录结构）。": "<b>Paste Files/Folders (Ctrl+V)</b>: Select a target folder (or any file) in the left list and press Ctrl+V to paste into that directory. Supports files/folders copied from Explorer, and also content copied from system ZIP or WinRAR (preserves folder structure).",
        "<b>预览图拖拽来源</b>：右侧预览区域支持拖拽本地图片文件，也支持从网页拖拽图片/图片链接（会自动下载并关联）。": "<b>Preview Drag Sources</b>: The right preview area supports dragging local image files, and also dragging images/image links from web pages (it will download and link automatically).",
        "<b>删除图片</b>：在左侧列表的图片文件上右键即可删除。": "<b>Delete Image</b>: Right-click on the image file in the left list to delete it.",
        "<b>右键菜单</b>：提供针对单个文件或目录的启用/禁用快捷方式。": "<b>Right-click Menu</b>: Provides quick enable/disable actions for a single file or directory.",
        "<b>免打扰模式：</b>开启后，列表将自动隐藏所有非包含 .pak 的干扰目录和文件。": "<b>Do Not Disturb (DND) Mode:</b> When enabled, the list automatically hides all interfering directories and files that do not contain .pak files.",
        "<b>排序：</b>支持按名称、时间的正序和倒序排列，自动记忆当前展开的目录。": "<b>Sorting:</b> Supports ascending and descending sorting by name and time, automatically remembering the currently expanded directories.",
        "<b>表格调整：</b>可以直接拖动“名称”、“预览”和“状态”三列之间的竖线来调整列宽，列宽会自动记忆。": "<b>Table Adjustment:</b> You can directly drag the vertical lines between the 'Name', 'Preview', and 'Status' columns to adjust their width. The column widths will be remembered automatically.",
        "名称": "Name",
        "大小": "Size",
        "修改时间": "Modified",
        "预览": "Preview",
        "状态": "Status",
        "已启用": "Enabled",
        "已启用 · 链接": "Enabled · Link",
        "已启用 · 拷贝": "Enabled · Copy",
        "软连接模式": "Symlink Mode",
        "拷贝模式": "Copy Mode",
        "链接": "Link",
        "拷贝": "Copy",
        "软连接模式需要管理员权限，是否以管理员身份重启程序？": "Symlink mode requires administrator privileges. Restart as administrator?",
        "部分启用": "Partially Enabled",
        "源MOD目录为空": "Source MOD Directory is empty",
        "源MOD目录不存在或不是文件夹": "Source MOD Directory does not exist or is not a folder",
        "未找到指定的记忆。": "Saved state not found.",
        "请先选择要删除的记忆。": "Please select a state to delete first.",
        "确定要删除记忆 '{name}' 吗？": "Are you sure you want to delete state '{name}'?",
        "成功删除记忆 '{name}'。": "Successfully deleted state '{name}'.",
        "请输入要保存的记忆名称：": "Please enter a name for the saved state:",
        "记忆名称 '{name}' 已存在，是否覆盖？": "State name '{name}' already exists, overwrite?",
        "记忆覆盖": "Overwrite State",
        "已保存当前状态为 '{name}'。": "Current state saved as '{name}'.",
        "语言已切换，是否立即重启应用以应用更改？": "Language switched, do you want to restart the application now to apply changes?",
    }
}

def init_i18n():
    global _current_lang
    cfg = load_config()
    _current_lang = cfg.get("language", "zh_CN")
    if _current_lang not in _LANGUAGES:
        _current_lang = "zh_CN"

def tr(text: str) -> str:
    global _current_lang
    if _current_lang in _translations and text in _translations[_current_lang]:
        return _translations[_current_lang][text]
    return text

def set_language(lang_code: str):
    global _current_lang, _translator_instance
    if lang_code in _LANGUAGES:
        _current_lang = lang_code
        save_config({"language": lang_code})
        
        # Trigger LanguageChange event via QTranslator
        app = QCoreApplication.instance()
        if app:
            if _translator_instance is None:
                _translator_instance = DictTranslator()
            # In PyQt, installing the same translator instance might not re-trigger the event.
            # We must remove it first and then install it again.
            app.removeTranslator(_translator_instance)
            app.installTranslator(_translator_instance)

def get_language() -> str:
    return _current_lang

def get_available_languages() -> dict:
    return _LANGUAGES

class DictTranslator(QTranslator):
    def translate(self, context, sourceText, disambiguation=None, n=-1):
        return tr(sourceText)

_translator_instance = None

