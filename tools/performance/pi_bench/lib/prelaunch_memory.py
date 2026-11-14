"""Symmetric prelaunch allocator release and compact parent/system observations."""
import ctypes,gc,os,re,time
from pathlib import Path

def process_snapshot():
 return {'time':time.time(),'pid':os.getpid(),'status':Path('/proc/self/status').read_text(),'proc_stat':Path('/proc/self/stat').read_text()}

def snapshot():
 out={'time':time.time(),'pid':os.getpid()}
 for name,path in [('status','/proc/self/status'),('mem','/proc/meminfo'),('vm','/proc/vmstat')]:out[name]=Path(path).read_text()
 return out

def release():
 before=snapshot();collected=gc.collect();lib=ctypes.CDLL(None);trim=getattr(lib,'malloc_trim',None)
 if trim:trim.argtypes=[ctypes.c_size_t];trim.restype=ctypes.c_int
 result=trim(0)if trim else None
 return {'before':before,'gc_collected':collected,'malloc_trim_available':bool(trim),'malloc_trim_return':result,'after':snapshot(),'scope':'Parent allocator only, before engine launch; no swap/CMA/cache/sysctl changes.'}
