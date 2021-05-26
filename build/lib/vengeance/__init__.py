
"""
import vengeance as ven
import vengeance as vgc
"""

from .version import *
from .util    import *
from .classes import *
from .conditional import loads_excel_module

''' loads_excel_module
    if environment is expected to support Windows COM interface, load excel_com module
    loads_excel_module = (not is_pypy_interpreter) and is_windows_os
    
    excel_com imports:
        vengeance.open_workbook
        vengeance.close_workbook
        vengeance.excel_levity_cls
        etc ...
'''
if loads_excel_module:
    from .excel_com import *



