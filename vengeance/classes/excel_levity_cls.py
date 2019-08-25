
import re

# noinspection PyUnresolvedReferences
from pythoncom import com_error

from collections import namedtuple
from collections import OrderedDict

from .. excel_com.worksheet import activate_sheet
from .. excel_com.worksheet import first_col
from .. excel_com.worksheet import last_col
from .. excel_com.worksheet import first_row
from .. excel_com.worksheet import last_row
from .. excel_com.worksheet import gen_range_rows
from .. excel_com.worksheet import clear_worksheet_filter
from .. excel_com.worksheet import is_filtered
from .. excel_com.worksheet import write_to_excel_range
from .. excel_com.worksheet import is_range_empty
from .. excel_com.worksheet import parse_range

from .. excel_com.excel_address import col_letter
from .. excel_com.excel_address import col_letter_offset
from .. excel_com.excel_address import col_number

from .. excel_com.excel_constants import *

from .. util.iter import index_sequence
from .. util.iter import modify_iteration_depth
from .. util.text import between

from . flux_row_cls import lev_row_cls


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

        self.headers   = OrderedDict()
        self.m_headers = OrderedDict()      # "meta" row headers

        self._fixed_columns = (first_c, last_c)
        self._fixed_rows    = (first_r, last_r)

        self.first_c  = first_c
        self.last_c   = last_c
        self.meta_r   = meta_r
        self.header_r = header_r
        self.first_r  = first_r
        self.last_r   = last_r

        self.num_cols = 0
        self.num_rows = 0
        self.is_empty = None

        self._named_ranges = _set_named_ranges(self.workbook)

        self.set_range_boundaries(index_meta=True, index_header=True)

    @property
    def application(self):
        return self.ws.Application

    @property
    def workbook(self):
        return self.ws.Parent

    @property
    def named_ranges(self):
        return {name: self.excel_range(name) for name in self._named_ranges.keys()}

    @property
    def worksheet(self):
        return self.ws

    @property
    def worksheet_name(self):
        return self.ws.Name

    @property
    def ws_name(self):
        return self.ws.Name

    @property
    def header_values(self):
        return list(self.headers.keys())

    @property
    def meta_headers(self):
        return self.m_headers

    @property
    def meta_header_values(self):
        return list(self.m_headers.keys())

    @property
    def has_headers(self):
        if self.is_empty:
            return False

        return bool(self.headers) and bool(self.m_headers)

    @property
    def has_filter(self):
        return bool(self.ws.AutoFilter)

    @property
    def append_r(self):
        """ determines the first available empty row in sheet """
        if self.is_empty:
            r = self.first_r
        else:
            r = self.last_r + 1

        return r

    @property
    def append_c(self):
        """ determines the first available empty column in sheet """
        if self.is_empty:
            c = self.first_c
        else:
            c = col_letter_offset(self.last_c, 1)

        return c

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

        was_filtered = is_filtered(self.ws)
        self.ws.AutoFilterMode = False

        if was_filtered:
            self.set_range_boundaries()

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

    def clear(self, ref,
                    clear_values=True,
                    clear_colors=False):

        excel_range = self.excel_range(ref)
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

        worksheet filter MUST be cleared in order to correctly determine these boundaries
        """
        clear_worksheet_filter(self.ws)

        self.__find_range_boundaries()

        if index_meta:
            self.__index_meta_columns()

        if index_header:
            self.__index_header_columns()

    def __find_range_boundaries(self):
        self.first_c, self.last_c = self._fixed_columns
        self.first_r, self.last_r = self._fixed_rows

        excel_range = self.ws.UsedRange

        self.first_c = self.first_c or first_col(excel_range)
        self.first_c = col_letter(self.first_c)
        self.last_c  = self.last_c or last_col(excel_range, default_c=self.first_c)
        self.last_c  = col_letter(self.last_c)

        self.num_cols = col_number(self.last_c) - col_number(self.first_c) + 1

        r_1 = max(self.meta_r, self.header_r) + 1
        r_2 = excel_range.Rows.Count
        a = '{}{}:{}{}'.format(self.first_c, r_1, self.last_c, r_2)
        excel_range = self.ws.Range(a)

        self.first_r = self.first_r or first_row(excel_range, default_r=r_1)
        self.last_r  = self.last_r or last_row(excel_range, default_r=self.first_r)

        self.num_rows = self.last_r - self.first_r + 1

        if self.last_r > self.first_r:
            self.is_empty = False
        else:
            header_r = self.header_r or self.meta_r or self.first_r
            a = '{}{}:{}{}'.format(self.first_c, header_r, self.last_c, header_r)
            self.is_empty = is_range_empty(self.ws.Range(a))

    @classmethod
    def index_headers(cls, ws, row_int=None):
        if row_int is None:
            row_int = first_row(ws)

        c = col_letter(ws.UsedRange.Columns.Count)
        a = '{}{}:{}{}'.format('A', row_int, c, row_int)
        excel_range = ws.Range(a)

        return cls.__index_row_headers(excel_range)

    def __index_headers(self, row_ref):
        a = '*f {} :*l {}'.format(row_ref, row_ref)
        excel_range = self.excel_range(a)

        return self.__index_row_headers(excel_range)

    @classmethod
    def __index_row_headers(cls, excel_range):
        row = next(gen_range_rows(excel_range))

        start = excel_range.Column
        headers = index_sequence(row, start)
        headers = OrderedDict((h, col_letter(v)) for h, v in headers.items())

        return headers

    def __index_meta_columns(self):
        if self.meta_r == 0:
            return

        self.m_headers = self.__index_headers('meta_r')

    def __index_header_columns(self):
        if self.header_r == 0:
            return

        self.headers = self.__index_headers('header_r')

    def excel_range(self, ref):
        a = None
        excel_range = None

        try:
            if ref not in self._named_ranges:
                a = self.excel_address(ref)
                excel_range = self.ws.Range(a)
            else:
                named_range = self._named_ranges[ref]
                a = '{}!{}'.format(named_range.tab_name, named_range.address)
                excel_range = self.workbook.Sheets(named_range.tab_name).Range(named_range.address)
        except com_error:
            pass

        if excel_range is None:
            raise ValueError("'{}' resolved to an invalid Excel address: '{}'".format(ref, a))

        return excel_range

    def excel_address(self, ref):
        if ':' in ref:
            a_1, a_2 = ref.split(':')

            c_1, r_1 = self.__reference_to_col_row(a_1)
            c_2, r_2 = self.__reference_to_col_row(a_2)
            a = '{}{}:{}{}'.format(c_1, r_1, c_2, r_2)
        else:
            c_1, r_1 = self.__reference_to_col_row(ref)
            a = '{}{}'.format(c_1, r_1)

        return a

    def __reference_to_col_row(self, ref):
        ref = ref.strip()
        ref = _anchor_substitution(ref)

        col, row = self.__property_reference(ref)
        col, row = _alphanum_reference(ref, col, row)

        return col, row

    def __property_reference(self, ref):
        if ' ' not in ref:
            return None, None

        ref = ' '.join(ref.split())
        splits = ref.split(' ')

        col = self.__levity_reference(splits[0])
        row = self.__levity_reference(splits[1])

        return col, row

    def __levity_reference(self, ref):
        if ref in self.headers:
            literal = self.headers[ref]
        elif ref in self.m_headers:
            literal = self.m_headers[ref]
        elif ref in self.__dict__:
            literal = self.__dict__[ref]
        elif ref in self.__class__.__dict__:
            literal = getattr(self, ref)
        else:
            literal = None

        return literal

    def rows(self, r_1='*h', r_2='*l'):
        if self.is_empty:
            return [[]]

        a = '*f {}:*l {}'.format(r_1, r_2)
        excel_range = self.excel_range(a)

        return (row for row in gen_range_rows(excel_range))

    def flux_rows(self, r_1='*h', r_2='*l'):
        if self.is_empty:
            return [[]]

        a = '*f {}:*l {}'.format(r_1, r_2)
        excel_range = self.excel_range(a)

        if self.headers:
            headers = index_sequence(self.headers.keys())
        elif self.m_headers:
            headers = index_sequence(self.m_headers.keys())
        else:
            headers = {}

        reserved = headers.keys() & lev_row_cls.class_names
        if reserved:
            raise NameError("reserved name(s) {} found in header row {}".format(list(reserved), list(headers.keys())))

        r_1 = excel_range.Row
        c_1, c_2 = self.first_c, self.last_c

        for r, row in enumerate(gen_range_rows(excel_range), r_1):
            a = '${}${}:${}${}'.format(c_1, r, c_2, r)
            yield lev_row_cls(headers, row, a)

    def __validate_destination_size(self, m, c_1, r_1):
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

    def __getitem__(self, ref):
        return self.excel_range(ref)

    def __setitem__(self, ref, v):
        """ write value(s) to excel range """
        excel_range = self.excel_range(ref)
        m = modify_iteration_depth(v, 2)

        c = excel_range.Column
        r = excel_range.Row
        self.__validate_destination_size(m, c, r)

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
            a = " {}{}:{}{}".format(self.first_c,
                                    self.header_r,
                                    self.last_c,
                                    self.last_r)
        else:
            a = ' {unknown address}'

        return "'{}'{}".format(self.ws_name, a)


def _set_named_ranges(wb):
    named_ranges = {}
    named_range_ntc = namedtuple('named_range_ntc', ('tab_name', 'address'))

    for nr in wb.Names:
        name = nr.Name.lower()
        full_addr = nr.RefersTo.lower()

        if ('!' not in name
          and '_xl' not in name
          and '#ref' not in full_addr):

            a = full_addr.split('\\')[-1]
            a = a.replace("'", '')
            a = a.replace('=', '')

            if '[' in a and ']' in a:
                wb_name = '[' + between(a, '[', ']') + ']'          # [workbook.xlsx]tab_name!address
                a = a.replace(wb_name, '')

            tab_name, a = a.split('!')
            named_ranges[nr.Name] = named_range_ntc(tab_name, a.upper())

    return named_ranges


def _anchor_substitution(ref):
    anchor_names = {'*m': 'meta',
                    '*h': 'header',
                    '*f': 'first',
                    '*l': 'last',
                    '*a': 'append'}

    anchor_re = re.compile('''
         (?P<col>^[*][fla])
        |(?P<row>[*][mhfla]$)
    ''', re.X | re.I)

    for match in anchor_re.finditer(ref):
        name_re = match.lastgroup
        val_re  = match.group(0)

        if name_re == 'col':
            col = anchor_names[val_re] + '_c '
            ref = ref.replace(val_re, col, 1)
        elif name_re == 'row':
            row = ' ' + anchor_names[val_re] + '_r'
            ref = ref.replace(val_re, row, 1)

    return ref


def _alphanum_reference(ref, col, row):
    if (col is not None) and (row is not None):
        return col, row

    address_re = re.compile(r'''
         (?P<col>^[$]?[a-z]{1,2})(?=[\d* ])
        |(?P<row>[$]?[\d]+$)
    ''', re.X | re.I)

    for match in address_re.finditer(ref):
        name_re = match.lastgroup
        val_re  = match.group(0)
        if name_re == 'col' and col is None:
            col = val_re
        elif name_re == 'row' and row is None:
            row = val_re

    return col, row


