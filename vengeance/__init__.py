#!python3
# -*- coding: utf-8 -*-

"""
But rather give place to wrath, for it is written: 'vengeance is mine, I shall repay'
"""
from .conditional import loads_excel_module

from .version import *
from .util    import *
from .classes import *

if loads_excel_module:
    from .excel_com import *

del loads_excel_module

