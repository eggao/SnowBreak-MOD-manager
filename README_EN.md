# Snowbreak MOD Manager

🇨🇳 [中文](./README.md) | 🇬🇧 [English](./README_EN.md)

## 📌 Quick Start

1. **Set MOD Library Folder (Source MOD Directory)**  
   Choose a folder to store your MOD files. It is recommended to keep it in the same directory as the MOD manager.

2. **Set Game MOD Install Folder (Target MOD Directory)**  
   Point this path to where the game actually loads MODs. Default example: `GameFolder/Game/Content/Paks/mods`

3. **Add Your MODs**  
   Extract the downloaded MOD archive, then copy the files into the MOD library folder from step 1. You can organize them into subfolders as you like.

   > 📸 **Preview Image**: If you put an image file (png, jpg, bmp, or webp) with the same name as a `.pak` file in the same folder, it will be automatically detected as the preview image for that MOD.

4. **Refresh and Start Managing**  
   Click the "Refresh" button. That's it — you can now enable, disable, and organize your MODs anytime.

---

## ⚙️ How to Use

### Source MOD Directory
Your MOD library folder that stores all MOD files (you can organize them into subfolders). Click "Browse..." to pick a folder, or click "Open" to open it in Explorer.

### Target MOD Directory
The folder where the game loads MODs, usually `GameFolder/Game/Content/Paks/mods`. If the `mods` folder does not exist, create it manually. Click "Browse..." to set the path, or click "Open" to locate it quickly.

### Clear Target Directory
Click "Clear Target Directory" to remove all installed MODs from the game's MOD folder.

### Application Mode
The toggle at the bottom bar switches between **Link** and **Copy** modes.

- **Link mode**: Uses symbolic links to enable MODs without copying files, saving disk space and operating faster
- **Copy mode**: Copies files to the target directory

Switching to Link mode requires administrator privileges. After enabling, the status column will display "Enabled · Link" or "Enabled · Copy".

### DND Mode
When enabled, hides items that don't contain `.pak` files to keep the list clean.

### Sorting
Sort by name/time (ascending/descending), while trying to preserve your current expanded folders.

### Expand All / Collapse All
If a folder is selected, it expands/collapses that folder recursively; otherwise it expands/collapses the whole list.

### New Folder
With a folder selected on the left, "New Folder" creates a subfolder inside it; if a file is selected, it creates a sibling folder; if nothing is selected, it creates the folder under the Source MOD Directory.

### Enable / Disable
Check `.pak` files and click "Enable/Disable". You can also check folders for batch selection. Double-click a `.pak` to toggle quickly, or use the right-click menu.

### Refresh
After adding/moving/deleting MOD files, click "Refresh" to rescan the source folder structure and update enabled status and preview info.

### Save Enabled State
In the bottom bar, "Save Enabled State" stores a set of enabled/disabled configurations. Later you can select one from the dropdown to "Apply State", or "Delete State".

### Preview Images
The right preview area supports dragging local images, dragging images/links from web pages (auto-download & link), and pasting images from the clipboard. Double-click the preview image to open it with the system image viewer. Right-click image files in the left list to delete.

### Paste (Ctrl+V)
Select a target folder (or any file) in the left list and press `Ctrl+V` to paste files/folders from the clipboard. Supports Explorer copy and system ZIP/WinRAR copy (keeps folder structure).

### Open Files
Double-click text/image files to open them with the system default application.

### Table Adjustment
Drag column separators to resize columns. Widths are remembered automatically.

### Language
Switch the UI language from the bottom-right dropdown.

---

## ⚠️ Disclaimer

1. The user assumes sole responsibility for any direct or indirect losses caused by using this tool.
2. The user assumes sole responsibility for any loss to their game account resulting from the use of MODs (including but not limited to account suspension).
