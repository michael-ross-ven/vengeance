
import os
import vengeance
from vengeance import flux_cls
from vengeance import excel_levity_cls

wb = None
__levs = {}

project_dir = os.getcwd() + '\\files\\'


def open_project_workbook(open_new_instance=True, read_only=False, update_links=True):
    global wb

    if wb is not None:
        return

    if open_new_instance:
        excel_app = None
    else:
        excel_app = 'any'

    f_dir  = project_dir
    f_name = 'example.xlsm'
    wb = vengeance.open_workbook(f_dir + f_name,
                                 excel_app,
                                 read_only=read_only,
                                 update_links=update_links)


def close_project_workbook(save=True):
    global wb

    if wb is None:
        return

    vengeance.close_workbook(wb, save)
    wb = None


def worksheet_to_lev(ws,
                     header_r=2,
                     meta_r=1,
                     first_c='B',
                     last_c=None):

    global __levs

    if isinstance(ws, excel_levity_cls):
        ws_name = ws.sheet_name.lower()
    elif hasattr(ws, 'Name'):
        ws_name = ws.Name.lower()
    else:
        ws_name = ws.lower()
        if ws_name in {'sheet1', 'empty sheet'}:
            header_r = 1
            meta_r   = 0
            first_c = 'A'

    k = (ws_name,
         header_r,
         meta_r,
         first_c,
         last_c)

    if k in __levs:
        lev = __levs[k]
    else:
        ws  = vengeance.get_worksheet(wb, ws)
        lev = excel_levity_cls(ws,
                               meta_r=meta_r,
                               header_r=header_r,
                               first_c=first_c,
                               last_c=last_c)
        __levs[k] = lev

    return lev


def lev_subsection(tab_name, c_1, c_2, header_r=2, meta_r=1):
    ws = vengeance.get_worksheet(wb, tab_name)

    headers = {**excel_levity_cls.index_headers(ws, meta_r),
               **excel_levity_cls.index_headers(ws, header_r)}

    c_1 = headers.get(c_1, c_1)
    c_2 = headers.get(c_2, c_2)

    return excel_levity_cls(ws,
                            meta_r=meta_r,
                            header_r=header_r,
                            first_c=c_1,
                            last_c=c_2)


def worksheet_to_flux(ws,
                      header_r=2,
                      meta_r=1,
                      first_c='B'):

    lev = worksheet_to_lev(ws, header_r, meta_r, first_c)
    return flux_cls(lev)


def write_to_worksheet(tab_name, m, r_1='*h', c_1=None, c_2=None):
    if c_1 is not None:
        lev = lev_subsection(tab_name, c_1, c_2)
    else:
        lev = worksheet_to_lev(tab_name)

    lev.activate()
    was_filtered = lev.has_filter

    if r_1 != '*a':
        a = '*f {}:*l *l'.format(r_1)
        lev.clear(a)

    a = '*f {}'.format(r_1)
    lev[a] = m

    if was_filtered:
        lev.reapply_filter()





