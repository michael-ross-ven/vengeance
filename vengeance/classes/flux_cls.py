
from copy import deepcopy
from collections import OrderedDict
from collections import Counter
from collections import namedtuple
from itertools import islice

from .. util.filesystem import write_file
from .. util.filesystem import read_file
from .. util.filesystem import apply_file_extension
from .. util.iter import OrderedDefaultDict
from .. util.iter import iterator_to_list
from .. util.iter import base_class_names
from .. util.iter import iteration_depth
from .. util.iter import modify_iteration_depth
from .. util.iter import transpose
from .. util.iter import index_sequence
from .. util.iter import ordered_unique
from .. util.iter import is_flux_row_class
from .. util.text import p_json_dumps

from . flux_row_cls import flux_row_cls


class flux_cls:

    def __init__(self, matrix=None):
        self._num_cols = None

        self.headers = OrderedDict()
        self.matrix  = self._to_flux_rows(matrix)

    @property
    def header_values(self):
        return list(self.headers.keys())

    @property
    def num_rows(self):
        """ header row not included in count """
        return len(self.matrix) - 1

    @property
    def num_cols(self):
        """ maximum number of columns of all rows """
        if self._num_cols is None:
            m = [row.values for row in self.matrix]
            self._num_cols = max(map(len, m))

        return self._num_cols

    @property
    def is_jagged(self):
        num_cols = len(self.matrix[0].values)

        for row in self:
            if len(row.values) != num_cols:
                return True

        return False

    @property
    def is_empty(self):
        for row in self.matrix:
            if row.values:
                return False

        return True

    def _to_flux_rows(self, m):
        if m is None:
            return [flux_row_cls({}, [])]

        m = self.__validate_matrix(m)
        self.__validate_headers(m[0])

        if not self.headers:
            self.headers = index_sequence(m[0])

        if self._num_cols is None:
            self._num_cols = max(map(len, m))

        headers = self.headers
        flux_m  = [flux_row_cls(headers, row) for row in m]

        return flux_m

    def _reapply_header_names(self, headers):
        """
        re-assigning self.headers will de-reference flux_row_cls._headers
        instead, self.headers.clear() must be called, followed by addition of new
        items
        """
        if len(headers) != self._num_cols:
            self._num_cols = None

        self.headers.clear()
        for i, header in enumerate(headers):
            self.headers[header] = i

    def execute_commands(self, commands, profile=False):
        if profile:
            # noinspection PyUnresolvedReferences
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
        nt_cls = namedtuple('command_nt', ('name',
                                           'method',
                                           'args',
                                           'num_args'))

        for command in commands:
            if isinstance(command, (list, tuple)):
                name, args = command

                if isinstance(args, str):
                    num_args = 1
                else:
                    num_args = len(args)
            else:
                name = command
                args = None
                num_args = 0

            method = getattr(self, name)
            parsed.append(nt_cls(name, method, args, num_args))

        return parsed

    def matrix_by_headers(self, *headers):
        """
        performance enhancements:
            convert all headers to indices first
            take values on demand
            for c in range(indices):
                columns.append([row.values[c] for row in self.matrix])

            store columns that have already been used in dict
            self._num_cols does not need to be reset if length of headers
            equal to self._num_cols
        """
        headers = modify_iteration_depth(headers, depth=1)
        columns = transpose([row.values for row in self]) or [[]]

        m = []
        for header in headers:
            header = self.__renamed_or_inserted_header(header)

            column = [header]
            if header not in self.headers:
                column += [None] * self.num_rows
            else:
                i = self.headers[header]
                column += columns[i]

            m.append(column)

        m = transpose(m)

        self.headers.clear()
        self._num_cols = None

        self.matrix = self._to_flux_rows(m)

    def __renamed_or_inserted_header(self, header):
        """
        to ensure new columns are being created intentionally and not because
        of spelling errors etc, inserted headers must be surrounded by parenthesis
        """
        if not isinstance(header, (dict, str)):
            raise ValueError('{}\nheader must be either dictionary or string'.format(header))

        if isinstance(header, dict):                            # renamed: {'header_a': 'header_z'}
            h_old, h_new = tuple(header.items())[0]
            self.headers[h_new] = self.headers[h_old]

            return h_new

        if header.startswith('(') and header.endswith(')'):     # inserted: '(inserted_header)'
            return header[1:-1]

        if header not in self.headers:
            raise ValueError("'{header}' does not exist\ninserted columns should be surrounded "
                             "by parenthesis, ie '({header})' not '{header}'".format(header=header))

        return header

    def rename_columns(self, old_to_new_headers):
        """
        :param old_to_new_headers: a dictionary of {h_old: h_new} headers
        """
        renamed = self.matrix[0].values

        for h_old, h_new in old_to_new_headers.items():
            if h_old not in self.headers:
                raise KeyError('invalid header name {}'.format(h_old))

            i = self.headers[h_old]
            renamed[i] = h_new

        self._reapply_header_names(renamed)

    def insert_columns(self, *inserted):
        """
        :param inserted: (before, header_name)

        eg names:
            flux.insert_columns('header_a')                     insert column at index 0
            flux.insert_columns((3, 'header_a'))                insert column at index 3
            flux.insert_columns(('header_a', 'header_b'))       insert column at index 0
        """
        inserted = modify_iteration_depth(inserted, depth=0)
        if not inserted:
            return

        nd = iteration_depth(inserted)
        if nd == 0:
            inserted = [(0, inserted)]
        elif nd == 1:
            inserted = [inserted]

        names = [n[1] for n in inserted]
        names = self.__validate_column_names(names)

        invalid = list(self.headers.keys() & set(names))
        if invalid:
            raise ValueError('column name(s) conflict with existing headers:\n{}'.format(invalid))

        header_values = self.matrix[0].values
        for before, header in inserted:
            if isinstance(before, int):
                i = before
            elif before == '*f':
                i = 0
            elif before == '*l':
                i = len(header_values)
            else:
                try:
                    i = header_values.index(before)
                except ValueError as e:
                    raise ValueError("header '{}' does not exist".format(before)) from e

            header_values.insert(i, header)

        indices = []
        for _, header in inserted:
            indices.append(header_values.index(header))

        indices.sort()
        for i in indices:
            for row in self:
                row.values.insert(i, None)

        self._reapply_header_names(header_values)

    def append_columns(self, *names):
        names = self.__validate_column_names(names)

        invalid = list(self.headers.keys() & set(names))
        if invalid:
            raise ValueError('column name(s) conflict with existing headers:\n{}'.format(invalid))

        self.matrix[0].values.extend(names)
        for header in names:
            self.headers[header] = len(self.headers)

        nones = [None for _ in range(len(names))]
        for row in self:
            row.values.extend(nones)

        self._num_cols = None

    def delete_columns(self, *names):
        """ if negative indices? """
        names = self.__validate_column_names(names)
        indices = [self.headers.get(h, h) for h in names]

        invalid = [i for i in indices if not isinstance(i, int)]
        if invalid:
            raise ValueError('column(s) do not exist:\n{}'.format(invalid))

        invalid = [i for i in indices if i < 0]
        if invalid:
            raise ValueError('negative indices not supported')

        indices.sort(reverse=True)

        for row in self.matrix:
            for c in indices:
                del row.values[c]

        self._reapply_header_names(self.matrix[0].values)

    def fill_jagged_columns(self):
        """ :returns indices of rows whose columns were extended """

        max_cols = self.num_cols

        row_indices = []
        for i, row in enumerate(self.matrix):
            values = row.values
            num_missing = max_cols - len(values)

            if num_missing > 0:
                row_indices.append(i)
                nones = [None for _ in range(num_missing)]
                values.extend(nones)

        return row_indices

    def insert_rows(self, i, rows):
        if self.is_empty:
            self.matrix = self._to_flux_rows(rows)
            return

        if i == 0:
            self.headers.clear()
            del self.matrix[0]

        self._num_cols = None
        self.matrix[i:i] = self._to_flux_rows(rows)

    def append_rows(self, rows):
        if self.is_empty:
            self.matrix = self._to_flux_rows(rows)
            return

        self._num_cols = None
        self.matrix.extend(self._to_flux_rows(rows))

    def sort(self, *f, reverse=None):
        """ in-place sort
        sort priority of columns proceeds from left to right

        eg:
            flux.sort('col_a')

        eg multiple columns:
            flux.sort('col_a', 'col_b', 'col_c',
                      reverse=[True, True, True])
        """
        self.matrix[1:] = self.__sort_rows(f, reverse)

    def sorted(self, *f, reverse=None):
        """ returns new flux after sorting
        sort priority of columns proceeds from left to right

        eg:
            flux = flux.sorted('col_a')

        eg multiple columns:
            flux = flux.sorted('col_a', 'col_b', 'col_c',
                               reverse=[True, True, True])
        """
        m = [self.matrix[0].values.copy()]
        m.extend([row.values.copy() for row in self.__sort_rows(f, reverse)])

        flux = self.__class__()
        flux._num_cols = self._num_cols
        flux.matrix = flux._to_flux_rows(m)

        return flux

    def __sort_rows(self, f, order):
        """
        sort priority of columns proceeds from left to right
        """
        if isinstance(order, bool):
            order = [order]
        else:
            order = order or []

        if not isinstance(order, (list, tuple)):
            raise TypeError('reverse must be a list of booleans')

        f = modify_iteration_depth(f, 1)
        for _ in range(len(f) - len(order)):
            order.append(False)

        m = self.matrix[1:]

        f = reversed(f)
        o = reversed(order)
        for _f_, _o_ in zip(f, o):
            _f_ = self.__row_values_accessor(_f_)
            m.sort(key=_f_, reverse=_o_)

        return m

    def filter(self, f):
        """ in-place """
        self.matrix[1:] = [row for row in self if f(row)]

    def filtered(self, f):
        """ returns new flux """
        m = [self.matrix[0].values.copy()]
        m.extend([row.values.copy() for row in self if f(row)])

        flux = self.__class__()
        flux._num_cols = self._num_cols
        flux.matrix = flux._to_flux_rows(m)

        return flux

    def filter_by_unique(self, *f):
        self.__filter_unique_rows(f, in_place=True)

    def filtered_by_unique(self, *f):
        return self.__filter_unique_rows(f, in_place=False)

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
        """ :return: list of unique values within column(s), original order is preserved """
        f = self.__row_values_accessor(f)
        return ordered_unique(f(row) for row in self)

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
            nt_cls = namedtuple('flux_row_nt', self.headers.keys())
            return [nt_cls(*row.values) for row in self]
        except ValueError as e:
            import re

            names = [n for n in self.headers.keys() if re.search('^[^a-z]|[ ]', str(n), re.I)]
            if names:
                raise ValueError('invalid field(s) for namedtuple constructor: {}'.format(names)) from e
            else:
                raise e

    def enumerate_rows(self, start=0):
        """ to assist with debugging """
        if 'i' in self.headers:
            raise AssertionError("column 'i' already exists as a header name")

        for i, row in enumerate(self.matrix, start):
            row.__dict__['i'] = i

    def copy(self, deep=False):
        if deep:
            return deepcopy(self)

        m = [row.values.copy() for row in self.matrix]

        flux = self.__class__()
        flux._num_cols = self._num_cols
        flux.matrix = flux._to_flux_rows(m)

        return flux

    def rows(self, r_1='*h', r_2='*l'):
        r_1 = self._matrix_index(r_1)
        r_2 = self._matrix_index(r_2)

        return (row.values for row in islice(self.matrix, r_1, r_2 + 1))

    def flux_rows(self, r_1='*h', r_2='*l'):
        r_1 = self._matrix_index(r_1)
        r_2 = self._matrix_index(r_2)

        return iter(islice(self.matrix, r_1, r_2 + 1))

    def contiguous_rows(self, *f):
        """ :return: list of rows where values are contiguous """
        rows = []
        for i_1, i_2 in self.contiguous_indices(f):
            rows.append(self.matrix[i_1:i_2])

        return rows

    def contiguous_indices(self, *f):
        """ :return: list of (i_1, i_2) row indices where values are contiguous
        eg:
            for i_1, i_2 in flux.contiguous_indices('col_a', 'col_b'):
                rows = flux[i_1:i_2]
        """
        if self.num_rows == 0:
            return []

        f = self.__row_values_accessor(f)

        rows = iter(self)
        row = next(rows)
        v_prev = f(row)

        i = 1
        indices = [i]
        i += 1

        for _i_, row in enumerate(rows, i):
            v = f(row)

            if v != v_prev:
                indices.append(_i_)
                v_prev = v

        indices.append(len(self.matrix))
        indices = [(i_1, i_2) for i_1, i_2 in zip(indices, indices[1:])]

        return indices

    def replace_matrix(self, m):
        self._num_cols = None

        self.headers = None
        self.matrix = self._to_flux_rows(m)


    def to_csv(self, path, encoding=None):
        m = list(self.rows())

        path = apply_file_extension(path, '.csv')
        write_file(path, m, encoding=encoding)

    @classmethod
    def from_csv(cls, path, encoding=None):
        m = read_file(path, encoding=encoding)

        return cls(m)

    def to_json(self, path=None, encoding=None):
        j = [row.dict() for row in self]
        j = p_json_dumps(j)

        if path is None:
            return j

        path = apply_file_extension(path, '.json')
        write_file(path, j, encoding=encoding)

    @classmethod
    def from_json(cls, path, encoding=None):

        rows = read_file(path, encoding=encoding)
        if rows:
            m = [list(d.values()) for d in rows]
            m.insert(0, list(rows[0].keys()))
        else:
            m = [[]]

        return cls(m)

    def serialize(self, path):
        """
        using pickle, while convenient,  also introduces significant security flaws
        you should be sure no malicious actors have access to the location of these files
        """
        path = apply_file_extension(path, '.flux')
        write_file(path, self)

    @classmethod
    def deserialize(cls, path):
        """
        using pickle, while convenient, also introduces significant security flaws
        you should be sure no malicious actors have access to the location of these files
        """
        path = apply_file_extension(path, '.flux')
        return read_file(path)

    def _matrix_index(self, reference):
        if isinstance(reference, (int, float)):
            return int(reference)

        anchors = {'*h': 0,
                   '*f': 1,
                   '*l': len(self.matrix) - 1}

        r_i = anchors.get(reference)
        if r_i is None:
            raise KeyError("invalid index '{}'".format(reference))

        return r_i

    def __row_values_accessor(self, f):
        """ convert f into a function that can retrieve values for each flux_row_cls """

        def row_values(row):
            """ return muliple values (as tuple) from each row """
            return tuple(row.values[c] for c in columns)

        def row_value(row):
            """ return single value from each row """
            return row.values[i]

        f = modify_iteration_depth(f, depth=0)
        if callable(f):
            return f

        self.__validate_accessor(f)

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

    def __validate_accessor(self, f):
        num_cols = len(self.headers) - 1

        if isinstance(f, (str, list, tuple)):
            _f_ = modify_iteration_depth(f, 1)

            invalid = [h for h in _f_
                         if isinstance(h, str)
                         if h not in self.headers]
            if invalid:
                raise KeyError("invalid column reference: {}".format(invalid))

            invalid = [i for i in _f_
                         if isinstance(i, int)
                         if i > num_cols]
            if invalid:
                raise KeyError("integer(s) out of bounds: {}".format(invalid))

        elif isinstance(f, int):
            if f > num_cols:
                raise KeyError("integer out of bounds: {}".format(f))

        else:
            raise TypeError("unhandled type conversion for '{}'".format(f))

    @staticmethod
    def __validate_matrix(m):
        base_names = set(base_class_names(m))

        if 'DataFrame' in base_names:
            raise NotImplementedError("conversion of 'DataFrame' not supported yet")

        if 'ndarray' in base_names:
            raise NotImplementedError("conversion of 'ndarray' not supported yet")

        if base_names & {'flux_cls', 'excel_levity_cls'}:
            m = list(m.rows())

        m = iterator_to_list(m)

        if iteration_depth(m) != 2:
            raise IndexError('matrix must have exactly 2 dimensions')

        if is_flux_row_class(m[0]):
            m = [m[0].names] + [row.values for row in m]

        return m

    @staticmethod
    def __validate_headers(headers):
        conflicting = set(headers) & flux_row_cls.class_names
        if conflicting:
            raise NameError('conflicting name(s) {} found in header row: {}'.format(list(conflicting), headers))

    @staticmethod
    def __validate_column_names(names):
        names = modify_iteration_depth(names, depth=1)

        duplicates = [n for n, count in Counter(names).items() if count > 1]
        if duplicates:
            raise ValueError('duplicate column name(s) detected:\n{}'.format(duplicates))

        return names

    def __len__(self):
        return len(self.matrix)

    def __getitem__(self, row_or_col):
        """ returns flux_row, flux_rows slice, or column values
        eg:
            flux_row  = flux[3]
            flux_rows = flux[3:5]
            values    = flux['col']
        """
        # flux_row
        if isinstance(row_or_col, int):
            return self.matrix[row_or_col]

        # flux_rows (slice)
        if isinstance(row_or_col, slice):
            i_1, i_2, step = row_or_col.start, row_or_col.stop, row_or_col.step
            if i_1 is not None:
                if i_1 < 0:
                    i_1 = len(self.matrix) + i_1

            if i_2 is not None:
                if i_2 < 0:
                    i_2 = len(self.matrix) + i_2

            return [row for row in islice(self.matrix, i_1, i_2, step)]

        # column values
        if row_or_col in self.headers:
            i = self.headers[row_or_col]
            return [row.values[i] for row in self]

        raise KeyError("undefined reference: '{}'".format(row_or_col))

    def __setitem__(self, col_name, col_values):
        """ sets values to a single column

        number of values must be equal to length of self.matrix - 1
        eg:
            flux['col'] = [None] * flux.num_rows
        """
        col_values = modify_iteration_depth(col_values, 1)

        nd = iteration_depth(col_values)
        if nd == 0:
            col_values = [col_values]
        elif nd == 2:
            col_values = transpose(col_values)[0]

        if len(col_values) != self.num_rows:
            raise ValueError('number of rows in column must match the number of rows in flux')

        if col_name not in self.headers:
            # potentially inefficient to init with Nones when values are known...
            self.append_columns(col_name)

        i = self.headers[col_name]
        for row, v in zip(self, col_values):
            row.values[i] = v

    def __iter__(self):
        return islice(self.matrix, 1, None)

    def __add__(self, flux_b):
        flux_final = self.copy()
        flux_final.append_rows(flux_b)

        return flux_final

    def __repr__(self):
        if self.is_empty:
            return '(empty)'

        headers = list(self.headers.keys())
        headers = str(headers).replace("'", '')

        return '({:,})  {}'.format(self.num_rows, headers)


