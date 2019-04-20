
from copy import deepcopy

from itertools import islice
from collections import OrderedDict
from collections import namedtuple

from .. util.iter import OrderedDefaultDict

from .. util.iter import generator_to_list
from .. util.iter import assert_iteration_depth
from .. util.iter import iteration_depth
from .. util.iter import modify_iteration_depth
from .. util.iter import transpose
from .. util.iter import index_sequence
from .. util.iter import depth_one
from .. util.iter import ordered_unique
from .. util.iter import is_vengeance_class
from .. util.iter import is_flux_row_class

from .. util.text import repr_
from .. util.text import p_json_dumps

from .. util.filesystem import write_file
from .. util.filesystem import read_file
from .. util.filesystem import apply_file_extension

from . flux_row_cls import flux_row_cls


class flux_cls:

    def __init__(self, matrix=None):
        self._num_cols = None
        self.is_empty  = None

        self.headers = OrderedDict()
        self.matrix  = self.__to_flux_rows(matrix)

    @property
    def header_values(self):
        return self.matrix[0].values

    @property
    def num_cols(self):
        """ find the maximum column length of all rows """
        if isinstance(self._num_cols, int):
            return self._num_cols

        self._num_cols = max(len(row) for row in self.matrix)

        return self._num_cols

    @property
    def is_jagged(self):
        num_cols = len(self.matrix[0])
        for row in self.matrix[1:]:
            if len(row) != num_cols:
                return True

        return False

    @property
    def has_data(self):
        return self.num_rows == 0

    @property
    def num_rows(self):
        """ header row not included in count """
        return len(self.matrix) - 1

    def execute_commands(self, commands, profile=False):
        if profile:
            from line_profiler import LineProfiler
            profiler = LineProfiler()
        else:
            profiler = None

        commands = self.__parse_commands(commands)

        for command in commands:
            method = command.method
            if profiler:
                method = profiler(method)

            if command.num_args == 0:
                method()
            elif command.num_args == 1:
                method(command.args)
            else:
                method(*command.args)

        if profiler:
            profiler.print_stats()

    def __parse_commands(self, commands):
        parsed = []
        command_names = index_sequence(['method_name', 'method', 'args', 'num_args'])

        for command in commands:
            if isinstance(command, (list, tuple)):
                name, args = command
                num_args = len(args)
            else:
                name = command
                args = None
                num_args = 0

            method = getattr(self, name)

            row_o = flux_row_cls(command_names, [name, method, args, num_args])
            row_o.bind()

            parsed.append(row_o)

        return parsed

    def reapply_header_names(self, headers):
        """
        as to not de-reference flux_row_cls._headers in meta_m

        can NOT reset self.headers to new variable, each item must be individually reassigned
        """
        if len(headers) != self._num_cols:
            self._num_cols = None

        self.headers.clear()
        for i, header in enumerate(headers):
            self.headers[header] = i

    def matrix_by_headers(self, *headers):
        columns = transpose([row.values for row in self.matrix[1:]])

        m = []
        for header in modify_iteration_depth(headers, 1):
            header = self.__process_header(header)

            if header not in self.headers:
                column = [None] * self.num_rows
            else:
                i = self.headers[header]
                column = columns[i].copy()

            column.insert(0, header)
            m.append(column)

        m = transpose(m)

        self.headers.clear()
        self.matrix = self.__to_flux_rows(m)

    def __process_header(self, header):
        """
        inserted headers must be surrounded by parenthesis to ensure these
        new columns are being created intentionally (and not because of spelling errors, etc)
        """

        # renamed header
        if isinstance(header, dict):
            h_old, h_new = tuple(header.items())[0]
            self.headers[h_new] = self.headers[h_old]

            return h_new

        # inserted header
        if header.startswith('(') and header.endswith(')'):
            return header.replace('(', '').replace(')', '')

        if header not in self.headers:
            raise ValueError("'{header}' not found in flux headers\n"
                             "inserted columns should be surrounded by parenthesis, ie '({header})' not '{header}'"
                             .format(header=header))

        return header

    def rename_columns(self, old_to_new_headers):
        """
        :param old_to_new_headers: a dictionary of {h_old: h_new} headers
        """
        renamed = self.header_values

        for h_old, h_new in old_to_new_headers.items():
            if h_old not in self.headers:
                raise KeyError('invalid header name {}'.format(h_old))

            i = self.headers[h_old]
            renamed[i] = h_new

        self.reapply_header_names(renamed)

    def insert_columns(self, *inserted):
        """
        :param inserted: (before_header, new_header)

        eg inserted:
            [(0,          'header_a'),      insert column at index 0
             ('*f',       'header_a'),      insert column at index 0
             ('header_a', 'header_b')]      insert column before 'header_b'
        """
        inserted = modify_iteration_depth(inserted)
        nd = iteration_depth(inserted)

        if nd == 0:
            inserted = [(0, inserted)]
        elif nd == 1:
            inserted = [inserted]

        headers = self.header_values
        for before, header in inserted:
            i = None

            if isinstance(before, int):
                i = before
            elif isinstance(before, str):
                if before == '*f':
                    i = 0
                elif before == '*l':
                    i = len(headers)
                else:
                    before = before.replace('*', '')
                    i = headers.index(before)

            if i is None:
                raise KeyError("insertion header '{}' does not exist".format(before))

            headers.insert(i, header)

        indeces = []
        for _, header in inserted:
            indeces.append(headers.index(header))

        indeces.sort()

        for i in indeces:
            for row in self:
                row.values.insert(i, None)

        self.reapply_header_names(headers)

    def append_columns(self, *names):
        names = modify_iteration_depth(names, depth=1)
        self.matrix[0].values.extend(names)

        for header in names:
            self.headers[header] = len(self.headers)
            for row in self:
                row.values.append(None)

    def delete_columns(self, *names):
        names = modify_iteration_depth(names, depth=1)
        indeces = [self.headers[h] for h in names]

        for c in sorted(indeces, reverse=True):
            for row in self.matrix:
                del row.values[c]

        self.reapply_header_names(self.header_values)

    def insert_rows(self, i, m):
        if self.is_empty:
            self.matrix = self.__to_flux_rows(m)
            return

        if i == 0:
            self.headers.clear()
            del self.matrix[0]
        elif is_vengeance_class(m):
            m = list(m.rows())[1:]

        self.matrix[i:i] = self.__to_flux_rows(m)

    def append_rows(self, m):
        if self.is_empty:
            self.matrix = self.__to_flux_rows(m)
            return

        if is_vengeance_class(m):
            m = list(m.rows())[1:]

        self.matrix.extend(self.__to_flux_rows(m))

    def fill_jagged_columns(self):
        num_cols = self.num_cols

        for row in self:
            values = row.values
            num_missing_c = num_cols - len(values)

            if num_missing_c > 0:
                values.extend([None] * num_missing_c)

    def sort(self, *f, **kwargs):
        """ in-place
        eg:
            flux.sort('col_a', 'col_b', 'col_c',
                      reverse=[True, True, True])
        """
        self.matrix[1:] = self.__sort_rows(f, kwargs)

    def sorted(self, *f, **kwargs):
        """ returns new flux
        eg:
            flux = flux.sorted('col_a', 'col_b', 'col_c',
                               reverse=[True, True, True])
        """
        m = [row.values for row in self.__sort_rows(f, kwargs)]
        m.insert(0, self.header_values)

        return self.__class__(m.copy())

    def filter(self, f):
        """ in-place """
        self.matrix[1:] = [row for row in self if f(row)]

    def filtered(self, f):
        """ return new flux """
        m = [row.values for row in self if f(row)]
        m.insert(0, self.header_values)

        return self.__class__(m.copy())

    def filter_by_unique(self, *f):
        self.__filter_unique_rows(f, in_place=True)

    def filtered_by_unique(self, *f):
        return self.__filter_unique_rows(f, in_place=False)

    def __sort_rows(self, f, kwargs):
        if kwargs and 'reverse' not in kwargs:
            raise ValueError("only 'reverse' keyword is accepted")

        r = list(kwargs.get('reverse', []))
        for _ in range(len(f) - len(r)):
            r.append(False)

        r = reversed(r)
        f = reversed(f)

        m = [row for row in self]
        for f, reverse in zip(f, r):
            f = self.__row_values_accessor(f)
            m.sort(key=f, reverse=reverse)

        return m

    def __filter_unique_rows(self, f, in_place):
        uniq = set()

        def evaluate_unique(row):
            v = f(row)
            if v not in uniq:
                uniq.add(v)
                return True
            else:
                return False

        f = self.__row_values_accessor(f)
        if in_place:
            self.filter(evaluate_unique)
        else:
            return self.filtered(evaluate_unique)

    def unique_values(self, *f):
        """ :return: unique values within column(s) """
        f = self.__row_values_accessor(f)
        return ordered_unique(f(row) for row in self)

    def reset_matrix(self, m):
        self._num_cols = None

        self.headers.clear()
        self.matrix = self.__to_flux_rows(m)

    def index_row(self, *f):
        """ dictionary of {f(row): row}
        overwrites row values for non-unique key values
        """
        f = self.__row_values_accessor(f)
        return OrderedDict((f(row), row) for row in self)

    def index_rows(self, *f):
        """ dictionary of {f(row): [rows]}
        preserves rows in a list for non-unique key values
        """
        f = self.__row_values_accessor(f)
        items = [(f(row), row) for row in self]

        return OrderedDefaultDict(list, items)

    def namedtuples(self):
        try:
            nt_cls = namedtuple('flux_row_nt', self.header_values)
            return [nt_cls(*row.values) for row in self]
        except ValueError as e:
            import re

            names = [n for n in self.header_values
                       if re.search('^[^a-z]|[ ]', n, re.IGNORECASE)]
            raise ValueError("invalid headers for namedtuple: {}".format(names)) from e

    def bind(self):
        """ speed up attribute access by binding values directly to flux_row_cls.__dict__
        (only use this if you know the side-effects)
        """
        [row.bind() for row in self.matrix]

    def unbind(self):
        """ return dynamic flux_row_cls.values from flux_row_cls.__dict__ """
        instance_names = tuple(self.headers.keys())
        [row.unbind(instance_names) for row in self.matrix]

    def to_csv(self, path, encoding=None):
        path = apply_file_extension(path, '.csv')
        m = list(self.rows())

        write_file(path, m, encoding=encoding)

    @classmethod
    def from_csv(cls, path, encoding=None):
        path = apply_file_extension(path, '.csv')
        m = read_file(path, encoding=encoding)

        return cls(m)

    def to_json(self, path=None, encoding=None):
        path = apply_file_extension(path, '.json')

        j = [row.dict() for row in self]
        j = p_json_dumps(j)

        if path is None:
            return j

        write_file(path, j, encoding=encoding)

    @classmethod
    def from_json(cls, path, encoding=None):
        path = apply_file_extension(path, '.json')

        rows = read_file(path, encoding=encoding)
        if rows:
            m = [list(d.values()) for d in rows]
            m.insert(0, list(rows[0].keys()))
        else:
            m = [[]]

        return cls(m)

    def serialize(self, path):
        """ you should be aware of the security flaws from using pickle """
        path = apply_file_extension(path, '.flux')
        write_file(path, self)

    @classmethod
    def deserialize(cls, path):
        """ you should be aware of the security flaws from using pickle """
        path = apply_file_extension(path, '.flux')
        return read_file(path)

    def rows(self, r_1='*h', r_2='*l'):
        r_1 = self.__matrix_index(r_1)
        r_2 = self.__matrix_index(r_2)

        return (row.values for row in islice(self.matrix, r_1, r_2 + 1))

    def flux_rows(self, r_1='*h', r_2='*l'):
        r_1 = self.__matrix_index(r_1)
        r_2 = self.__matrix_index(r_2)

        return iter(islice(self.matrix, r_1, r_2 + 1))

    def __to_flux_rows(self, m):
        if m is None:
            self.is_empty = True
            return [flux_row_cls({}, [])]

        m = generator_to_list(m)
        assert_iteration_depth(m, 2)
        
        if is_flux_row_class(m[0]):
            m = [row.values for row in m]

        self.__assert_no_reserved_headers(m[0])
        if not self.headers:
            self.headers = index_sequence(str(v) for v in m[0])

        num_cols = self._num_cols or 0
        flux_m   = []

        for row in m:
            if not isinstance(row, list):
                raise ValueError('row must be list')

            num_cols = max(num_cols, len(row))
            flux_m.append(flux_row_cls(self.headers, row))

        self._num_cols = num_cols
        self.is_empty  = (len(flux_m) == 0)

        return flux_m

    @staticmethod
    def __assert_no_reserved_headers(headers):
        reserved = set(headers) & flux_row_cls.class_names
        if reserved:
            raise NameError("reserved name(s) {} found in header row {}".format(list(reserved), headers))

    def __to_primitive_rows(self):
        if not isinstance(self.matrix[0], flux_row_cls):
            return

        self.matrix = [row.values for row in self.matrix]

    def __row_values_accessor(self, f):
        """ convert f into a function that can be called on each row in self._matrix """

        # return muliple values (as tuple) from each row
        def row_values(row):
            return tuple(row.values[c] for c in columns)

        # return single value from each row
        def row_value(row):
            return row.values[i]

        f = modify_iteration_depth(f, depth=0)
        self.__validate_row_accessor(f)

        if callable(f):
            return f

        if isinstance(f, (list, tuple)):
            columns = tuple(self.headers.get(n, n) for n in f)
            f = row_values
        elif isinstance(f, str):
            i = self.headers[f]
            f = row_value
        elif isinstance(f, int):
            i = f
            f = row_value

        return f

    def __validate_row_accessor(self, f):
        num_cols = len(self.headers) - 1

        if isinstance(f, (str, list, tuple)):
            f_ = depth_one(f)

            invalid = [h for h in f_
                         if isinstance(h, str)
                         if h not in self.headers]
            if invalid:
                raise KeyError("invalid column reference: {}".format(repr_(invalid)))

            invalid = [i for i in f_
                         if isinstance(i, int)
                         if i > num_cols]
            if invalid:
                raise KeyError("integer(s) out of bounds: {}".format(repr_(invalid)))

        elif isinstance(f, int):
            if f > num_cols:
                raise KeyError("integer out of bounds: {}".format(f))

        else:
            raise TypeError("unhandled type conversion for '{}'".format(f))

    def __matrix_index(self, reference):
        r_i = None

        if isinstance(reference, (int, float)):
            r_i = int(reference)
        elif reference == '*h':
            r_i = 0
        elif reference == '*f':
            r_i = 1
        elif reference == '*l':
            r_i = self.num_rows

        if r_i is None:
            raise KeyError("invalid index '{}'".format(reference))

        return r_i

    def copy(self, deep=False):
        if deep:
            return deepcopy(self)

        # self._num_cols?
        m = [row.values for row in self.matrix]
        return self.__class__(m.copy())

    def __len__(self):
        return len(self.matrix)

    def __getitem__(self, ref):
        if isinstance(ref, int):
            return self.matrix[ref]

        if isinstance(ref, str):
            if ref not in self.headers:
                raise ValueError("column '{}' not in headers".format(ref))

            i = self.headers[ref]
            return [row.values[i] for row in self]

        if isinstance(ref, slice):
            i_1, i_2, step = ref.start, ref.stop, ref.step
            if i_1 is not None:
                if i_1 < 0:
                    i_1 = len(self.matrix) + i_1

            if i_2 is not None:
                if i_2 < 0:
                    i_2 = len(self.matrix) + i_2

            return list(row for row in islice(self.matrix, i_1, i_2, step))

        raise KeyError("reference syntax should be integers, eg 'flux[1:3]'")

    def __setitem__(self, ref, column):
        if ref not in self.headers:
            self.append_columns(ref)

        column = modify_iteration_depth(column, 1)
        nd = iteration_depth(column)

        if nd == 0:
            column = [column]
        elif nd == 2:
            column = transpose(column)[0]

        if len(column) != self.num_rows:
            raise ValueError('invalid length')

        i = self.headers[ref]
        for row, v in zip(self, column):
            row.values[i] = v

    def __iter__(self):
        return iter(islice(self.matrix, 1, None))

    def __repr__(self):
        headers = repr_(self.headers.keys(), wrap='[]')
        return '{} ({:,})'.format(headers, self.num_rows)


