
""" determine which site-packages and python interpreter version are installed """

import sys
from collections import OrderedDict

""" ordereddict:
    starting at python 3.6 the built-in dict is both 
    insertion-ordered AND compact, using about half the 
    memory of collections.OrderedDict
"""
if sys.version_info >= (3, 6):
    ordereddict = dict
else:
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


# dateutil_installed      = False
# ultrajson_installed     = False
# line_profiler_installed = False

