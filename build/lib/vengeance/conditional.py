
import os
import sys


is_pypy_interpreter = ('__pypy__' in iter(sys.builtin_module_names))
is_windows_os       = (os.name == 'nt')
is_utf_console      = ('utf' in sys.stdout.encoding.lower())
is_tty_console      = False


''' loads_excel_module: 
    determines if excel_com module should be loaded in vengeance.__init__ 
'''
loads_excel_module = (not is_pypy_interpreter) and is_windows_os

''' ordereddict:
    starting at python 3.6, the built-in dict is both insertion-ordered and compact, 
    using about half the memory of collections.OrderedDict 
'''
if sys.version_info >= (3, 6):
    ordereddict = dict
else:
    from collections import OrderedDict
    ordereddict = OrderedDict

try:
    import dateutil
    dateutil_installed = True
except ImportError:
    dateutil_installed = False

try:
    import ujson
    ultrajson_installed = True
except ImportError:
    ultrajson_installed = False

try:
    import numpy
    numpy_installed = True
except ImportError:
    numpy_installed = False

try:
    import line_profiler
    line_profiler_installed = True
except ImportError:
    line_profiler_installed = False


# is_tty_console          = (hasattr(sys.stdout, 'isatty') and sys.stdout.isatty())
# is_pypy_interpreter     = True
# is_windows_os           = True
# dateutil_installed      = False
# ultrajson_installed     = False
# numpy_installed         = False
# line_profiler_installed = False
# loads_excel_module      = False


