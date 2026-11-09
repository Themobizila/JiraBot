"""Utilitários Win32 para instância e janela próprias do aplicativo."""
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import hashlib
from pathlib import Path
import sys


@contextmanager
def single_instance(kind, base):
    if sys.platform != "win32":
        yield True
        return
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    key = hashlib.sha256(str(Path(base).resolve()).lower().encode()).hexdigest()[:24]
    ctypes.set_last_error(0)
    handle = kernel.CreateMutexW(None, False, "Local\\JiraBot_" + kind + "_" + key)
    if not handle:
        raise OSError("Não foi possível reservar a instância da janela.")
    owned = ctypes.get_last_error() != 183
    try:
        yield owned
    finally:
        kernel.CloseHandle(handle)


def root_handle(root):
    user = ctypes.windll.user32
    user.GetParent.argtypes = [wintypes.HWND]
    user.GetParent.restype = wintypes.HWND
    return user.GetParent(root.winfo_id()) or root.winfo_id()


def show_sprite(root, x, y, width, height, borderless=True):
    """Mapeia uma janela Tk gerenciada antes de remover sua moldura nativa."""
    if not root.winfo_viewable():
        root.deiconify()
    root.update_idletasks()
    if sys.platform != "win32":
        return bool(root.winfo_viewable())
    user = ctypes.windll.user32
    hwnd = root_handle(root)
    changed = False
    if borderless:
        get_style = user.GetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8 else user.GetWindowLongW
        set_style = user.SetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8 else user.SetWindowLongW
        get_style.argtypes = [wintypes.HWND, ctypes.c_int]
        get_style.restype = ctypes.c_ssize_t
        set_style.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
        set_style.restype = ctypes.c_ssize_t
        style = get_style(hwnd, -16)
        style &= ~(0x00C00000 | 0x00040000 | 0x00080000 | 0x00020000 | 0x00010000)
        target_style = style | 0x80000000
        if get_style(hwnd, -16) != ctypes.c_ssize_t(target_style).value:
            set_style(hwnd, -16, target_style)
            changed = True
        extended = get_style(hwnd, -20)
        target_extended = (extended | 0x80) & ~0x40000
        if extended != target_extended:
            set_style(hwnd, -20, target_extended)
            changed = True
    user.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user.IsWindowVisible.argtypes = [wintypes.HWND]
    user.IsWindowVisible.restype = wintypes.BOOL
    visible = bool(user.IsWindowVisible(hwnd))
    user.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    rect = wintypes.RECT()
    positioned = user.GetWindowRect(hwnd, ctypes.byref(rect)) and (rect.left, rect.top) == (x, y)
    sized = not borderless or (rect.right - rect.left, rect.bottom - rect.top) == (width, height)
    if visible and not changed and positioned and sized:
        return True
    if not visible:
        user.ShowWindow(hwnd, 4)  # SW_SHOWNOACTIVATE
    flags = 0x0010 | 0x0040  # NOACTIVATE, SHOWWINDOW
    if changed:
        flags |= 0x0020  # FRAMECHANGED somente ao configurar a moldura.
    if not borderless:
        flags |= 0x0001  # Mantém a moldura e o tamanho da demonstração.
    user.SetWindowPos(hwnd, wintypes.HWND(-1), x, y, width, height, flags)
    return bool(user.IsWindowVisible(hwnd))
