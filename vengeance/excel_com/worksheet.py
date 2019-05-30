
# noinspection PyUnresolvedReferences
from pythoncom import com_error

from datetime import date
from datetime import datetime

from .. util.iter import modify_iteration_depth

from .. excel_com.excel_address import col_letter
from .. excel_com.excel_address import col_number
from .. excel_com.excel_address import max_cols as excel_max_cols
from .. excel_com.excel_address import max_rows as excel_max_rows

from . workbook import app_to_foreground
from . excel_constants import *


def get_worksheet(wb,
                  ws_name,
                  *,
                  clear_filter=False,
                  activate=False):

    if ws_name.__class__.__name__ in {'CDispatch', '_Worksheet'}:
        return ws_name

    if wb is None:
        raise AssertionError("Excel workbook has not been initialized! Cannot retrieve tab: '{}'".format(ws_name))

    try:
        ws = wb.Sheets[ws_name]
    except com_error as e:
        raise NameError("'{}' worksheet not found in '{}'".format(ws_name, wb.Name)) from e

    if clear_filter:
        clear_worksheet_filter(ws)

    if activate:
        ws.Visible = True
        app_to_foreground(ws.Application)
        ws.Activate()

    return ws


def first_row(excel_range, default_r=1):
    search = range_find(excel_range,
                        what='*',
                        look_at=xlPart,
                        search_order=xlByRows,
                        search_direction=xlNext)

    if search:
        r = max(search.Row, default_r)
    else:
        r = default_r

    return r


def last_row(excel_range, default_r=1):
    search = range_find(excel_range,
                        what='*',
                        look_at=xlPart,
                        search_order=xlByRows,
                        search_direction=xlPrevious)

    if search:
        r = max(search.Row, default_r)
    else:
        r = default_r

    return r


def first_col(excel_range, default_c='A'):
    search = range_find(excel_range,
                        what='*',
                        look_at=xlPart,
                        search_order=xlByColumns,
                        search_direction=xlNext)

    if search:
        c = max(search.Column, col_number(default_c))
        c_lttr = col_letter(c)
    else:
        c_lttr = default_c

    return c_lttr


def last_col(excel_range, default_c='A'):
    search = range_find(excel_range,
                        what='*',
                        look_at=xlPart,
                        search_order=xlByColumns,
                        search_direction=xlPrevious)

    if search:
        c = max(search.Column, col_number(default_c))
        c_lttr = col_letter(c)
    else:
        c_lttr = default_c

    return c_lttr


def range_find(excel_range,
               what,
               after=None,
               look_in=xlValues,
               look_at=xlWhole,
               search_order=xlByRows,
               search_direction=xlPrevious,
               match_case=False):

    if after is None:
        if search_direction == xlNext:
            after = last_cell(excel_range)
        elif search_direction == xlPrevious:
            after = first_cell(excel_range)

    search = excel_range.Find(what,
                              after,
                              look_in,
                              look_at,
                              search_order,
                              search_direction,
                              match_case)

    return search


def first_cell(excel_range):
    return excel_range.Cells(1)


def last_cell(excel_range):
    """ excel_range.Cells(excel_range.Cells.Count) causes an overflow error
    this is not always reliable when excel_range.Cells() requires both row and column arguments
    """
    a = excel_range.Address.split(':')[-1]
    return excel_range.Parent.Range(a)


def is_filtered(ws):
    if ws.AutoFilter is not None:
        return ws.AutoFilter.FilterMode


# noinspection PyProtectedMember
def clear_worksheet_filter(ws):
    if is_filtered(ws):
        ws._AutoFilter.ShowAllData()


def is_range_empty(excel_range):
    num_blank = excel_range.Application.WorksheetFunction.CountBlank(excel_range)
    num_cells = excel_range.Cells.Count

    return num_blank == num_cells


def activate_sheet(ws):
    app_to_foreground(ws.Application)
    ws.Visible = True
    ws.Activate()


def write_to_excel_range(v, excel_range):
    m = modify_iteration_depth(v, 2)
    m = list(__excel_friendly_matrix(m))

    a = excel_range.Address
    if ':' not in a:
        a = '{}:{}'.format(a, excel_range.Resize(len(m), len(m[0])).Address)
    else:
        a = excel_range.Resize(len(m), len(m[0])).Address

    excel_range.Parent.Range(a).Value = m


def gen_range_rows(excel_range):
    for row in __convert_excel_errors(excel_range):
        yield row


def __convert_excel_errors(excel_range):
    m = excel_range.Value
    m = modify_iteration_depth(m, 2)
    m = [list(row) for row in m]

    try:
        range_errors = excel_range.SpecialCells(xlCellTypeFormulas, xlErrors)
        cell = first_cell(excel_range)
        r_0  = cell.Row
        c_0  = cell.Column

        for cell_error in range_errors:
            r = cell_error.Row - r_0
            c = cell_error.Column - c_0
            m[r][c] = excel_errors.get(m[r][c], 'unknown error')

    except com_error:
        pass

    return m


def __excel_friendly_matrix(m):
    """ modify matrix values so they can be written to an excel range without error """
    num_cols = len(m[0])

    if num_cols > excel_max_cols:
        raise ValueError("number of columns ({:,}) exceeds Excel's column limit\n"
                         "(did you mean to transpose this matrix?)".format(num_cols))

    if len(m) > excel_max_rows:
        raise ValueError("number of rows ({:,}) exceeds Excel's row limit".format(len(m)))

    for r, row in enumerate(m):
        if len(row) != num_cols:
            raise ValueError('jagged column (at row {:,}), cannot write to Excel'.format(r))

        row_ = []
        for c, v in enumerate(row):
            if isinstance(v, (bool, int, float, str)) or v is None:
                pass
            elif isinstance(v, date):
                v = datetime(v.year, v.month, v.day)
            else:
                v = repr(v)

            row_.append(v)

        yield row_


def parse_range(excel_range):
    c_1 = first_cell(excel_range).Column
    c_1 = col_letter(c_1)

    c_2 = last_cell(excel_range).Column
    c_2 = col_letter(c_2)

    r_1 = first_cell(excel_range).Row
    r_2 = last_cell(excel_range).Row

    return c_1, r_1, c_2, r_2

