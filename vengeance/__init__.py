
try:
    from . version import __version__
    from . util import *
    from . classes import *
    from . excel_com import *

except ModuleNotFoundError as e:
    raise ModuleNotFoundError('\n\n\n*** vengeance import failure: {} ***\n'.format(e)) from e

except ImportError as e:
    raise ImportError('\n\n\n*** vengeance import failure: {} ***\n'.format(e)) from e


