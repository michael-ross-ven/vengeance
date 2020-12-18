import sys
if sys.version_info < (3,):
    raise ImportError('\n*** vengeance import failure *** \nonly Python 3+ version supported\n')

try:
    from .version import __version__, __release__
    from .util import *
    from .classes import *
    from .excel_com import *
except ModuleNotFoundError as e:
    raise ModuleNotFoundError('\n*** vengeance module import failure *** \n{}\n'.format(e)) from e
except ImportError as e:
    raise ImportError('\n*** vengeance import failure *** \n{}\n'.format(e)) from e


