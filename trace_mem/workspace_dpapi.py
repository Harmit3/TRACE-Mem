"""Current-user Windows DPAPI for portable beta memory snapshots."""
import ctypes
from ctypes import wintypes


class Blob(ctypes.Structure):
    _fields_ = [("size",wintypes.DWORD),("data",ctypes.c_void_p)]


def transform(raw, *, decrypt=False):
    buf=ctypes.create_string_buffer(raw)
    source=Blob(len(raw),ctypes.cast(buf,ctypes.c_void_p))
    result=Blob()
    api=ctypes.WinDLL("crypt32",use_last_error=True)
    call=api.CryptUnprotectData if decrypt else api.CryptProtectData
    if not call(ctypes.byref(source),None,None,None,None,1,ctypes.byref(result)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(result.data,result.size)
    finally:
        ctypes.windll.kernel32.LocalFree(ctypes.c_void_p(result.data))
