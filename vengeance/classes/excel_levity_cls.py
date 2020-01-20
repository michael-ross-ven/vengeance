
import re

# noinspection PyUnresolvedReferences
from pythoncom import com_error as pythoncom_error

from collections import OrderedDict

from ..excel_com.worksheet import activate_sheet
from ..excel_com.worksheet import first_col
from ..excel_com.worksheet import last_col
from ..excel_com.worksheet import first_row
from ..excel_com.worksheet import last_row
from ..excel_com.worksheet import excel_range_rows
from ..excel_com.worksheet import clear_worksheet_filter
from ..excel_com.worksheet import is_filtered
from ..excel_com.worksheet import write_to_excel_range
from ..excel_com.worksheet import is_range_empty
from ..excel_com.worksheet import parse_range

from ..excel_com.excel_address import col_letter
from ..excel_com.excel_address import col_letter_offset
from ..excel_com.excel_address import col_number

from ..excel_com.excel_constants import *

from ..util.iter import map_numeric_indices
from ..util.iter import modify_iteration_depth
from ..util.iter import iterator_to_list

from .flux_row_cls import lev_row_cls


class excel_levity_cls:
    allow_focus = False

    def __init__(self, ws,
                       *,
                       first_c=None,
                       last_c=None,
                       meta_r=0,
                       header_r=0,
                       first_r=0,
                       last_r=0):

        self.ws = ws
        self.ws_name = ws.Name

        self.headers   = OrderedDict()
        self.m_headers = OrderedDict()

        self._named_ranges = {}

        self._fixed_columns = first_c, last_c
        self._fixed_rows    = first_r, last_r

        self.first_c  = first_c
        self.last_c   = last_c
        self.meta_r   = meta_r
        self.header_r = header_r
        self.first_r  = first_r
        self.last_r   = last_r

        self.set_range_boundaries(index_meta=True,
                                  index_header=True)

    @staticmethod
    def col_letter_offset(col_str, offset):
        return col_letter_offset(col_str, offset)

    @staticmethod
    def col_letter(col_int):
        return col_letter(col_int)

    @staticmethod
    def col_number(col_str):
        return col_number(col_str)

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

    @property
    def header_values(self):
        return list(self.headers.keys())

    @property
    def meta_header_values(self):
        return list(self.m_headers.keys())

    @property
    def has_headers(self):
        if self.is_empty:
            return False

        return bool(self.headers) or bool(self.m_headers)

    @property
    def has_filter(self):
        return bool(self.ws.AutoFilter)

    @property
    def first_empty_row(self):
        if self.is_empty:
            return self.header_r or self.meta_r or 1

        a = '{}{}:{}{}'.format(self.first_c, self.first_r,
                               self.last_c, self.first_r)
        first_data_row = self.ws.Range(a)

        if is_range_empty(first_data_row):
            r = self.first_r
        else:
            r = self.last_r + 1

        return r

    @property
    def first_empty_column(self):
        """ determines the first available empty column in sheet """
        if self.is_empty:
            c = self.first_c
        else:
            c = col_letter_offset(self.last_c, 1)

        return c

    @property
    def num_cols(self):
        return col_number(self.last_c) - col_number(self.first_c) + 1

    @property
    def num_rows(self):
        return int(self.last_r) - int(self.first_r) + 1

    @property
    def is_empty(self):
        if self.last_r > self.first_r:
            return False

        r_1 = self.header_r or self.meta_r or 1
        r_2 = self.last_r
        a = '{}{}:{}{}'.format(self.first_c, r_1, self.last_c, r_2)

        return is_range_empty(self.ws.Range(a))

    def rows(self, r_1='*h', r_2='*l'):
        if self.is_empty:
            return [[]]

        a = '*f {}:*l {}'.format(r_1, r_2)
        excel_range = self.excel_range(a)

        return (row for row in excel_range_rows(excel_range))

    def flux_rows(self, r_1='*h', r_2='*l'):
        if self.is_empty:
            return [[]]

        if self.headers:
            headers = map_numeric_indices(self.headers.keys())
        elif self.m_headers:
            headers = map_numeric_indices(self.m_headers.keys())
        else:
            headers = {}

        reserved = headers.keys() & lev_row_cls.class_names
        if reserved:
            raise NameError("reserved name(s) {} found in header row {}"
                            .format(list(reserved), list(headers.keys())))

        a = '*f {}:*l {}'.format(r_1, r_2)
        excel_range = self.excel_range(a)

        r_1 = excel_range.Row
        c_1, c_2 = self.first_c, self.last_c

        for r, row in enumerate(excel_range_rows(excel_range), r_1):
            a = '${}${}:${}${}'.format(c_1, r, c_2, r)
            yield lev_row_cls(headers, row, a)

    def activate(self):
        if self.allow_focus:
            activate_sheet(self.ws)

    def clear_filter(self):
        if not self.has_filter:
            return

        if is_filtered(self.ws):
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
        excel_range = self.excel_range(a)

        if excel_range.Cells.Count == 1:
            a = '{} {}:{} {}'.format(c_1, r, c_2, self.last_r + 1)
            excel_range = self.excel_range(a)

        self.remove_filter()
        excel_range.AutoFilter(*(1,))

    def calculate(self):
        self.excel_range('*f *h: *l *l').Calculate()

    def clear(self, reference,
                    clear_values=True,
                    clear_colors=False):

        excel_range = self.excel_range(reference)
        _, r_1, _, r_2 = parse_range(excel_range)

        if clear_values:
            excel_range.ClearContents()

            index_meta   = (r_1 <= self.meta_r)
            index_header = (r_1 <= self.header_r)
            self.set_range_boundaries(index_meta, index_header)

        if clear_colors:
            excel_range.Interior.Color = xlClear

    def set_range_boundaries(self, index_meta=True, index_header=True):
        """ find the edges of data in worksheet

        worksheet filter MUST be cleared from worksheet to
        determine these boundaries correctly
        """
        clear_worksheet_filter(self.ws)
        self.__range_boundaries()

        if index_meta:
            self.__index_meta_columns()

        if index_header:
            self.__index_header_columns()

    def __range_boundaries(self):
        used_range = self.ws.UsedRange

        first_c, last_c = self._fixed_columns
        first_r, last_r = self._fixed_rows

        self.first_c = first_c or first_col(used_range)
        self.last_c  = last_c  or last_col(used_range, default=self.first_c)

        r_1 = max(self.meta_r, self.header_r) + 1
        r_2 = used_range.Rows.Count
        a = '{}{}:{}{}'.format(self.first_c, r_1,
                               self.last_c,  r_2)
        excel_range = self.ws.Range(a)

        self.first_r = first_r or first_row(excel_range, default=r_1)
        self.last_r  = last_r  or last_row(excel_range, default=self.first_r)

        self.first_c = col_letter(self.first_c)
        self.last_c  = col_letter(self.last_c)
        self.first_r = int(self.first_r)
        self.last_r  = int(self.last_r)

    @classmethod
    def index_headers(cls, ws, row_int=None):
        if row_int is None:
            row_int = first_row(ws)

        c = col_letter(ws.UsedRange.Columns.Count)
        a = '{}{}:{}{}'.format('A', row_int, c, row_int)
        excel_range = ws.Range(a)

        return cls.__index_row_headers(excel_range)

    @classmethod
    def __index_row_headers(cls, excel_range):
        row = next(excel_range_rows(excel_range))
        if not any(row):
            return OrderedDict()

        start = excel_range.Column
        headers = map_numeric_indices(row, start)
        headers = OrderedDict((h, col_letter(v)) for h, v in headers.items())

        return headers

    def __index_headers(self, row_ref):
        a = '*f {} :*l {}'.format(row_ref, row_ref)
        excel_range = self.excel_range(a)

        return self.__index_row_headers(excel_range)

    def __index_meta_columns(self):
        if self.meta_r == 0:
            return

        self.m_headers = self.__index_headers('meta_r')

    def __index_header_columns(self):
        if self.header_r == 0:
            return

        self.headers = self.__index_headers('header_r')

    def excel_range(self, reference):
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

            a = '{}{}:{}{}'.format(c_1, r_1, c_2, r_2)
        else:
            c_1, r_1 = _reference_to_col_row(self, reference)
            a = '{}{}'.format(c_1, r_1)

        return a

    def __validate_within_fixed_destination(self, m, c_1, r_1):
        """
        if lev has fixed columns or rows, these should not be exceeded
        make sure matrix fits in allowed destination space
        """
        num_cols = len(m[0])
        num_rows = len(m)

        first_c, last_c = self._fixed_columns
        first_r, last_r = self._fixed_rows

        if last_c:
            first_c = col_number(first_c) or col_number(c_1)
            last_c  = col_number(last_c)
            col_max = (last_c - first_c) + 1

            if num_cols > col_max:
                raise ValueError('Number of columns in data exceeds fixed destination range')

        if last_r:
            first_r = int(first_r) or int(r_1)
            last_r  = int(last_r)
            row_max = (last_r - first_r) + 1

            if num_rows > row_max:
                raise ValueError('Number of rows in data exceeds fixed destination range')

    def __getitem__(self, reference):
        return self.excel_range(reference)

    def __setitem__(self, reference, v):
        """ write value(s) to excel range """
        excel_range = self.excel_range(reference)
        c = excel_range.Column
        r = excel_range.Row

        v = iterator_to_list(v)
        m = modify_iteration_depth(v, 2)
        self.__validate_within_fixed_destination(m, c, r)

        write_to_excel_range(m, excel_range)

        index_meta   = (r <= self.meta_r)
        index_header = (r <= self.header_r)
        self.set_range_boundaries(index_meta, index_header)

        if self.has_filter:
            self.reapply_filter()

    def __iter__(self):
        for row in self.flux_rows('*f'):
            yield row

    def __repr__(self):
        if self.first_c and self.last_c:
            a = "{}{}:{}{}".format(self.first_c,
                                   self.header_r,
                                   self.last_c,
                                   self.last_r)
        else:
            a = '{unknown address}'

        return "'{}' {}".format(self.ws_name, a)


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

    for match in address_re.finditer(reference):
        name  = match.lastgroup
        value = match.group(0)

        if (name == 'col') and (col is None):
            col = value
        elif (name == 'row') and (row is None):
            row = value

    return col, row

