
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
        vengeance.lev_cls
        etc ...

ordereddict:
    starting at python 3.6, the built-in dict is both insertion-ordered and compact, 
    using about half the memory of collections.OrderedDict 

'''
config             = {}
config_file_loaded = False

python_version      = sys.version_info
is_windows_os       = (os.name == 'nt' or sys.platform == 'win32')
is_utf_console      = ('utf' in sys.stdout.encoding.lower())
is_pypy_interpreter = ('__pypy__' in sys.builtin_module_names)
loads_excel_module  = (not is_pypy_interpreter and is_windows_os)

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


def load_vengeance_configuration_file():
    """
    sys.getfilesystemencoding()
    locale.getpreferredencoding()

    if cp.has_section('filesystem'):
        cp_section = cp['filesystem']
        config.update({'encoding': cp_section.get('encoding')})
    """
    global config
    global config_file_loaded

    vcf = __load_vengeance_configuration_file()
    if vcf is None:
        return

    if vcf.has_section('console'):
        cp_section = vcf['console']
        config.update({'color':              cp_section.get('color'),
                       'effect':             cp_section.get('effect'),
                       'formatter':          cp_section.get('formatter'),
                       'enable_ansi_escape': cp_section.getboolean('enable_ansi_escape')})

        if config['enable_ansi_escape']:
            __enable_ansi_escape_in_windows_console()

    config_file_loaded = True


def __load_vengeance_configuration_file():
    import site

    config_paths = [site.getsitepackages()[1]  + '\\vengeance\\config.ini']

    if is_windows_os:
        try:    config_paths.append(os.environ['localappdata'] + '\\Temp\\vengeance\\config.ini')
        except: pass

    for config_path in config_paths:
        if os.path.exists(config_path):
            from configparser import ConfigParser

            vcf = ConfigParser()
            vcf.read(config_path)

            return vcf

    return None


def __enable_ansi_escape_in_windows_console():
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

    # GetConsoleMode = ctypes.windll.kernel32.GetConsoleMode
    # print(f'{GetConsoleMode(STD_OUTPUT_HANDLE) = }')
    """
    if not is_windows_os:
        return

    try:
        import ctypes
        global is_utf_console

        SetConsoleMode    = ctypes.windll.kernel32.SetConsoleMode
        GetStdHandle      = ctypes.windll.kernel32.GetStdHandle
        STD_OUTPUT_HANDLE = -11
        DWMODE            = 7

        SetConsoleMode(GetStdHandle(STD_OUTPUT_HANDLE), DWMODE)
        is_utf_console = True

    except:
        is_utf_console = False


if config_file_loaded is False:
    load_vengeance_configuration_file()


# is_pypy_interpreter     = True
# is_windows_os           = True
# dateutil_installed      = False
# ultrajson_installed     = False
# numpy_installed         = False
# line_profiler_installed = False
# loads_excel_module      = False


