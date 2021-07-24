
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
config          = {}
config_already_read = False

python_version      = sys.version_info
is_windows_os       = (os.name == 'nt') or (sys.platform == 'win32')
is_utf_console      = ('utf' in sys.stdout.encoding.lower())
is_pypy_interpreter = ('__pypy__' in sys.builtin_module_names)
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

    # os.popen('chcp 65001')

    import codecs
    import locale
    a = codecs.getwriter(locale.getpreferredencoding())(sys.stdout)

    STD_OUTPUT_HANDLE = -11
    DWMODE            = 7
    """
    global is_utf_console

    if not is_windows_os:
        return

    try:
        import ctypes

        SetConsoleMode    = ctypes.windll.kernel32.SetConsoleMode
        GetStdHandle      = ctypes.windll.kernel32.GetStdHandle
        STD_OUTPUT_HANDLE = -11
        DWMODE            = 7

        SetConsoleMode(GetStdHandle(STD_OUTPUT_HANDLE), DWMODE)

        is_utf_console = True
        # is_utf_console =('utf' in sys.stdout.encoding.lower())
    except:
        pass


def read_config_file():
    global config
    global config_already_read
    from configparser import ConfigParser

    config_already_read = True

    config_path = __locate_config_path()
    if config_path is None:
        return

    cp = ConfigParser()
    cp.read(config_path)

    if cp.has_section('console'):
        cp_section = cp['console']

        config.update({'color':              cp_section.get('color'),
                       'effect':             cp_section.get('effect'),
                       'formatter':          cp_section.get('formatter'),
                       'enable_ansi_escape': cp_section.getboolean('enable_ansi_escape')})

        if config['enable_ansi_escape']:
            enable_ansi_escape_in_console()

    # sys.getfilesystemencoding()

    # if cp.has_section('filesystem'):
    #     cp_section = cp['filesystem']
    #     config.update({'encoding': cp_section.get('encoding')})


def __locate_config_path():
    import site

    config_paths = [site.getsitepackages()[1]  + '\\vengeance\\config.ini',
                    os.environ['localappdata'] + '\\Temp\\vengeance\\config.ini']
    if not is_windows_os:
        del config_paths[-1]

    for config_path in config_paths:
        if os.path.exists(config_path):
            return config_path

    return None


if config_already_read is False:
    read_config_file()

# is_pypy_interpreter     = True
# is_windows_os           = True
# dateutil_installed      = False
# ultrajson_installed     = False
# numpy_installed         = False
# line_profiler_installed = False
# loads_excel_module      = False


