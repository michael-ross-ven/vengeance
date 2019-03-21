
import os
import vengeance

wb = None
project_dir = os.getcwd() + '\\files\\'


def open_project_workbook(open_new_instance=True, read_only=False, update_links=True):
    global wb

    if wb is not None:
        return

    if open_new_instance:
        excel_app = None
    else:
        excel_app = vengeance.any_excel_instance()

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


def tab_to_lev(tab, header_r=2, meta_r=1, first_c='B', clear_filter=True):
    if isinstance(tab, vengeance.excel_levity_cls):
        return tab

    if isinstance(tab, str):
        if tab.lower() == 'sheet1' or tab.lower() == 'empty sheet':
            header_r = 1
            meta_r   = 0
            first_c = 'A'

    ws = vengeance.get_worksheet(wb, tab)
    lev = vengeance.excel_levity_cls(ws,
                                     meta_r=meta_r,
                                     header_r=header_r,
                                     first_c=first_c)
    if clear_filter:
        lev.clear_filter()

    return lev


def lev_subsection(tab_name, c_1, c_2, header_r=2, meta_r=1):
    ws = vengeance.get_worksheet(wb, tab_name)

    headers = {**vengeance.excel_levity_cls.index_headers(ws, meta_r),
               **vengeance.excel_levity_cls.index_headers(ws, header_r)}

    c_1 = headers.get(c_1, c_1)
    c_2 = headers.get(c_2, c_2)

    return vengeance.excel_levity_cls(ws,
                                      meta_r=meta_r,
                                      header_r=header_r,
                                      first_c=c_1,
                                      last_c=c_2)


def tab_to_flux(tab_name, header_r=2, meta_r=1, first_c='B'):
    lev = tab_to_lev(tab_name,
                     header_r,
                     meta_r,
                     first_c)

    return vengeance.flux_cls(lev)


def write_to_tab(tab_name, m, r_1='*h', c_1=None, c_2=None):
    if c_1 is not None:
        lev = lev_subsection(tab_name, c_1, c_2)
    else:
        lev = tab_to_lev(tab_name)

    lev.activate()
    if r_1 != '*a':
        lev.clear('*f {}:*l *l'.format(r_1))

    lev['*f ' + str(r_1)] = m





