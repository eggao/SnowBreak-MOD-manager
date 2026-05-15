import os
import shutil
import sys
import ctypes
import hashlib
from typing import Optional

from PyQt6.QtCore import QSize
from PyQt6.QtGui import QPixmap, QImage

from config import get_app_dir, normalize_path

_third_party_dir = os.path.join(get_app_dir(), "third_party")
if os.path.isdir(_third_party_dir) and _third_party_dir not in sys.path:
    sys.path.insert(0, _third_party_dir)

try:
    from PIL import Image
    PIL_AVAILABLE = True
    PIL_IMPORT_ERROR = None
except Exception as e:
    Image = None
    PIL_AVAILABLE = False
    PIL_IMPORT_ERROR = f"{type(e).__name__}: {e}"

try:
    import PIL
    PIL_VERSION = getattr(PIL, "__version__", None)
except Exception:
    PIL_VERSION = None

def get_pillow_webp_support() -> Optional[bool]:
    if not PIL_AVAILABLE:
        return None
    try:
        from PIL import features
        return bool(features.check("webp"))
    except Exception:
        return None

def is_pak_file(path: str) -> bool:
    return os.path.isfile(path) and os.path.splitext(path)[1].lower() == ".pak"

def find_preview_image_for_pak(pak_path: str) -> Optional[str]:
    pak_path = normalize_path(pak_path)
    if not pak_path:
        return None
    folder = os.path.dirname(pak_path)
    stem = os.path.splitext(os.path.basename(pak_path))[0]
    exts = (".png", ".jpg", ".jpeg", ".bmp", ".webp")
    for ext in exts:
        candidate = os.path.join(folder, stem + ext)
        if os.path.isfile(candidate):
            return candidate
    return None

def has_symlink_permission() -> bool:
    cache_dir = os.path.join(get_app_dir(), "cache")
    os.makedirs(cache_dir, exist_ok=True)
    test_src = os.path.join(cache_dir, ".symlink_test_src")
    test_dst = os.path.join(cache_dir, ".symlink_test_dst")
    try:
        with open(test_src, "w") as f:
            f.write("test")
        os.symlink(test_src, test_dst)
        return True
    except OSError:
        return False
    finally:
        for p in (test_src, test_dst):
            try:
                if os.path.islink(p):
                    os.unlink(p)
                elif os.path.isfile(p):
                    os.remove(p)
            except Exception:
                pass

def relaunch_as_admin():
    try:
        exe = sys.executable
        args = " ".join(f'"{a}"' for a in sys.argv)
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", exe, args, None, 1
        )
    except Exception:
        pass

def symlink_or_copy(src: str, dst: str, use_symlink: bool = True) -> bool:
    if not os.path.isfile(src):
        return False
    if os.path.lexists(dst):
        try:
            os.unlink(dst)
        except OSError:
            pass
    if use_symlink:
        try:
            os.symlink(src, dst)
            return True
        except OSError:
            pass
    try:
        shutil.copy2(src, dst)
        return True
    except Exception:
        return False

THUMB_CELL_SIZE = QSize(56, 38)

def get_thumb_cache_path(src_path: str, target_size: QSize) -> str:
    key = f"{src_path}_{target_size.width()}x{target_size.height()}"
    hash_name = hashlib.md5(key.encode("utf-8")).hexdigest()
    cache_dir = os.path.join(get_app_dir(), "cache", "thumbs")
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, hash_name + ".png")

def load_cached_thumb(src_path: str, target_size: QSize) -> Optional[QPixmap]:
    if not os.path.isfile(src_path):
        return None
    cache_path = get_thumb_cache_path(src_path, target_size)
    if os.path.isfile(cache_path):
        src_mtime = os.path.getmtime(src_path)
        cache_mtime = os.path.getmtime(cache_path)
        if cache_mtime >= src_mtime:
            pixmap = QPixmap(cache_path)
            if not pixmap.isNull():
                return pixmap
    pixmap = load_qpixmap(src_path, target_size)
    if pixmap and not pixmap.isNull():
        pixmap.save(cache_path, "PNG")
    return pixmap

def load_qpixmap(image_path: str, max_size: Optional[QSize] = None) -> Optional[QPixmap]:
    if not os.path.isfile(image_path):
        return None

    if PIL_AVAILABLE and Image is not None:
        try:
            with Image.open(image_path) as opened:
                img = opened.convert("RGBA")
                if max_size is not None:
                    resample = getattr(Image, "Resampling", None)
                    if resample and hasattr(resample, "LANCZOS"):
                        resample_filter = resample.LANCZOS
                    elif hasattr(Image, "LANCZOS"):
                        resample_filter = getattr(Image, "LANCZOS")
                    else:
                        resample_filter = getattr(Image, "ANTIALIAS", 1)
                    img.thumbnail((max_size.width(), max_size.height()), resample_filter)
                
                data = img.tobytes("raw", "RGBA")
                qim = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
                return QPixmap.fromImage(qim)
        except Exception:
            pass

    # Fallback to Qt native loader
    pixmap = QPixmap(image_path)
    if pixmap.isNull():
        return None
    if max_size is not None:
        if pixmap.width() > max_size.width() or pixmap.height() > max_size.height():
            from PyQt6.QtCore import Qt
            pixmap = pixmap.scaled(
                max_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
    return pixmap

def extract_virtual_files(target_dir: str):
    import ctypes
    from ctypes import wintypes
    import os
    
    try:
        ole32 = ctypes.oledll.ole32
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        
        CF_FILEGROUPDESCRIPTORW = user32.RegisterClipboardFormatW("FileGroupDescriptorW")
        CF_FILEGROUPDESCRIPTOR = user32.RegisterClipboardFormatW("FileGroupDescriptor")
        CF_FILECONTENTS = user32.RegisterClipboardFormatW("FileContents")
        
        if CF_FILECONTENTS == 0 or (CF_FILEGROUPDESCRIPTORW == 0 and CF_FILEGROUPDESCRIPTOR == 0):
            return 0, ["无法注册剪贴板格式"]
            
        ole32.OleInitialize(None)
        
        class FORMATETC(ctypes.Structure):
            _fields_ = [
                ("cfFormat", wintypes.WORD),
                ("ptd", ctypes.c_void_p),
                ("dwAspect", wintypes.DWORD),
                ("lindex", wintypes.LONG),
                ("tymed", wintypes.DWORD)
            ]

        class STGMEDIUM(ctypes.Structure):
            _fields_ = [
                ("tymed", wintypes.DWORD),
                ("hGlobal", ctypes.c_void_p),
                ("pUnkForRelease", ctypes.c_void_p)
            ]

        class IDataObjectVtbl(ctypes.Structure):
            _fields_ = [
                ("QueryInterface", ctypes.c_void_p),
                ("AddRef", ctypes.c_void_p),
                ("Release", ctypes.WINFUNCTYPE(wintypes.ULONG, ctypes.c_void_p)),
                ("GetData", ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, ctypes.POINTER(FORMATETC), ctypes.POINTER(STGMEDIUM))),
                ("GetDataHere", ctypes.c_void_p),
                ("QueryGetData", ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, ctypes.POINTER(FORMATETC)))
            ]

        class IDataObject(ctypes.Structure):
            _fields_ = [("lpVtbl", ctypes.POINTER(IDataObjectVtbl))]
            
        class FILETIME(ctypes.Structure):
            _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

        class FILEDESCRIPTORW(ctypes.Structure):
            _fields_ = [
                ("dwFlags", wintypes.DWORD),
                ("clsid", ctypes.c_byte * 16),
                ("sizel", wintypes.LONG * 2),
                ("pointl", wintypes.LONG * 2),
                ("dwFileAttributes", wintypes.DWORD),
                ("ftCreationTime", FILETIME),
                ("ftLastAccessTime", FILETIME),
                ("ftLastWriteTime", FILETIME),
                ("nFileSizeHigh", wintypes.DWORD),
                ("nFileSizeLow", wintypes.DWORD),
                ("cFileName", wintypes.WCHAR * 260)
            ]
            
        class FILEDESCRIPTORA(ctypes.Structure):
            _fields_ = [
                ("dwFlags", wintypes.DWORD),
                ("clsid", ctypes.c_byte * 16),
                ("sizel", wintypes.LONG * 2),
                ("pointl", wintypes.LONG * 2),
                ("dwFileAttributes", wintypes.DWORD),
                ("ftCreationTime", FILETIME),
                ("ftLastAccessTime", FILETIME),
                ("ftLastWriteTime", FILETIME),
                ("nFileSizeHigh", wintypes.DWORD),
                ("nFileSizeLow", wintypes.DWORD),
                ("cFileName", wintypes.CHAR * 260)
            ]

        ole32.OleGetClipboard.argtypes = [ctypes.POINTER(ctypes.POINTER(IDataObject))]
        ole32.ReleaseStgMedium.argtypes = [ctypes.POINTER(STGMEDIUM)]
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalSize.argtypes = [ctypes.c_void_p]
        kernel32.GlobalSize.restype = ctypes.c_size_t

        pDataObj = ctypes.POINTER(IDataObject)()
        hr = ole32.OleGetClipboard(ctypes.byref(pDataObj))
        if hr != 0 or not pDataObj:
            return 0, []
            
        copied = 0
        errors = []
        
        try:
            FILE_ATTRIBUTE_DIRECTORY = 0x10

            def _safe_rel_path(raw_name: str) -> Optional[str]:
                if not raw_name:
                    return None
                name = str(raw_name).replace("/", os.sep).replace("\\", os.sep)
                drive, tail = os.path.splitdrive(name)
                if drive:
                    name = tail
                name = name.lstrip(os.sep)
                rel = os.path.normpath(name)
                if rel in ("", ".", ".."):
                    return None
                if os.path.isabs(rel):
                    return None
                if rel == ".." or rel.startswith(".." + os.sep):
                    return None
                return rel

            fmt_fgd = FORMATETC()
            fmt_fgd.cfFormat = CF_FILEGROUPDESCRIPTORW
            fmt_fgd.ptd = None
            fmt_fgd.dwAspect = 1
            fmt_fgd.lindex = -1
            fmt_fgd.tymed = 1 # TYMED_HGLOBAL
            
            is_unicode = True
            hr = pDataObj.contents.lpVtbl.contents.QueryGetData(pDataObj, ctypes.byref(fmt_fgd))
            if hr != 0:
                fmt_fgd.cfFormat = CF_FILEGROUPDESCRIPTOR
                hr = pDataObj.contents.lpVtbl.contents.QueryGetData(pDataObj, ctypes.byref(fmt_fgd))
                is_unicode = False
                if hr != 0:
                    return 0, []
                
            stg_fgd = STGMEDIUM()
            hr = pDataObj.contents.lpVtbl.contents.GetData(pDataObj, ctypes.byref(fmt_fgd), ctypes.byref(stg_fgd))
            if hr == 0 and stg_fgd.tymed == 1 and stg_fgd.hGlobal:
                ptr = kernel32.GlobalLock(stg_fgd.hGlobal)
                if ptr:
                    try:
                        cItems = ctypes.cast(ptr, ctypes.POINTER(wintypes.UINT)).contents.value
                        offset = 4
                        
                        desc_size = ctypes.sizeof(FILEDESCRIPTORW) if is_unicode else ctypes.sizeof(FILEDESCRIPTORA)
                        
                        for i in range(cItems):
                            fd_ptr = ptr + offset + i * desc_size
                            if is_unicode:
                                fd = FILEDESCRIPTORW.from_address(fd_ptr)
                                name = fd.cFileName
                            else:
                                fd = FILEDESCRIPTORA.from_address(fd_ptr)
                                try:
                                    name = fd.cFileName.decode('mbcs', errors='ignore')
                                except Exception:
                                    name = fd.cFileName.decode('utf-8', errors='ignore')
                            
                            if not name: continue

                            rel = _safe_rel_path(name)
                            if not rel:
                                errors.append(f"{name}: 无效的路径")
                                continue

                            dst_path = os.path.join(target_dir, rel)
                            try:
                                target_abs = os.path.abspath(target_dir)
                                dst_abs = os.path.abspath(dst_path)
                                if os.path.commonpath([target_abs, dst_abs]).lower() != target_abs.lower():
                                    errors.append(f"{name}: 路径越界")
                                    continue
                            except Exception:
                                errors.append(f"{name}: 路径解析失败")
                                continue

                            is_dir = bool(getattr(fd, "dwFileAttributes", 0) & FILE_ATTRIBUTE_DIRECTORY)
                            if str(name).endswith("\\") or str(name).endswith("/"):
                                is_dir = True

                            if is_dir:
                                try:
                                    os.makedirs(dst_path, exist_ok=True)
                                    copied += 1
                                except Exception as e:
                                    errors.append(f"{name}: {e}")
                                continue
                                
                            fmt_fc = FORMATETC()
                            fmt_fc.cfFormat = CF_FILECONTENTS
                            fmt_fc.ptd = None
                            fmt_fc.dwAspect = 1
                            fmt_fc.lindex = i
                            fmt_fc.tymed = 1 | 4 # TYMED_HGLOBAL | TYMED_ISTREAM
                            
                            stg_fc = STGMEDIUM()
                            hr_fc = pDataObj.contents.lpVtbl.contents.GetData(pDataObj, ctypes.byref(fmt_fc), ctypes.byref(stg_fc))
                            
                            if hr_fc == 0:
                                try:
                                    parent_dir = os.path.dirname(dst_path)
                                    if parent_dir:
                                        os.makedirs(parent_dir, exist_ok=True)
                                except Exception as e:
                                    errors.append(f"{name}: {e}")
                                    ole32.ReleaseStgMedium(ctypes.byref(stg_fc))
                                    continue
                                
                                if stg_fc.tymed == 1: # TYMED_HGLOBAL
                                    fc_ptr = kernel32.GlobalLock(stg_fc.hGlobal)
                                    if fc_ptr:
                                        size = kernel32.GlobalSize(stg_fc.hGlobal)
                                        data = ctypes.string_at(fc_ptr, size)
                                        with open(dst_path, "wb") as f:
                                            f.write(data)
                                        kernel32.GlobalUnlock(stg_fc.hGlobal)
                                        copied += 1
                                    ole32.ReleaseStgMedium(ctypes.byref(stg_fc))
                                elif stg_fc.tymed == 4: # TYMED_ISTREAM
                                    class IStreamVtbl(ctypes.Structure):
                                        _fields_ = [
                                            ("QueryInterface", ctypes.c_void_p),
                                            ("AddRef", ctypes.c_void_p),
                                            ("Release", ctypes.WINFUNCTYPE(wintypes.ULONG, ctypes.c_void_p)),
                                            ("Read", ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, ctypes.c_void_p, wintypes.ULONG, ctypes.POINTER(wintypes.ULONG))),
                                        ]
                                    class IStream(ctypes.Structure):
                                        _fields_ = [("lpVtbl", ctypes.POINTER(IStreamVtbl))]
                                        
                                    pStream = ctypes.cast(stg_fc.hGlobal, ctypes.POINTER(IStream))
                                    with open(dst_path, "wb") as f:
                                        buf = ctypes.create_string_buffer(8192)
                                        cbRead = wintypes.ULONG(0)
                                        while True:
                                            hr_read = pStream.contents.lpVtbl.contents.Read(pStream, buf, 8192, ctypes.byref(cbRead))
                                            if cbRead.value > 0:
                                                f.write(buf.raw[:cbRead.value])
                                            if hr_read != 0 or cbRead.value == 0:
                                                break
                                    copied += 1
                                    ole32.ReleaseStgMedium(ctypes.byref(stg_fc))
                                else:
                                    errors.append(f"{name}: 不支持的传输介质 ({stg_fc.tymed})")
                                    ole32.ReleaseStgMedium(ctypes.byref(stg_fc))
                            else:
                                errors.append(f"{name}: 无法获取文件内容 (HRESULT: {hr_fc})")
                                
                    finally:
                        kernel32.GlobalUnlock(stg_fgd.hGlobal)
                ole32.ReleaseStgMedium(ctypes.byref(stg_fgd))
                
        finally:
            pDataObj.contents.lpVtbl.contents.Release(pDataObj)
            
        return copied, errors
    except Exception as e:
        return 0, [str(e)]
