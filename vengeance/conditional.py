
import os
import sys
from collections import OrderedDict

python_version      = sys.version_info
is_pypy_interpreter = ('__pypy__' in sys.builtin_module_names)
is_windows_os       = (os.name == 'nt')
is_tty_console      = (hasattr(sys.stdout, 'isatty') and sys.stdout.isatty())
is_utf_console      = ('utf' in sys.stdout.encoding.lower())

''' ordereddict:
    starting at python 3.6 the built-in dict is both 
    insertion-ordered AND compact, using about half the 
    memory of collections.OrderedDict
'''
if python_version >= (3, 6):
    ordereddict = dict
else:
    ordereddict = OrderedDict

try:
    import _pickle as cpickle
except ImportError:
    import pickle as cpickle

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

# is_pypy_interpreter     = True
# is_windows_os           = True
# dateutil_installed      = False
# ultrajson_installed     = False
# line_profiler_installed = False

# determines if excel_com module should be loaded in __init__
loads_excel_module = (not is_pypy_interpreter) and is_windows_os


