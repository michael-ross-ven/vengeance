
from collections import Counter
from collections import namedtuple
from copy import copy
from copy import deepcopy

from .flux_row_cls import flux_row_cls

from ..util.filesystem import file_extension
from ..util.filesystem import read_file
from ..util.filesystem import write_file
from ..util.filesystem import binary_extensions

from ..util.iter import OrderedDefaultDict
from ..util.iter import base_class_names
from ..util.iter import is_exhaustable
from ..util.iter import is_subscriptable
from ..util.iter import iteration_depth
from ..util.iter import map_numeric_indices
from ..util.iter import modify_iteration_depth
from ..util.iter import transpose
from ..util.text import json_dumps_extended
from ..util.text import print_runtime

from ..conditional import ordereddict_
from ..conditional import line_profiler_installed

if line_profiler_installed:
    from line_profiler import LineProfiler


class flux_cls:
    """ primary data management class
    eg:
        matrix = [['col_a', 'col_b', 'col_c'],
                  ['a', 'b', 'c'],
                  [1, 2, 3],
                  [None, None, None]]
        flux = flux_cls(matrix)
    """

    def __init__(self, matrix=None):
        (self.headers,
         self.matrix) = self.to_flux_rows(matrix)

    @classmethod
    def to_flux_rows(cls, matrix, headers=None):
        matrix = cls.__validate_modify_matrix(matrix)
        if headers is None:
            cls.__validate_no_reserved_headers(matrix[0])
            headers = map_numeric_indices(matrix[0])

        return headers, [flux_row_cls(headers, row) for row in matrix]

    # region {filesystem methods}
    def to_file(self, path, encoding=None, fkwargs=None):
        extn = file_extension(path)

        if extn == '.csv':
            self.to_csv(path, encoding, fkwargs)
        elif extn == '.json':
            self.to_json(path, encoding, fkwargs)
        elif extn in binary_extensions:
            self.serialize(path, fkwargs)
        else:
            raise ValueError("invalid file extension for '{}'".format(path))

    @classmethod
    def from_file(cls, path, encoding=None, fkwargs=None):
        extn = file_extension(path)

        if extn == '.csv':
            return cls.from_csv(path, encoding, fkwargs)
        if extn == '.json':
            return cls.from_json(path, encoding, fkwargs)
        if extn in binary_extensions:
            return cls.deserialize(path, fkwargs)

        raise ValueError("invalid file extension for '{}'".format(path))

    def to_csv(self, path, encoding=None, fkwargs=None):
        if file_extension(path) != '.csv':
            raise ValueError("file extension must end with '.csv'")

        m = self.rows()
        write_file(path, m, encoding, fkwargs)

    @classmethod
    def from_csv(cls, path, encoding=None, fkwargs=None):
        if file_extension(path) != '.csv':
            raise ValueError("file extension must end with '.csv'")

        m = read_file(path, encoding, fkwargs)
        return cls(m)

    def to_json(self, path=None, encoding=None, fkwargs=None):
        if file_extension(path) != '.json':
            raise ValueError("file extension must end with '.json'")

        if self.is_empty or self.num_rows == 0:
            j = [{}]
        else:
            j = [row.dict() for row in self.matrix[1:]]

        if path is None:
            return json_dumps_extended(j, **fkwargs)
        else:
            write_file(path, j, encoding, fkwargs)

    @classmethod
    def from_json(cls, path, encoding=None, fkwargs=None):
        if file_extension(path) != '.json':
            raise ValueError("file extension must end with '.json'")

        j = read_file(path, encoding, fkwargs)

        if not j:
            m = [[]]
        else:
            m = [list(j[0].keys())] + \
                [list(row.values()) for row in j]

        return cls(m)

    def serialize(self, path, fkwargs=None):
        """
        although convenient, pickle introduces significant security flaws
        you should be sure no malicious actors have access to the location of these files
        """
        if file_extension(path) not in binary_extensions:
            raise ValueError("file extension must end with {}".format(binary_extensions))

        write_file(path, self, fkwargs=fkwargs)

    @classmethod
    def deserialize(cls, path, fkwargs=None):
        """
        although convenient, pickle introduces significant security flaws
        you should be sure no malicious actors have access to the location of these files
        """
        if file_extension(path) not in binary_extensions:
            raise ValueError("file extension must end with {}".format(binary_extensions))

        return read_file(path, fkwargs=fkwargs)
    # endregion

    @property
    def header_names(self):
        """
        self.matrix[0].values and self.headers.keys may not always be identical
            map_numeric_indices() makes certain modifications to self.headers.keys,
            such as coercing values to strings, modifying duplicate values, etc
        """
        return list(self.headers.keys())

    @property
    def preview(self):
        """ peek at values of header row + first five rows
        acts like pandas.DataFrame.head
        """
        return [row.values for row in self.matrix[:6]]

    @property
    def is_empty(self):
        for row in self.matrix:
            if any(row.values):
                return False

        return True

    @property
    def num_rows(self):
        """ header row excluded """
        if self.is_empty:
            return -1

        return len(self.matrix) - 1

    @property
    def num_cols(self):
        return len(self.matrix[0].values)

    @property
    def min_num_cols(self):
        return min(map(len, self.matrix))

    @property
    def max_num_cols(self):
        return max(map(len, self.matrix))

    @property
    def is_jagged(self):
        num_cols = self.num_cols
        for row in self.matrix[1:]:
            if len(row.values) != num_cols:
                return True

        return False

    def rows(self, r_1=0, r_2=None):
        return (row.values for row in self.matrix[r_1:r_2])

    def flux_rows(self, r_1=0, r_2=None):
        return (row for row in self.matrix[r_1:r_2])

    def columns(self, *names, headers=False):
        names   = modify_iteration_depth(names, depth=1)
        indices = self.__validate_modify_column_indices(names, self.headers)

        if headers:
            m = self.matrix
        else:
            m = self.matrix[1:]

        f = self.__row_values_accessor(indices)
        c = [f(row) for row in m]
        if len(indices) > 1:
            c = [list(v) for v in transpose(c)]

        return c

    def execute_commands(self, commands, use_profiler=False):
        profiler = self.__validate_modify_profiler_function(use_profiler)
        commands = self.__parse_commands(commands)

        completed_commands = []
        for command in commands:
            methodname = command.name
            if profiler:
                flux_method = profiler(command.method)
            else:
                flux_method = command.method

            if command.num_args == 0:
                flux_method()
            elif command.num_args == 1:
                flux_method(command.args)
            else:
                flux_method(*command.args)

            completed_commands.append(methodname)

        if hasattr(profiler, 'print_stats'):
            profiler.print_stats()

        return completed_commands

    def __parse_commands(self, commands):
        parsed = []
        nt_cls = namedtuple('command_nt', 'name method args num_args')

        for command in commands:
            if isinstance(command, (list, tuple)):
                name, args = command

                if isinstance(args, dict):
                    raise NotImplementedError('keyword args not supported yet')

                if isinstance(args, str):
                    num_args = 1
                else:
                    num_args = len(args)

            else:
                name = command
                args = tuple()
                num_args = 0

            if name.startswith('__'):
                name = '_{}{}'.format(self.__class__.__name__, name)

            method = getattr(self, name)
            parsed.append(nt_cls(name, method, args, num_args))

        return parsed

    def replace_matrix(self, m):
        self.headers, self.matrix = self.to_flux_rows(m)

    def matrix_by_headers(self, *names):
        if self.is_empty:
            return self

        names = modify_iteration_depth(names, depth=1)
        if isinstance(names, dict):
            names = [names]

        blank_column = None

        columns = [list(v) for v in transpose([row.values for row in self.matrix[1:]])]
        columns = columns or [[]]

        m = []
        for header in names:
            header = self.__renamed_or_inserted_header(header)

            if header in self.headers:
                i = self.headers[header]
                column = columns[i]
            else:
                if blank_column is None:
                    blank_column = [None for _ in range(self.num_rows)]
                column = blank_column

            column = copy(column)
            column.insert(0, header)

            m.append(column)

        m = [list(row) for row in transpose(m)]
        self.headers, self.matrix = self.to_flux_rows(m)

        return self

    def __renamed_or_inserted_header(self, header):
        """
        parentheses around inserted headers:
            to ensure new columns are being created intentionally and not because
            of spelling errors, inserted headers must be surrounded by parenthesis,
            eg: '(inserted_header)'
        """
        if not isinstance(header, (dict, str)):
            raise TypeError('{}\nheader must be either dictionary or string'.format(header))

        if isinstance(header, dict):
            if len(header) != 1:
                raise ValueError('only a single {old, new} pair permitted for new header mapping')

            h_old, h_new = list(header.items())[0]
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

    def rename_columns(self, old_to_new_headers):
        header_values = self.matrix[0].values

        for h_old, h_new in old_to_new_headers.items():
            i = self.headers[h_old]
            header_values[i] = h_new

        self._reapply_header_names(header_values)

    def insert_columns(self, *names):
        """ eg:
            flux.insert_columns((0, 'inserted'))         # insert column at beginning
            flux.insert_columns((3, 'inserted'))         # insert column before column 3
            flux.insert_columns(('col_c', 'inserted'))   # insert column before column 'col_c'
            flux.insert_columns((-1, 'inserted'))        # insert column before end
            flux.insert_columns((1, 'inserted_a'),       # insert columns
                                (1, 'inserted_b'),
                                (1, 'inserted_c'))
        """
        if not names:
            return

        names = self.__validate_modify_inserted_names(names, self.headers)
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
            for row in self.matrix[1:]:
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
            for row in self.matrix[1:]:
                row.values.extend(columns)

            return

        if len(values) != self.num_rows:
            raise ValueError('number of values must match the number of rows in flux')

        for row, v in zip(self, values):
            row.values.append(v)

    def delete_columns(self, *names):
        if not names:
            return

        names = modify_iteration_depth(names, depth=1)
        self.__validate_no_duplicates(names)

        indices = self.__validate_modify_column_indices(names, self.headers)
        indices.sort(reverse=True)

        for row in self.matrix:
            for i in indices:
                del row.values[i]

        self._reapply_header_names(self.matrix[0].values)

    def identify_jagged_rows(self):
        num_cols = self.num_cols

        jagged_items = []
        for i, row in enumerate(self.matrix[1:]):
            if len(row.values) != num_cols:
                jagged_items.append((i, row))

        return jagged_items

    def insert_rows(self, i, rows):
        if self.is_empty:
            self.headers, self.matrix = self.to_flux_rows(rows)
            return

        if i == 0:
            del self.matrix[0]

            headers, matrix  = self.to_flux_rows(rows)
            self.headers     = headers
            self.matrix[i:i] = matrix

            return

        _, matrix = self.to_flux_rows(rows, self.headers)
        self.matrix[i:i] = matrix

    def append_rows(self, rows):
        if self.is_empty:
            self.headers, self.matrix = self.to_flux_rows(rows)
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
        m = [copy(self.matrix[0].values)] + \
            [copy(row.values) for row in self.__sort_rows(names, reverse)]

        flux = self.__class__(m)

        return flux

    def __sort_rows(self, names, order):
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

        # sort priority from left to right; leftmost column sorted last
        names = reversed(names)
        order = reversed(order)

        for f, o in zip(names, order):
            f = self.__row_values_accessor(f)
            o = bool(o)
            m.sort(key=f, reverse=o)

        return m

    def filter(self, f, *args, **kwargs):
        """ in-place """
        self.matrix[1:] = [row for row in self.matrix[1:]
                               if f(row, *args, **kwargs)]

    def filtered(self, f, *args, **kwargs):
        """ :return: new flux_cls """
        m = [copy(self.matrix[0].values)]
        m.extend([copy(row.values) for row in self.matrix[1:]
                                   if f(row, *args, **kwargs)])

        flux = self.__class__(m)

        return flux

    def filter_by_unique(self, *names):
        self.__filter_unique_rows(*names, in_place=True)

    def filtered_by_unique(self, *names):
        return self.__filter_unique_rows(*names, in_place=False)

    def __filter_unique_rows(self, *names, in_place):
        def evaluate_unique(row):
            """ first-class function """
            v = f(row)

            if v not in u:
                u.add(v)
                return True
            else:
                return False

        u = set()
        f = self.__row_values_accessor(names)

        if in_place:
            self.filter(evaluate_unique)
        else:
            return self.filtered(evaluate_unique)

    def unique(self, *names):
        f = self.__row_values_accessor(names)
        items = ((f(row), None) for row in self.matrix[1:])

        return ordereddict_(items).keys()

    # noinspection DuplicatedCode
    def index_row(self, *names, as_namedtuples=False):
        """ :return: dictionary of {v(row): row}

        rows with non-unique keys are overwritten
        """
        f = self.__row_values_accessor(names)

        if as_namedtuples:
            ntc   = namedtuple('flux_row_ntc', self.headers.keys())
            items = ((f(row), ntc(*row.values)) for row in self.matrix[1:])
        else:
            items = ((f(row), row) for row in self.matrix[1:])

        return ordereddict_(items)

    # noinspection DuplicatedCode
    def index_rows(self, *names, as_namedtuples=False):
        """ :return: dictionary of {v(row): [rows]}

        rows with non-unique keys are appended to a list
        """
        f = self.__row_values_accessor(names)

        if as_namedtuples:
            ntc   = namedtuple('flux_row_ntc', self.headers.keys())
            items = ((f(row), ntc(*row.values)) for row in self.matrix[1:])
        else:
            items = ((f(row), row) for row in self.matrix[1:])

        return (OrderedDefaultDict(list, items)
                .ordereddict())

    def namedtuples(self, r_1=1, r_2=None):
        ntc = namedtuple('flux_row_ntc', self.headers.keys())

        for i, row in enumerate(self.matrix[r_1:r_2], r_1):
            try:
                yield ntc(*row.values)
            except TypeError as e:
                if len(row) != self.num_cols:
                    raise TypeError('{}\n(jagged row at matrix index: {})'.format(e, i)) from e
                else:
                    raise e

    def label_row_indices(self, start=0):
        """ meant to assist with debugging;

        label each flux_row_cls.__dict__ with an index, which will then appear
        in each row's __repr__ function and make them easier to identify after
        filtering, sorting, etc
        """
        if 'i' in self.headers:
            raise AssertionError("'i' already exists as header name")

        for i, row in enumerate(self.matrix, start):
            row.__dict__['i'] = i

    def copy(self, deep=False):
        if deep:
            return deepcopy(self)

        m = [copy(row.values) for row in self.matrix]
        flux = self.__class__(m)

        return flux

    def contiguous_indices(self, *names):
        """ :return: yield (i_1, i_2) indices where values are identical """
        if self.is_empty:
            raise TypeError('matrix is empty')

        f = self.__row_values_accessor(names)

        i_1 = 1
        v_1 = f(self.matrix[i_1])

        for i_2, row in enumerate(self.matrix[i_1+1:], i_1 + 1):
            v_2 = f(row)

            if v_2 != v_1:
                if i_2 - 1 != i_1:
                    yield i_1, i_2 - 1

                v_1 = v_2
                i_1 = i_2

        yield i_1, self.num_rows

    def _reapply_header_names(self, headers):
        """
        reassignment of self.headers will de-reference all flux_row_cls._headers
        in self.matrix. To prevent this, self.headers.clear() must be called,
        followed by individual reassignment of new values
        """
        self.headers.clear()
        for h, i in map_numeric_indices(headers).items():
            self.headers[h] = i

    def __row_values_accessor(self, names):
        """ :return: a function that retrieves column values for each flux_row_cls """

        # region {closure functions}
        def row_slice(row):
            return tuple(row.values[i])

        def row_values(row):
            """ return muliple column values from each row """
            return tuple([row.values[_i_] for _i_ in indices])

        def row_value(row):
            """ return single column value from each row """
            return row.values[i]
        # endregion

        names = modify_iteration_depth(names, depth=0)

        if callable(names):
            f = names
        elif isinstance(names, slice):
            i = names
            f = row_slice
        elif iteration_depth(names) == 0:
            i = self.__validate_modify_column_indices([names], self.headers)[0]
            f = row_value
        else:
            indices = self.__validate_modify_column_indices(names, self.headers)
            f = row_values

        return f

    def __len__(self):
        return self.num_rows

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
        nd = iteration_depth(name)
        if nd > 0:
            raise AssertionError('values must be set one column at a time')

        if nd == 2:
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
        return (row for row in self.matrix[1:])

    def __add__(self, rows):
        flux_final = self.copy()
        flux_final.append_rows(rows)

        return flux_final

    def __iadd__(self, rows):
        self.append_rows(rows)

        return self

    def __getstate__(self):
        is_sublcassed = (type(self) == flux_cls and
                         type(self.matrix[0]) == flux_row_cls)
        if is_sublcassed:
            return list(self.rows())
        
        return self.__dict__

    def __setstate__(self, v):
        if isinstance(v, list):
            # call constructor directly
            self.__init__(v)
        else:
            setattr(self, '__dict__', v)

    def __repr__(self):
        if self.is_empty:
            return '(empty)'

        headers = list(self.headers.keys())
        headers = str(headers).replace("'", '').replace('"', '')

        return '({:,})  {}'.format(self.num_rows, headers)

    # region {validation functions}
    @staticmethod
    def __validate_modify_matrix(m):
        """ validate matrix datatype and has at least 2 dimensions;
        convert matrix to list of lists if neccessary
        """
        if m is None:
            return [[]]

        base_names = set(base_class_names(m))

        if ('flux_cls' in base_names) or ('excel_levity_cls' in base_names):
            return [copy(row) for row in m.rows()]

        if 'DataFrame' in base_names:
            raise NotImplementedError('DataFrame not supported')
        elif 'ndarray' in base_names:
            raise NotImplementedError('ndarray not supported (must be native python lists)')
        elif is_exhaustable(m):
            raise NotImplementedError('exhaustable iterators must be converted to lists')
        elif not is_subscriptable(m):
            raise TypeError("invalid type: <'{}'> (matrix must be a list of lists)".format(type(m)))
        elif iteration_depth(m) < 2:
            raise IndexError('matrix must have at least two dimensions (one dimension for rows, one for columns)')
        elif 'flux_row_cls' in base_class_names(m[0]):

            first_row = m[0]
            if first_row.is_header_row():
                m = [copy(row.values) for row in m]
            else:
                m = [first_row.names] + \
                    [copy(row.values) for row in m]

        return m

    @staticmethod
    def __validate_modify_profiler_function(use_profiler):
        if use_profiler is False:
            return None

        if use_profiler is True:
            if line_profiler_installed:
                return LineProfiler()
            else:
                return print_runtime

        profiler = str(use_profiler).lower()
        if profiler == 'print_runtime':
            return print_runtime

        if profiler in ('line_profiler', 'lineprofiler'):
            if line_profiler_installed is False:
                raise ImportError("'line_profiler' package not installed")
            else:
                return LineProfiler()

        raise ValueError("invalid profiler: '{}'".format(profiler))

    @classmethod
    def __validate_modify_inserted_names(cls, inserted, headers):
        inserted = modify_iteration_depth(inserted, depth=0)

        nd = iteration_depth(inserted)
        if nd == 1 and len(inserted) == 2:
            inserted = [inserted]
        elif nd == 0:
            raise ValueError("inserted values should be (int, 'column_name') tuples")
        else:
            for item in inserted:
                if iteration_depth(item) != 1 or len(item) != 2:
                    raise ValueError("inserted values should be (int, 'column_name') tuples")

        indices, names = [n for n in zip(*inserted)]
        cls.__validate_no_index_errors_with_headers(indices, headers)
        cls.__validate_no_duplicates(names)
        cls.__validate_no_overlap_with_headers(names, headers)

        return inserted

    @staticmethod
    def __validate_no_reserved_headers(names):
        conflicting = set(names) & flux_row_cls.class_names
        if conflicting:
            raise ValueError('conflicting name(s) {} found in header row: {}'.format(list(conflicting), names))

    @staticmethod
    def __validate_no_duplicates(names):
        duplicates = [n for n, count in Counter(names).items() if count > 1]
        if duplicates:
            raise ValueError('duplicate column name(s) detected:\n{}'.format(duplicates))

    @staticmethod
    def __validate_no_overlap_with_headers(names, headers):
        invalid = headers.keys() & set(names)
        if invalid:
            raise ValueError('column name(s) conflict with existing headers:\n{}'.format(list(invalid)))

    @staticmethod
    def __validate_complete_overlap_with_headers(names, headers):
        _names_ = set(s for s in names if not isinstance(s, int))
        invalid = _names_ - headers.keys()
        if invalid:
            raise ValueError('columns do not exist:\n{}'.format(list(invalid)))

    @classmethod
    def __validate_no_index_errors_with_headers(cls, names, headers):
        cls.__validate_complete_overlap_with_headers(names, headers)

        num_cols = len(headers) - 1
        invalid  = [i for i in names
                      if isinstance(i, int)
                      if i > num_cols]
        if invalid:
            raise ValueError('column indices out of bounds:\n{}'.format(invalid))

    @classmethod
    def __validate_modify_column_indices(cls, names, headers):
        cls.__validate_no_index_errors_with_headers(names, headers)

        header_indices = list(range(len(headers)))
        indices = [headers.get(str(n), n) for n in names]       # convert names to integers
        indices = [header_indices[i] for i in indices]          # convert any negative indices to positive indices

        return indices
    # endregion


