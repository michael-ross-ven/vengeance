
import os
import sys

''' 
config: 
    default settings for vengeance.util functions
    eg:
        [console]
        effect = bold
        enable_ansi_escape = True
        formatter = {vengeance_prefix}@{name}: {elapsed}

loads_excel_module: 
    determines if excel_com module should be loaded in vengeance.__init__ 
    if environment is expected to support Windows COM interface, load vengeance.excel_com module
    
    vengeance.excel_com functions:
        vengeance.open_workbook
        vengeance.close_workbook
        vengeance.excel_levity_cls
        etc ...

ordereddict:
    starting at python 3.6, the built-in dict is both insertion-ordered and compact, 
    using about half the memory of collections.OrderedDict 

'''
config = {}

python_version      = sys.version_info
is_pypy_interpreter = ('__pypy__' in iter(sys.builtin_module_names))
is_windows_os       = (os.name == 'nt')
is_utf_console      = ('utf' in sys.stdout.encoding.lower())
is_tty_console      = False
loads_excel_module  = (not is_pypy_interpreter) and is_windows_os

ordereddict             = dict
dateutil_installed      = False
ultrajson_installed     = False
numpy_installed         = False
line_profiler_installed = False


if python_version < (3, 6):
    from collections import OrderedDict
    ordereddict = OrderedDict

if python_version < (3, 9):
    try:
        import ujson
        ultrajson_installed = True
    except ImportError:
        pass

try:
    import dateutil
    dateutil_installed = True
except ImportError:
    pass

try:
    import numpy
    numpy_installed = True
except ImportError:
    pass

try:
    import line_profiler
    line_profiler_installed = True
except ImportError:
    pass


def enable_ansi_escape_in_console():
    """ attempt to turn on ansi escape colors in console

    ansi escape: \x1b, \033, <0x1b>, 
    how to effectively check if console supports ansi escapes?
        ansi escape shows up as '←' in python.exe console

    STD_OUTPUT_HANDLE = -11
    DWMODE            = 7
    """
    global is_utf_console
    global is_tty_console

    if not is_windows_os:
        return

    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)

        is_utf_console = True
        is_tty_console = False
    except:
        pass


def read_config_file():
    config_path = __locate_config_path()
    if config_path is None:
        return

    global config
    from configparser import ConfigParser

    cp = ConfigParser()
    cp.read(config_path)

    if cp.has_section('console'):
        cp_section = cp['console']

        config.update({'color':     cp_section.get('color'),
                       'effect':    cp_section.get('effect'),
                       'formatter': cp_section.get('formatter')})

        if cp_section.getboolean('enable_ansi_escape'):
            enable_ansi_escape_in_console()

    # if cp.has_section('filesystem'):
    #     cp_section = cp['filesystem']
    #     config.update({'encoding': cp_section.get('encoding')})


def __locate_config_path():
    import site

    config_paths = [site.getsitepackages()[1] + '\\vengeance\\config.ini']
    if is_windows_os:
        config_paths.append(os.environ['localappdata'] + '\\Temp\\vengeance\\config.ini')

    for config_path in config_paths:
        if os.path.exists(config_path):
            return config_path

    return None


# read_config_file()

# is_tty_console          = (hasattr(sys.stdout, 'isatty') and sys.stdout.isatty())
# is_pypy_interpreter     = True
# is_windows_os           = True
# dateutil_installed      = False
# ultrajson_installed     = False
# numpy_installed         = False
# line_profiler_installed = False
# loads_excel_module      = False


