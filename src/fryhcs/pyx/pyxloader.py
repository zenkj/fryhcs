"""
扩展python import机制，直接import pyx文件，在线转换成py文件，然后编译为.pyc文件直接执行。
"""
import sys
from importlib.machinery import FileFinder, SourceFileLoader
from importlib._bootstrap_external import _get_supported_file_loaders
from .generator import pyx_to_py

PYXSOURCE_SUFFIXES = ['.pyx']

class PyxSourceFileLoader(SourceFileLoader):
    def source_to_code(self, data, path, *, _optimize=-1):
        data = pyx_to_py(data.decode())
        print(data)
        return super(SourceFileLoader, self).source_to_code(data, path, _optimize=_optimize)

def install_path_hook():
    if sys.path_hooks and hasattr(sys.path_hooks[0], 'fryhcs'):
        return
    loader_details = [(PyxSourceFileLoader, PYXSOURCE_SUFFIXES)] + _get_supported_file_loaders()
    factory_func = FileFinder.path_hook(*loader_details)
    setattr(factory_func, 'fryhcs', True)
    sys.path_hooks.insert(0, factory_func)

    # 清空已有的PathEntryFinder缓存
    sys.path_importer_cache.clear()
