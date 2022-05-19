#!python3
# -*- coding: utf-8 -*-

"""
import vengeance as ven
import vengeance as vgc
"""
from .conditional import loads_excel_module

from .version import *
from .util    import *
from .classes import *

if loads_excel_module:
    from .excel_com import *

del loads_excel_module

