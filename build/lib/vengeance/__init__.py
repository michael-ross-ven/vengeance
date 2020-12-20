
# import sys


def format_error_message(m):
    return '\n*** vengeance import failure *** \n{}\n'.format(m)


# if sys.version_info < (3,):
#     raise ImportError(format_error_message('only Python 3+ version supported'))

try:
    from .version import __version__, __release__
    from .util import *
    from .classes import *

    from .conditional import is_pypy
except ModuleNotFoundError as e:
    raise ModuleNotFoundError(format_error_message(e)) from e
except ImportError as e:
    raise ImportError(format_error_message(e)) from e

try:
    from .excel_com import *
except ImportError as e:
    pass
