
import re

# noinspection PyUnresolvedReferences
from pythoncom import com_error as pythoncom_error

from typing import Generator
from typing import List
from typing import Any

from ... classes.flux_row_cls import flux_row_cls

from .. import excel_address
from .. import worksheet
from .. excel_constants import *

from ... util.iter import iterator_to_collection
from ... util.iter import map_values_to_enum
from ... util.iter import modify_iteration_depth
from ... util.text import object_name

from ... conditional import ordereddict


class lev_cls:
    """ data management class for worksheets
    https://github.com/michael-ross-ven/vengeance_example/blob/main/excel_example.py

    ★ automatic range boundary detection

    lev_cls range reference:
        lev['{col}{row}:{col}{row}']
        :returns a win32com reference to Excel range

        anchor reference mnemonics:
            '*h': header
            '*o': first
            '*l': last
            '*a': append

        a = lev['*f *h:*l *l'].Address

    eg:
        wb = vengeance.open_workbook('example.xlsm',
                                     excel_app='new',
                                     **kwargs)
        ws   = wb.Sheets[ws_name]
        lev = lev_cls(ws,
                      meta_r=1,
                      header_r=2,
                      first_c='A')

        for row in lev:
            a = row.col_a
            a = row['col_a']
            a = row[0]

        matrix = [['attribute_a', 'attribute_b', 'attribute_c'],
                  ['a',           'b',           'c'],
                  ['a',           'b',           'c'],
                  ['a',           'b',           'c']]

        lev.clear('*f *f:*l *l')
        lev['*f *h'] = matrix
    """
    allow_focus = False

    def __init__(self, ws, *,
                       first_c=None,
                       last_c=None,
                       meta_r=0,
                       header_r=0,
                       first_r=0,
                       last_r=0):

        if (not isinstance(meta_r, int) or
             not isinstance(header_r, int) or
             not isinstance(first_r, int) or
             not isinstance(last_r, int)):

            raise TypeError('row references must be integers')

        self.ws = ws
        if hasattr(ws, 'Name'):
            self.ws_name = ws.Name
        else:
            self.ws_name = "(no 'Name' attribute)"

        self.headers   = ordereddict()
        self.m_headers = ordereddict()

        self._named_ranges  = {}
        self._fixed_columns = (first_c, last_c)
        self._fixed_rows    = (first_r, last_r)

        self.first_c = first_c
        self.last_c  = last_c

        self.meta_r   = meta_r
        self.header_r = header_r
        self.first_r  = first_r
        self.last_r   = last_r

        self.set_range_boundaries(index_meta=True,
                                  index_header=True)

    @property
    def is_worksheet_type(self):
        """ ie,
            a chart that has been moved to its own worksheet will not be
            a true worksheet object
        """
        return worksheet.is_win32_worksheet_instance(self.ws)

    @staticmethod
    def col_letter_offset(col_str, offset):
        return excel_address.col_letter_offset(col_str, offset)

    @staticmethod
    def col_letter(col_int):
        return excel_address.col_letter(col_int)

    @staticmethod
    def col_number(col_str):
        return excel_address.col_number(col_str)

    @property
    def application(self):
        return self.ws.Application

    @property
    def workbook(self):
        return self.ws.Parent

    @property
    def named_ranges(self):
        if not self._named_ranges:
            self._named_ranges = _named_ranges_in_workbook(self.workbook)

        return self._named_ranges

    @property
    def worksheet(self):
        return self.ws

    @property
    def worksheet_name(self):
        return self.ws_name

    @property
    def meta_headers(self):
        return self.m_headers

    def header_names(self):
        return list(self.headers.keys())

    def meta_header_names(self):
        return list(self.m_headers.keys())

    @property
    def has_headers(self):
        if self.is_empty():
            return False

        return bool(self.headers) or bool(self.m_headers)

    @property
    def has_filter(self):
        if not self.is_worksheet_type:
            return False

        return bool(self.ws.AutoFilter)

    @property
    def first_empty_row(self):
        if self.is_empty():
            return self.header_r or self.meta_r or 1

        a = '{}{}:{}{}'.format(self.first_c, self.first_r,
                               self.last_c, self.first_r)
        first_data_row = self.ws.Range(a)

        if worksheet.is_range_empty(first_data_row):
            r = self.first_r
        else:
            r = self.last_r + 1

        return r

    @property
    def first_empty_column(self):
        """ determines the first available empty column in sheet """
        if self.is_empty():
            c = self.first_c
        else:
            c = excel_address.col_letter_offset(self.last_c, 1)

        return c

    @property
    def num_cols(self):
        return excel_address.col_number(self.last_c) - excel_address.col_number(self.first_c) + 1

    @property
    def num_rows(self):
        return int(self.last_r) - int(self.first_r) + 1

    def is_empty(self):
        if self.last_r > self.first_r:
            return False

        r_1 = self.header_r or self.meta_r or 1
        r_2 = self.last_r
        a = '{}{}:{}{}'.format(self.first_c, r_1, self.last_c, r_2)

        return worksheet.is_range_empty(self.ws.Range(a))

    def values(self, r_1='*h', r_2='*l') -> Generator[List, Any, Any]:
        if self.is_empty():
            return ([] for _ in range(1))

        a = '*f {}:*l {}'.format(r_1, r_2)
        excel_range = self.range(a)

        return (row for row in worksheet.escape_excel_range_errors(excel_range))

    def flux_rows(self, r_1='*h', r_2='*l') -> Generator[flux_row_cls, Any, Any]:
        if self.headers:
            headers = map_values_to_enum(self.headers.keys())
        elif self.m_headers:
            headers = map_values_to_enum(self.m_headers.keys())
        else:
            headers = ordereddict()

        if self.is_empty():
            return (flux_row_cls(headers, [], '') for _ in range(1))

        reserved = headers.keys() & set(flux_row_cls.reserved_names())
        if reserved:
            raise NameError("reserved name(s) {} found in header row {}"
                            .format(list(reserved), list(headers.keys())))

        a = '*f {}:*l {}'.format(r_1, r_2)
        excel_range = self.range(a)

        r_1 = excel_range.Row
        c_1, c_2 = self.first_c, self.last_c

        for r, row in enumerate(worksheet.escape_excel_range_errors(excel_range), r_1):
            a = '${}${}:${}${}'.format(c_1, r, c_2, r)
            yield flux_row_cls(headers, row, a)

    def activate(self):
        if self.allow_focus:
            worksheet.activate_worksheet(self.ws)

    def clear_filter(self):
        if not self.has_filter:
            return

        if worksheet.is_filtered(self.ws):
            self.set_range_boundaries()

    def remove_filter(self):
        if not self.has_filter:
            return

        self.ws.AutoFilterMode = False

    def reapply_filter(self, c_1='*f', c_2='*l'):
        if self.header_r > 0:
            r = '*h'
        else:
            r = '*f'

        a = '{} {}:{} {}'.format(c_1, r, c_2, r)
        excel_range = self.range(a)

        if excel_range.Cells.Count == 1:
            a = '{} {}:{} {}'.format(c_1, r, c_2, self.last_r + 1)
            excel_range = self.range(a)

        self.remove_filter()
        excel_range.AutoFilter(*(1,))

    def calculate(self):
        self.range('*f *h: *l *l').Calculate()

    def clear(self, reference,
                    clear_values=True,
                    clear_colors=False):

        excel_range = self.range(reference)
        _, r_1, _, r_2 = worksheet.parse_range(excel_range)

        if clear_values:
            excel_range.ClearContents()

            index_meta   = (r_1 <= self.meta_r)
            index_header = (r_1 <= self.header_r)
            self.set_range_boundaries(index_meta, index_header)

        if clear_colors:
            excel_range.Interior.Color = xlNone

    def set_range_boundaries(self, index_meta=True, index_header=True):
        """ find the edges of data in worksheet

        worksheet filter MUST be cleared from worksheet to
        determine these boundaries correctly
        """

        if not self.is_worksheet_type:
            self.first_c = ''
            self.last_c  = ''
            self.first_r = 0
            self.last_r  = 0
            return

        worksheet.clear_worksheet_filter(self.ws)
        self.__range_boundaries()

        if index_meta:
            self.__index_meta_columns()

        if index_header:
            self.__index_header_columns()

    def __range_boundaries(self):
        used_range = self.ws.UsedRange

        first_c, last_c = self._fixed_columns
        first_r, last_r = self._fixed_rows

        self.first_c = first_c or worksheet.first_col(used_range)
        self.last_c  = last_c  or worksheet.last_col(used_range, default=self.first_c)

        r_1 = max(self.meta_r, self.header_r) + 1
        r_2 = used_range.Rows.Count

        a = '{}{}:{}{}'.format(self.first_c, r_1,
                               self.last_c,  r_2)
        excel_range = self.ws.Range(a)

        self.first_r = first_r or worksheet.first_row(excel_range, default=r_1)
        self.last_r  = last_r  or worksheet.last_row(excel_range,  default=self.first_r)

        self.first_c = excel_address.col_letter(self.first_c)
        self.last_c  = excel_address.col_letter(self.last_c)
        self.first_r = int(self.first_r)
        self.last_r  = int(self.last_r)

    @classmethod
    def index_headers(cls, ws, row_int=None):
        if ws.__class__.__name__ != '_Worksheet':
            return {}

        if row_int is None:
            row_int = worksheet.first_row(ws)

        c = excel_address.col_letter(ws.UsedRange.Columns.Count)
        a = '{}{}:{}{}'.format('A', row_int, c, row_int)
        excel_range = ws.Range(a)

        return cls.__index_row_headers(excel_range)

    @classmethod
    def __index_row_headers(cls, excel_range):
        row = excel_range.Rows(1)
        row = worksheet.escape_excel_range_errors(row)[0]
        if not any(row):
            return ordereddict()

        c_1 = excel_range.Column
        headers = map_values_to_enum(row, c_1)
        headers = ordereddict((h, excel_address.col_letter(v)) for h, v in headers.items())

        return headers

    def __index_headers(self, row_ref):
        a = '*f {} :*l {}'.format(row_ref, row_ref)
        excel_range = self.range(a)

        return self.__index_row_headers(excel_range)

    def __index_meta_columns(self):
        if self.meta_r == 0:
            return

        self.m_headers = self.__index_headers('meta_r')

    def __index_header_columns(self):
        if self.header_r == 0:
            return

        self.headers = self.__index_headers('header_r')

    def range(self, reference):
        if not self.is_worksheet_type:
            ws_type = object_name(self.ws)
            raise TypeError('{} is not an Excel worksheet '.format(ws_type))

        try:
            a = self.excel_address(reference)
            excel_range = self.ws.Range(a)
        except pythoncom_error:
            excel_range = self.named_ranges.get(reference)

        if excel_range is None:
            raise ValueError("Invalid Range reference '{}'".format(reference))

        return excel_range

    def excel_address(self, reference):
        if ':' in reference:
            a_1, a_2 = reference.split(':')
            c_1, r_1 = _reference_to_col_row(self, a_1)
            c_2, r_2 = _reference_to_col_row(self, a_2)

            a = '${}${}:${}${}'.format(c_1, r_1, c_2, r_2)
        else:
            c_1, r_1 = _reference_to_col_row(self, reference)
            a = '${}${}'.format(c_1, r_1)

        return a

    def __getitem__(self, reference):
        return self.range(reference)

    def __setitem__(self, reference, v):
        """ write value(s) to excel range """
        excel_range = self.range(reference)

        m = self.__validate_matrix_within_range_boundaries(v, excel_range)

        was_filtered = self.has_filter
        worksheet.write_to_excel_range(m, excel_range)

        r = excel_range.Row
        self.set_range_boundaries(index_meta=(r   <= self.meta_r),
                                  index_header=(r <= self.header_r))

        if was_filtered:
            self.reapply_filter()

    def __iter__(self) -> Generator[flux_row_cls, Any, Any]:
        return self.flux_rows('*f')

    def __repr__(self):
        if not self.is_worksheet_type:
            return "{{}}: '{}'".format(self.ws.__class__.__name__, self.ws_name)

        if self.first_c and self.last_c:
            r = max(self.header_r, self.header_r)
            if r == 0:
                r = self.first_r

            a = "{}{}:{}{}".format(self.first_c,
                                   r,
                                   self.last_c,
                                   self.last_r)
        else:
            a = '{unknown address}'

        return "'{}' {}".format(self.ws_name, a)

    def __validate_matrix_within_range_boundaries(self, v, excel_range):
        """
        if lev has fixed columns or rows, these should not be exceeded
        make sure matrix fits in allowed destination space
        """
        m = iterator_to_collection(v)
        m = modify_iteration_depth(m, depth=2)

        col_max = num_cols = len(m[0])
        row_max = num_rows = len(m)

        first_c, last_c = self._fixed_columns
        first_r, last_r = self._fixed_rows

        c_1 = excel_range.Column
        r_1 = excel_range.Row

        if last_c:
            first_c = excel_address.col_number(first_c) or excel_address.col_number(c_1)
            last_c  = excel_address.col_number(last_c)
            col_max = (last_c - first_c) + 1

        if last_r:
            first_r = int(first_r) or int(r_1)
            last_r  = int(last_r)
            row_max = (last_r - first_r) + 1

        if num_cols > col_max:
            raise ValueError('Number of columns in data exceeds fixed destination range')

        if num_rows > row_max:
            raise ValueError('Number of rows in data exceeds fixed destination range')

        return m


def _named_ranges_in_workbook(wb):
    named_ranges = {}

    for nr in wb.Names:
        if nr.Visible:
            try:
                named_ranges[nr.Name] = nr.RefersToRange
            except pythoncom_error:
                continue

    return named_ranges


def _reference_to_col_row(lev, reference):
    reference = __reference_to_property_names(reference)
    col, row  = __property_names_to_value(lev, reference)

    if col is None or row is None:
        col, row = __parse_characters_from_digits(reference, col, row)

    return col, row


def __reference_to_property_names(reference):
    """
    eg:
        'header_c first_r' = __reference_to_property_names('*h *f')
    """
    anchor_names = {'*m': 'meta',
                    '*h': 'header',
                    '*f': 'first',
                    '*l': 'last'}

    anchor_re = re.compile('''
         (?P<col>^[*][fla])
        |(?P<row>[*][mhfla]$)
    ''', re.X | re.I)

    reference = reference.strip()

    for match in anchor_re.finditer(reference):
        name  = match.lastgroup
        value = match.group(0)

        if name == 'col':
            if value == '*a':
                col = 'first_empty_column '
            else:
                col = anchor_names[value] + '_c '

            reference = reference.replace(value, col, 1)

        elif name == 'row':
            if value == '*a':
                row = 'first_empty_row '
            else:
                row = ' ' + anchor_names[value] + '_r'

            reference = reference.replace(value, row, 1)

    # replace multiple spaces with single space
    reference = ' '.join(reference.split())

    return reference


def __property_names_to_value(lev, reference):
    if ' ' not in reference:
        return None, None

    # replace multiple spaces with single space
    reference = ' '.join(reference.split())

    splits = reference.split(' ')
    col = __col_row_to_value(lev, splits[0])
    row = __col_row_to_value(lev, splits[1])

    return col, row


def __col_row_to_value(lev, reference):
    if reference in lev.headers:
        literal = lev.headers[reference]
    elif reference in lev.m_headers:
        literal = lev.m_headers[reference]
    elif reference in lev.__dict__:
        literal = lev.__dict__[reference]
    elif reference in lev.__class__.__dict__:
        literal = getattr(lev, reference)
    else:
        literal = None

    return literal


def __parse_characters_from_digits(reference, col, row):

    address_re = re.compile(r'''
         (?P<col>^[$]?[a-z]{1,2})(?=[\d* ])
        |(?P<row>[$]?[\d]+$)
    ''', re.X | re.I)

    reference = reference.replace('$', '')

    for match in address_re.finditer(reference):
        name  = match.lastgroup
        value = match.group(0)

        if (name == 'col') and (col is None):
            col = value
        elif (name == 'row') and (row is None):
            row = value

    return col, row

