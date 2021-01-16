
""" import vengeance as ven """

from .version import *
from .util import *
from .classes import *
from .conditional import loads_excel_module

''' 
attempt to load Excel module, but allow it to fail if it's not expected to support Windows COM
loads_excel_module = (not is_pypy_interpreter) and is_windows_os
    
    vgc.open_workbook, 
    vgc.close_workbook,
    vgc.excel_levity_cls, 
    etc 
'''
if loads_excel_module:
    from .excel_com import *
