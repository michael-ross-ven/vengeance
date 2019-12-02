
from copy import deepcopy
from collections import OrderedDict
from collections import Counter
from collections import namedtuple

from .. util.filesystem import write_file
from .. util.filesystem import read_file
from .. util.filesystem import apply_file_extension

from .. util.iter import OrderedDefaultDict
from .. util.iter import iterator_to_list
from .. util.iter import iteration_depth
from .. util.iter import modify_iteration_depth
from .. util.iter import transpose
from .. util.iter import index_sequence
from .. util.iter import ordered_unique
from .. util.iter import base_class_names
from .. util.iter import is_flux_row_class

from .. util.text import p_json_dumps
from .. util.text import print_runtime

from . flux_row_cls import flux_row_cls


class flux_cls:

    def __init__(self, matrix=None):
        headers, matrix = flux_cls.to_flux_rows(matrix)

        self.headers = headers
        self.matrix  = matrix

    @classmethod
    def to_flux_rows(cls, matrix, headers=None):
        matrix = matrix or [[]]
        matrix = cls.__validate_modify_matrix(matrix)

        if headers is None:
            cls.__validate_no_reserved_headers(matrix[0])
            headers = index_sequence(matrix[0])

        matrix = [flux_row_cls(headers, row) for row in matrix]

        return headers, matrix

    @property
    def header_values(self):
        """
        there may be a discrepancy between self.matrix[0].values and self.headers.keys
            index_sequence() makes certain modifications to self.headers.keys,
            such as coercing values to strings, modifying duplicate values, etc
        """
        return list(self.headers.keys())

    @property
    def first_five_rows(self):
        return [row.values for row in self.matrix[:6]]

    @property
    def num_rows(self):
        """ header row excluded """
        return len(self.matrix) - 1

    @property
    def num_cols(self):
        return len(self.matrix[0].values)

    @property
    def max_num_cols(self):
        m = [row.values for row in self.matrix]
        return max(map(len, m))

    @property
    def is_jagged(self):
        num_cols = self.num_cols

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

    def rows(self, r_1=0, r_2='*l'):
        r_1 = self.__matrix_row_index(r_1)
        r_2 = self.__matrix_row_index(r_2) + 1

        return (row.values for row in self.matrix[r_1:r_2])

    def flux_rows(self, r_1=0, r_2='*l'):
        r_1 = self.__matrix_row_index(r_1)
        r_2 = self.__matrix_row_index(r_2) + 1

        return (row for row in self.matrix[r_1:r_2])

    def __matrix_row_index(self, r):
        anchors = {'*h': 0,
                   '*f': 1,
                   '*l': self.num_rows}

        r_i = anchors.get(r, r)
        if not isinstance(r_i, int):
            raise ValueError("invalid row reference '{}'".format(r))

        return r_i

    def execute_commands(self, commands, profile=False):
        profiler = self.__profiler_function(profile)
        commands = self.__parse_commands(commands)

        completed_commands = []

        for command in commands:
            completed_commands.append(command.name)

            if profiler:
                method = profiler(command.method)
            else:
                method = command.method

            if command.num_args == 0:
                method()
            elif command.num_args == 1:
                method(command.args)
            else:
                method(*command.args)

        if hasattr(profiler, 'print_stats'):
            profiler.print_stats()

    @staticmethod
    def __profiler_function(profile):
        if not profile:
            return None

        if profile == 'print_runtime':
            return print_runtime

        try:
            # noinspection PyUnresolvedReferences
            from line_profiler import LineProfiler
            return LineProfiler()

        except ImportError as e:
            if str(profile).lower() in ('line_profiler', 'lineprofiler'):
                raise ImportError('line_profiler site-package not installed') from e

        return print_runtime

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

    def matrix_by_headers(self, *names):
        names   = modify_iteration_depth(names, depth=1)
        columns = transpose([row.values for row in self]) or [[]]

        m = []
        for header in names:
            header = self.__renamed_or_inserted_header(header)

            if header in self.headers:
                i = self.headers[header]
                column = columns[i]
            else:
                column = [None] * self.num_rows

            column.insert(0, header)
            m.append(column)

        m = transpose(m)

        (self.headers, self.matrix) = self.to_flux_rows(m)

    def __renamed_or_inserted_header(self, header):
        """
        parentheses around inserted headers:
            to ensure new columns are being created intentionally and not because
            of spelling errors, inserted headers must be surrounded by parenthesis,
            eg: '(inserted_header)'
        """
        if not isinstance(header, (dict, tuple, str)):
            raise ValueError('{}\nheader must be either dictionary or string'.format(header))

        if isinstance(header, dict):
            h_old, h_new = tuple(header.items())[0]
            self.headers[h_new] = self.headers[h_old]

            return h_new

        if isinstance(header, tuple):
            h_old, h_new = header
            self.headers[h_new] = self.headers[h_old]

            return h_new

        if header in self.headers:
            return header

        if header.startswith('(') and header.endswith(')'):
            return header[1:-1]

        if header not in self.headers:
            raise ValueError("'{header}' does not exist\ninserted columns should be surrounded "
                             "by parenthesis, ie '({header})' not '{header}'".format(header=header))

        return header

    def columns(self, *names):
        """ :return column values """
        names = modify_iteration_depth(names, depth=1)
        names = self.__names_to_column_indices(names, self.headers)

        f = self.__row_values_accessor(names)
        m = [f(row) for row in self]

        if len(names) > 1:
            return transpose(m)

        return m

    def rename_columns(self, old_to_new_headers):
        header_values = self.matrix[0].values

        for h_old, h_new in old_to_new_headers.items():
            i = self.headers[h_old]
            header_values[i] = h_new

        self._reapply_header_names(header_values)

    def insert_columns(self, *names):
        """
        eg names:
            flux.insert_columns((0, 'inserted'))         insert column at beginning
            flux.insert_columns((3, 'inserted'))         insert column before column 3
            flux.insert_columns(('col_c', 'inserted'))   insert column before column 'col_c'
            flux.insert_columns((-1, 'inserted'))        insert column before end

            flux.insert_columns((1, 'inserted_a'),       insert columns before column 1
                                (1, 'inserted_b'),
                                (1, 'inserted_c'))
        """
        if not names:
            return

        names = self.__validate_modify_inserted_names(names)
        names = list(reversed(names))

        header_values = self.matrix[0].values

        num_inserted = 0
        for before, header in names:
            if isinstance(before, int):
                i = before
            else:
                i = header_values.index(before)

            header_values.insert(i, header)
            num_inserted += 1

        indices = [header_values.index(h) for _, h in names]
        indices.sort()

        self._reapply_header_names(header_values)

        for i in indices:
            for row in self:
                row.values.insert(i, None)

    def append_columns(self, *names, values=None):
        if not names:
            return

        names = modify_iteration_depth(names, depth=1)
        self.__validate_no_duplicates(names)
        self.__validate_no_overlap_with_headers(names, self.headers)

        header_values = self.matrix[0].values
        header_values.extend(names)
        self._reapply_header_names(header_values)

        if values is None:
            columns = [None for _ in range(len(names))]
            for row in self:
                row.values.extend(columns)

            return

        if iteration_depth(values) != 1:
            raise ValueError('iteration depth of values must be exactly one')

        if len(values) != self.num_rows:
            raise ValueError('number of values must match the number of rows in flux')

        for row, v in zip(self, values):
            row.values.append(v)

    def delete_columns(self, *names):
        if not names:
            return

        names = modify_iteration_depth(names, depth=1)

        self.__validate_no_duplicates(names)
        self.__validate_no_index_errors_with_headers(names, self.headers)

        indices = self.__names_to_column_indices(names, self.headers)
        indices.sort(reverse=True)

        for row in self.matrix:
            for c in indices:
                del row.values[c]

        self._reapply_header_names(self.matrix[0].values)

    def identify_jagged_columns(self):
        num_cols = self.num_cols

        row_indices = []
        for i, row in enumerate(self.matrix):
            if len(row.values) != num_cols:
                row_indices.append((i, row))

        return row_indices

    def fill_jagged_columns(self):
        max_cols = self.max_num_cols

        row_indices = []
        for i, row in enumerate(self.matrix):
            num_missing = max_cols - len(row.values)

            if num_missing > 0:
                row_indices.append((i, row))
                row.values.extend([None for _ in range(num_missing)])

                if i == 0:
                    self._reapply_header_names(row.values)

        return row_indices

    def insert_rows(self, i, rows):
        if self.is_empty:
            (self.headers, self.matrix) = self.to_flux_rows(rows)
            return

        if i == 0:
            del self.matrix[0]
            # (self.headers, self.matrix) = self.to_flux_rows(rows)
            #
            # return

        _, matrix = self.to_flux_rows(rows, self.headers)
        self.matrix[i:i] = matrix

    def append_rows(self, rows):
        if self.is_empty:
            (self.headers, self.matrix) = self.to_flux_rows(rows)
            return

        _, matrix = self.to_flux_rows(rows, self.headers)
        self.matrix += matrix

    def sort(self, *names, reverse=None):
        """ in-place sort

        eg:
            flux.sort('col_a')
            flux.sort('col_a', 'col_b', 'col_c',
                      reverse=[True, False, True])
        """
        self.matrix[1:] = self.__sort_rows(names, reverse)

    def sorted(self, *names, reverse=None):
        """ :return: sorted flux_cls

        eg:
            flux = flux.sorted('col_a')
            flux = flux.sorted('col_a', 'col_b', 'col_c',
                               reverse=[False, True, True])
        """
        m = [self.matrix[0].values.copy()]
        m += [row.values.copy() for row in self.__sort_rows(names, reverse)]

        flux = self.__class__(m)

        return flux

    def __sort_rows(self, names, order):
        """
        sort priority from left to right:
            names and order must be reversed
            rightmost column sorted first
            leftmost column sorted last
        """
        if isinstance(order, bool):
            order = [order]
        else:
            order = order or []

        if not isinstance(order, (list, tuple)):
            raise TypeError('reverse must be a list of booleans')

        names = modify_iteration_depth(names, depth=1)
        for _ in range(len(names) - len(order)):
            order.append(False)

        m = self.matrix[1:]
        names = reversed(names)
        order = reversed(order)

        for f, o in zip(names, order):
            f = self.__row_values_accessor(f)
            o = bool(o)
            m.sort(key=f, reverse=o)

        return m

    def filter(self, f, *args, **kwargs):
        """ in-place """
        self.matrix[1:] = [row for row in self if f(row, *args, **kwargs)]

    def filtered(self, f, *args, **kwargs):
        """ :return: new flux_cls """
        m = [self.matrix[0].values.copy()]
        m.extend([row.values.copy() for row in self if f(row, *args, **kwargs)])

        flux = self.__class__(m)

        return flux

    def filter_by_unique(self, *f):
        self.__filter_unique_rows(*f, in_place=True)

    def filtered_by_unique(self, *f):
        return self.__filter_unique_rows(*f, in_place=False)

    def __filter_unique_rows(self, *f, in_place):

        def evaluate_unique(row):
            """ first-class function for .filter() """
            v = f(row)
            if v not in u:
                u.add(v)
                return True
            else:
                return False

        u = set()
        f = self.__row_values_accessor(f)

        if in_place:
            self.filter(evaluate_unique)
        else:
            return self.filtered(evaluate_unique)

    def unique_values(self, *f):
        """ :return: list of ordered, unique values from [f(row)] """
        f = self.__row_values_accessor(f)
        return ordered_unique(f(row) for row in self)

    def index_row(self, *f):
        """ :return: dictionary of {f(row): row}

        (rows with non-unique keys are overwritten)
        """
        f = self.__row_values_accessor(f)
        return OrderedDict((f(row), row) for row in self)

    def index_rows(self, *f):
        """ :return: dictionary of {f(row): [row(s)]}

        (rows with non-unique keys are appended to a list)
        """
        f = self.__row_values_accessor(f)
        d = OrderedDefaultDict(list, [(f(row), row) for row in self])

        return d.ordereddict()

    def namedtuples(self):
        try:
            nt_cls = namedtuple('flux_row_nt', self.headers.keys())
            return [nt_cls(*row.values) for row in self]

        except TypeError as e:
            if self.is_jagged:
                i = [item[0] for item in self.identify_jagged_columns()][:3]
                raise TypeError('jagged rows detected in matrix: \n\t(indices {}...)'.format(i)) from e
            raise e
        except ValueError as e:
            import re
            names = [n for n in self.headers.keys() if re.search('^[^a-z]|[ ]', str(n), re.I)]
            if names:
                raise ValueError('invalid field(s) for namedtuple constructor: {}'.format(names)) from e
            raise e

    def enumerate_rows(self, start=0):
        """ label each flux_row_cls __dict__ with index; meant to assist with debugging """

        if 'i' in self.headers:
            raise AssertionError("'i' already exists as header name")

        for i, row in enumerate(self.matrix, start):
            row.__dict__['i'] = i

    def copy(self, deep=False):
        if deep:
            return deepcopy(self)

        m = [row.values.copy() for row in self.matrix]
        flux = self.__class__(m)

        return flux

    def contiguous_rows(self, *f):
        """ :return: list of flux_row_cls where values are identical """
        sections = []
        for i_1, i_2 in self.contiguous_indices(f):
            sections.append(self.matrix[i_1:i_2])

        return sections

    def contiguous_indices(self, *f):
        """ :return: list of (i_1, i_2) row indices where values are identical """
        if self.num_rows == 0 or self.is_empty:
            return []

        f = self.__row_values_accessor(f)
        rows   = iter(self)
        v_prev = f(next(rows))

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
        (self.headers, self.matrix) = self.to_flux_rows(m)

    def _reapply_header_names(self, headers):
        """
        reassignment of self.headers will de-reference all flux_row_cls._headers
        in self.matrix. To prevent this, self.headers.clear() must be called,
        followed by individual reassignment of new values
        """
        self.headers.clear()
        for h, i in index_sequence(headers).items():
            self.headers[h] = i

    def __row_values_accessor(self, names):
        """ :return: a function that retrieves values for each flux_row_cls """

        def row_values(row):
            """ return muliple values from each row """
            return tuple(row.values[_i_] for _i_ in indices)

        def row_value(row):
            """ return single value from each row """
            return row.values[i]

        names = modify_iteration_depth(names, depth=0)
        if callable(names):
            return names

        self.__validate_no_index_errors_with_headers(modify_iteration_depth(names, 1), self.headers)

        if isinstance(names, (list, tuple)):
            indices = self.__names_to_column_indices(names, self.headers)
            f = row_values
        else:
            i = self.headers.get(str(names), names)
            f = row_value

        return f

    # region {serialization methods}
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
        using pickle, while convenient, introduces significant security flaws
        you should be sure no malicious actors have access to the location of these files
        """
        path = apply_file_extension(path, '.flux')
        write_file(path, self)

    @classmethod
    def deserialize(cls, path):
        """
        using pickle, while convenient, introduces significant security flaws
        you should be sure no malicious actors have access to the location of these files
        """
        path = apply_file_extension(path, '.flux')
        return read_file(path)
    # endregion

    def __len__(self):
        return len(self.matrix)

    def __getitem__(self, name):
        """ :return column values """
        if isinstance(name, slice):
            indices = list(range(self.num_cols))
            name = indices[name]

        return self.columns(name)

    def __setitem__(self, name, values):
        """ sets values to a single column

        number of values must be equal to number of rows in matrix,
        excluding header row

        eg:
            flux['col'] = ['blah'] * flux.num_rows
        """
        if iteration_depth(name) > 0:
            raise AssertionError('values must be set one column at a time')

        if iteration_depth(values) == 2:
            values = transpose(values)[0]

        if len(values) != self.num_rows:
            raise ValueError('number of values must match the number of rows in flux')

        if name not in self.headers:
            self.append_columns(name, values=values)
        else:
            i = self.headers.get(str(name), name)
            for row, v in zip(self, values):
                row.values[i] = v

    def __iter__(self):
        return iter(self.matrix[1:])

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

    # region {validation functions}
    @staticmethod
    def __validate_modify_matrix(m):
        base_names = set(base_class_names(m))

        if 'DataFrame' in base_names:
            raise NotImplementedError('DataFrame matrix not supported')

        if 'ndarray' in base_names:
            raise NotImplementedError('ndarray not supported')

        if base_names & {'flux_cls', 'excel_levity_cls'}:
            m = list(m.rows())
        else:
            m = iterator_to_list(m)

        if iteration_depth(m) < 2:
            raise IndexError('matrix must have at least 2 dimensions')

        if is_flux_row_class(m[0]):
            m = [m[0].names] + [row.values for row in m]

        return m

    def __validate_modify_inserted_names(self, inserted):
        inserted = modify_iteration_depth(inserted, depth=0)

        nd = iteration_depth(inserted)
        if nd == 1 and len(inserted) == 2:
            inserted = [inserted]
        elif nd != 2:
            raise IndexError('inserted values should be tuples')

        before, names = [n for n in zip(*inserted)]
        self.__validate_no_index_errors_with_headers(before, self.headers)

        self.__validate_no_duplicates(names)
        self.__validate_no_overlap_with_headers(names, self.headers)

        return inserted

    @staticmethod
    def __validate_no_reserved_headers(names):
        conflicting = set(names) & flux_row_cls.class_names
        if conflicting:
            raise NameError('conflicting name(s) {} found in header row: {}'.format(list(conflicting), names))

    @staticmethod
    def __validate_no_duplicates(names):
        duplicates = [n for n, count in Counter(names).items() if count > 1]
        if duplicates:
            raise ValueError('duplicate column name(s) detected:\n{}'.format(duplicates))

    @staticmethod
    def __validate_no_overlap_with_headers(names, headers):
        invalid = list(headers.keys() & set(names))
        if invalid:
            raise ValueError('column name(s) conflict with existing headers:\n{}'.format(invalid))

    @staticmethod
    def __validate_complete_overlap_with_headers(names, headers):
        _names_ = set(s for s in names if not isinstance(s, int))
        invalid = _names_ - headers.keys()
        if invalid:
            raise ValueError('column(s) do not exist:\n{}'.format(invalid))

    def __validate_no_index_errors_with_headers(self, names, headers):
        self.__validate_complete_overlap_with_headers(names, headers)

        num_cols = len(headers) - 1
        invalid  = [i for i in names if isinstance(i, int) if i > num_cols]
        if invalid:
            raise IndexError('column(s) out of bounds:\n{}'.format(invalid))

    @staticmethod
    def __names_to_column_indices(names, headers):
        _indices_ = list(range(len(headers)))

        indices = [headers.get(str(h), h) for h in names]       # convert to integers
        indices = [_indices_[i] for i in indices]               # handle negative indices

        return indices
    # endregion


