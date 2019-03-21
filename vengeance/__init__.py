
__import_error = False

try:
    from . version import __version__
    from . util import *
    from . classes import *
    from . excel_com import *

except ImportError as e:
    import warnings
    from time import sleep
    from . version import dependencies

    __import_error = True

    errs = ['\n\n*** vengeance import failure: {} ***'.format(e)]
    for dependency in dependencies:
        try:
            __import__(dependency)
        except ImportError as de:
            errs.append('*** (dependency not installed: {}) ***\n'.format(de))

    warnings.warn('\n'.join(errs))
    sleep(0.5)


if __import_error:
    raise ImportError('can not import vengeance')

del __import_error
