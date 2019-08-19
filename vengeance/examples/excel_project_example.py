
import os

from vengeance import open_workbook
from vengeance import close_workbook
from vengeance import get_worksheet
from vengeance import flux_cls
from vengeance import excel_levity_cls

wb = None
__levs = {}

project_dir = os.getcwd() + '\\files\\'


def open_project_workbook(open_new_instance=True,
                          read_only=False,
                          update_links=True):
    global wb

    if wb is not None:
        return

    if open_new_instance:
        excel_app = None
    else:
        excel_app = 'any'

    wb = open_workbook(project_dir + 'example.xlsm',
                       excel_app,
                       read_only=read_only,
                       update_links=update_links)


def close_project_workbook(save=True):
    global wb

    if wb is None:
        return

    close_workbook(wb, save)
    wb = None


def worksheet_to_lev(ws,
                     meta_r=1,
                     header_r=2,
                     c_1=None,
                     c_2=None):

    global __levs

    if isinstance(ws, str):
        ws_name = ws.lower()
    elif isinstance(ws, excel_levity_cls):
        ws = ws.worksheet
        ws_name = ws.Name
    elif ws.__class__.__name__ in {'CDispatch', '_Worksheet'}:
        ws = ws
        ws_name = ws.Name
    else:
        ws_name = ws

    if ws_name in {'sheet1', 'empty sheet'}:
        header_r = 1
        meta_r   = 0
    else:
        c_1 = c_1 or 'B'

    k = (ws_name,
         meta_r,
         header_r,
         c_1,
         c_2)

    if k in __levs:
        return __levs[k]

    ws = get_worksheet(wb, ws)

    headers = {}
    if (c_1 or c_2) and (header_r > 0):
        headers.update(excel_levity_cls.index_headers(ws, header_r))
    if (c_1 or c_2) and (meta_r > 0):
        headers.update(excel_levity_cls.index_headers(ws, meta_r))

    c_1 = headers.get(c_1, c_1)
    c_2 = headers.get(c_2, c_2)

    lev = excel_levity_cls(ws,
                           meta_r=meta_r,
                           header_r=header_r,
                           first_c=c_1,
                           last_c=c_2)
    __levs[k] = lev

    return lev


def worksheet_to_flux(ws,
                      meta_r=1,
                      header_r=2,
                      c_1=None,
                      c_2=None):

    lev = worksheet_to_lev(ws,
                           meta_r,
                           header_r,
                           c_1,
                           c_2)
    return flux_cls(lev)


def write_to_worksheet(ws,
                       m,
                       r_1='*h',
                       c_1='B',
                       c_2=None):

    lev = worksheet_to_lev(ws, c_1=c_1, c_2=c_2)
    lev.activate()

    was_filtered = lev.has_filter

    if r_1 != '*a':
        lev.clear('*f %s:*l *l' % r_1)

    lev['*f %s' % r_1] = m

    if was_filtered:
        lev.reapply_filter()







