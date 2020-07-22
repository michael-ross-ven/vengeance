
import sys
if sys.version_info < (3,):
    raise ImportError('\n\n\n*** vengeance import failure *** \nonly Python 3+ version supported\n')

# import os
# if os.name != 'nt':
#     raise OSError('\n\n\n*** vengeance import failure *** \nonly Windows OS is supported\n')


try:
    from .version import __version__, __release__
    from .util import *
    from .classes import *
    from .excel_com import *
except ModuleNotFoundError as e:
    raise ModuleNotFoundError('\n\n\n*** vengeance module import failure *** \n{}\n'.format(e)) from e
except ImportError as e:
    raise ImportError('\n\n\n*** vengeance import failure *** \n{}\n'.format(e)) from e


