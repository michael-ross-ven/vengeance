
import gc

from collections import Counter
from collections import namedtuple
from copy import deepcopy
from types import SimpleNamespace

from .flux_row_cls import flux_row_cls

from ..util.filesystem import parse_file_extension
from ..util.filesystem import read_file
from ..util.filesystem import write_file
from ..util.filesystem import pickle_extensions

from ..util.iter import IterationDepthError
from ..util.iter import ColumnNameError
from ..util.iter import base_class_names
from ..util.iter import is_exhaustable
from ..util.iter import is_collection
from ..util.iter import is_subscriptable
from ..util.iter import is_vengeance_class
from ..util.iter import standardize_variable_arity_arguments
from ..util.iter import iteration_depth
from ..util.iter import map_to_numeric_indices
from ..util.iter import are_indices_contiguous
from ..util.iter import modify_iteration_depth
from ..util.iter import transpose
from ..util.iter import transpose_as_lists

from ..util.text import print_runtime
from ..util.text import json_dumps_extended
from ..util.text import deprecated
from ..util.text import object_name
from ..util.text import format_header
from ..util.text import format_header_lite
from ..util.text import format_integer

from ..conditional import ordereddict
from ..conditional import line_profiler_installed
from ..conditional import numpy_installed

if numpy_installed:
    import numpy


class flux_cls:
    """ primary data management class

    * converts a list of lists (a matrix) to a list of flux_row_cls objects
    * similar to a pandas DataFrame, but optimized for row-major ordered operations (df.iterrows())

    eg:
        matrix = [['col_a', 'col_b', 'col_c'],
                  ['a', 'b', 'c']]
        flux = flux_cls(matrix)
        flux = flux_cls.from_csv('file.csv')

        for row in flux:
            a = row.col_a
            row.col_a = None
            
        flux['col_d'] = [o.upper() for c in flux['col_a']]
        flux.sort('col_a', 'col_b')
        flux.filter(lambda: row: row.col_a == 'value')
        
        flux.to_csv('file.csv')
        flux = flux_cls.from_csv('file.csv')
    """

    def __init__(self, matrix=None):
        was_gc_enabled = gc.isenabled()
        gc.disable()

        matrix  = self.__validate_matrix(matrix)
        headers = self.__validate_matrix_headers(matrix[0])
        matrix  = [flux_row_cls(headers, row) for row in matrix]

        self.headers = headers
        self.matrix  = matrix

        if was_gc_enabled:
            gc.enable()

    @property
    def num_cols(self):
        return len(self.matrix[0].values)

    @property
    def num_rows(self):
        """ header row is not counted """
        return len(self.matrix) - 1

    def __len__(self):
        """ header row is counted """
        return len(self.matrix)

    def as_array(self, r_1=1, r_2=None):
        """ to help with debugging: meant to trigger a debugging feature in PyCharm

        PyCharm will recognize the ndarray and enable the "...view as array"
        option in the debugger which displays values in a special window as a table
        """
        if not numpy_installed:
            raise ImportError('numpy site-package not installed')

        # region {closure functions}
        max_cols = max(max(len(row.values) for row in self.matrix[r_1:r_2]),
                       self.num_cols)

        def enum_start_index():
            if r_1 < 0:
                return max(1, self.num_rows + r_1)
            elif r_1 == 0:
                return 1
            else:
                return r_1
        # endregion

        _rif_ = '     {}     '
        r_i = format_header_lite(_rif_.format('r_i'))
        h   = [format_header(' {} '.format(n)) for n in self.header_names()]
        j   = ['🗲'] * (max_cols - len(h))

        m = [[r_i, *h, *j]]
        for r_i, row in enumerate(self.matrix[r_1:r_2], enum_start_index()):
            r_i = format_integer(row.__dict__.get('r_i', r_i))
            r_i = format_header_lite(_rif_.format(r_i))
            v   = row.values
            j   = ['🗲jagged🗲'] * (max_cols - len(v))

            m.append([r_i, *v, *j])

        return numpy.array(m, dtype=object)

    def header_names(self):
        """
        self.matrix[0].values and self.headers.keys may not always be identical
            map_numeric_indices() makes certain modifications to self.headers.keys,
            such as coercing values to strings, modifying duplicate values, etc
        """
        return list(self.headers.keys())

    def is_empty(self):
        for row in self.matrix:
            if row.values:
                return False

        return True

    def has_duplicate_pointers(self):
        """ if row.values share pointers to the same underlying list (row.values),
        this will usually cause unwanted behaviors to any modifications
        """
        row_ids = set()

        for row in self.matrix:
            row_id = id(row.values)
            if row_id in row_ids:
                return True

            row_ids.add(row_id)

        return False

    def duplicate_pointers(self):
        DuplicateRow = namedtuple('DuplicateRow', ('i', 'row'))

        d = ordereddict()
        for i, row in enumerate(self.matrix):
            row_id = '\\x{:x}'.format(id(row.values))
            row    = DuplicateRow(i, row)

            if row_id in d:
                d[row_id].append(row)
            else:
                d[row_id] = [row]

        d = ordereddict((row_id, rows) for row_id, rows in d.items()
                                       if len(rows) > 1)
        return d

    def is_jagged(self):
        num_cols = len(self.matrix[0].values)
        for row in self.matrix[1:]:
            if len(row.values) != num_cols:
                return True

        return False

    def jagged_rows(self):
        JaggedRow = namedtuple('JaggedRow', ('i', 'row'))

        num_cols = self.num_cols
        for i, row in enumerate(self.matrix):
            if len(row.values) != num_cols:
                yield JaggedRow(i, row)

    # region {filesystem methods}
    def to_file(self, path,
                      encoding=None,
                      filetype=None,
                      **fkwargs):

        filetype = parse_file_extension((filetype or path), include_dot=True)
        filetype = filetype.lower()

        if filetype == '.csv':
            return self.to_csv(path, encoding, **fkwargs)
        elif filetype == '.json':
            return self.to_json(path, encoding, **fkwargs)
        elif filetype in pickle_extensions:
            return self.serialize(path, **fkwargs)

        raise ValueError("invalid filetype: '{}' \nfiletype must be in {}"
                         .format(filetype, ['.csv', '.json'] + list(pickle_extensions)))

    @classmethod
    def from_file(cls, path,
                       encoding=None,
                       filetype=None,
                       **fkwargs):

        if isinstance(path, flux_cls):
            raise TypeError('function is a classmethod, should be called from flux_cls, not flux')

        filetype = parse_file_extension((filetype or path), include_dot=True)
        filetype = filetype.lower()

        if filetype == '.csv':
            return cls.from_csv(path, encoding, **fkwargs)
        if filetype == '.json':
            return cls.from_json(path, encoding, **fkwargs)
        if filetype in pickle_extensions:
            return cls.deserialize(path, **fkwargs)

        raise ValueError("invalid filetype: '{}' \nfiletype must be in {}"
                         .format(filetype, ['.csv', '.json'] + list(pickle_extensions)))

    def to_csv(self, path,
                     encoding=None,
                     **fkwargs):

        write_file(path, self.rows(), encoding, filetype='.csv', fkwargs=fkwargs)
        return self

    @classmethod
    def from_csv(cls, path,
                      encoding=None,
                      **fkwargs):

        if isinstance(path, flux_cls):
            raise TypeError('function is a classmethod, should be called from flux_cls, not flux')

        m = read_file(path, encoding, filetype='.csv', fkwargs=fkwargs)
        return cls(m)

    def to_json(self, path=None,
                      encoding=None,
                      **fkwargs):

        h = tuple(self.header_names())
        j = [ordereddict(zip(h, row.values)) for row in self.matrix[1:]]

        if path is None:
            return json_dumps_extended(j, **fkwargs)

        write_file(path, j, encoding, filetype='.json', fkwargs=fkwargs)
        return self

    @classmethod
    def from_json(cls, path,
                       encoding=None,
                       **fkwargs):

        if isinstance(path, flux_cls):
            raise TypeError('function is a classmethod, should be called from flux_cls, not flux')

        j = read_file(path, encoding, filetype='.json', fkwargs=fkwargs)

        if not j:
            m = [[]]
        else:
            first_row = j[0]
            if isinstance(first_row, dict):
                m = [list(first_row.keys())] + \
                    [list(row.values()) for row in j]
            else:
                m = j

        return cls(m)

    def serialize(self, path, **fkwargs):
        """
        although convenient, pickle introduces significant security flaws
        you should be sure no malicious actors have access to the location of these files
        """
        write_file(path, self, filetype='.flux', fkwargs=fkwargs)
        return self

    @classmethod
    def deserialize(cls, path, **fkwargs):
        """
        although convenient, pickle introduces significant security flaws
        you should be sure no malicious actors have access to the location of these files
        """
        if isinstance(path, flux_cls):
            raise TypeError('function is a classmethod, should be called from flux_cls, not flux')

        return read_file(path, filetype='.flux', fkwargs=fkwargs)
    # endregion

    def columns(self, *names):
        """
        return a one-dimensional list if single column name:
            ['a', 'a', 'a' ...] = list(flux.columns('col_a'))

            flux_b['col_a'] = flux_a['col_a']

        return a two-dimensional list if multiple column names:
            [('a', 'a', 'a', ...),
             ('b', 'b', 'b', ...)] = list(flux.columns('col_a', 'col_b'))

        a, b, c = flux.columns('col_a', 'col_b', 'col_c')
        a, b, c = flux['col_a', 'col_b', 'col_c']

        for a, b, c in zip(*flux[:3]):
            pass
        """
        names = self.__validate_names_not_empty(names, depth_offset=-1)

        nd = iteration_depth(names)
        is_single_column = (nd == 0 or
                           (nd == 1 and len(names) == 1))

        rva = self.row_values_accessor(names)
        col = (rva(row) for row in self.matrix[1:])

        if not is_single_column:
            col = transpose_as_lists(col)

        return col

    def row_values(self, *names):
        """
        return a one-dimensional list if single column name:
            ['a', 'a', 'a', ...] = list(flux.row_values('col_a'))

        return a two-dimensional list if multiple column names:
            [('a', 'b')
             ('a', 'b'),
             ('a', 'b'), ...] = list(flux.row_values('col_a', 'col_b'))

        a, b, c = zip(*flux.row_values('col_a', 'col_b', 'col_c'))

        for a, b, c in flux.row_values('col_a', 'col_b', 'col_c'):
            pass
        """
        names = self.__validate_names_not_empty(names, depth_offset=-1)

        rva = self.row_values_accessor(names)
        return (rva(row) for row in self.matrix[1:])

    def rows(self, r_1=0, r_2=None):
        return (row.values for row in self.matrix[r_1:r_2])

    def flux_rows(self, r_1=0, r_2=None):
        return (row for row in self.matrix[r_1:r_2])

    def namedrows(self, r_1=1, r_2=None):
        h = tuple(self.header_names())
        for row in self.matrix[r_1:r_2]:
            yield SimpleNamespace(**ordereddict(zip(h, row.values)))

    # noinspection PyArgumentList
    def namedtuples(self, r_1=1, r_2=None):
        FluxRow = namedtuple('FluxRow', self.header_names())
        for row in self.matrix[r_1:r_2]:
            yield FluxRow(*row.values)

    def reset_headers(self, names=None):
        """
        simply re-assigning self.headers to a new variable
        (eg self.headers = map_to_numeric_indices(names))
        will de-reference all flux_row_cls._headers in matrix
        """
        use_existing_headers = (names is None)

        if use_existing_headers:
            names = self.matrix[0].values

        headers = map_to_numeric_indices(names)
        self.headers.clear()
        self.headers.update(headers)

        if not use_existing_headers:
            self.matrix[0].values = list(headers.keys())

        return self

    def reset_matrix(self, m):
        (self.headers,
         self.matrix) = self.__validate_headers_and_matrix(m, headers=None)

        return self

    def execute_commands(self, commands, profiler=False):
        Command = namedtuple('Command', ('name', 'method', 'args', 'kwargs'))

        commands = self.__validate_command_methods(commands, Command)
        profiler = self.__validate_profiler_function(profiler)

        completed_commands = []
        for command in commands:
            flux_method = command.method

            if profiler:
                flux_method = profiler(flux_method)

            flux_method(*command.args, **command.kwargs)
            completed_commands.append((command.name, command.args, command.kwargs))

        if hasattr(profiler, 'print_stats'):
            profiler.print_stats()

        return completed_commands

    def matrix_by_headers(self, *names):
        if self.is_empty():
            raise ValueError('matrix is empty')

        names = standardize_variable_arity_arguments(names, depth=1)
        if not names:
            return self

        if isinstance(names, dict):
            names = [names]

        headers = self.headers
        names   = [self.__validate_renamed_or_inserted_column(name, headers) for name in names]

        if self.num_rows == 0:
            (self.headers, self.matrix) = self.__validate_headers_and_matrix([names], headers=None)
            return self

        columns = [row.values for row in self.matrix[1:]]
        columns = list(transpose(columns))

        new_column = [None for _ in range(self.num_rows)]

        m = []
        for n in names:
            if n in headers:
                column = columns[headers[n]]
            else:
                column = new_column

            m.append([n] + column)

        m = list(transpose(m))
        (self.headers, self.matrix) = self.__validate_headers_and_matrix(m, headers=None)

        return self

    def rename_columns(self, old_to_new_mapping):
        if not isinstance(old_to_new_mapping, dict):
            raise TypeError('old_to_new_mapping must be a dictionary')

        header_names = self.header_names()
        for h_old, h_new in old_to_new_mapping.items():
            i = self.headers[h_old]
            header_names[i] = h_new

        self.reset_headers(header_names)

        return self

    def insert_columns(self, *names):
        """ eg:
            flux.insert_columns((0, 'inserted'))         insert as first column
            flux.insert_columns((3,  'inserted'))        insert column before 4th column
            flux.insert_columns((-1, 'inserted'))        insert column at end
            flux.insert_columns(('col_c', 'inserted'))   insert column before column 'col_c'

            flux.insert_columns((1, 'inserted_a'),       insert multiple columns before 1st column
                                (1, 'inserted_b'),
                                (1, 'inserted_c'))
        """
        names = standardize_variable_arity_arguments(names, depth=1)
        if not names:
            return self

        names = self.__validate_inserted_items(names, self.headers)
        names = list(reversed(names))

        header_names = self.header_names()
        for before, header in names:
            if isinstance(before, int):
                i = before
            else:
                i = header_names.index(before)

            header_names.insert(i, header)

        indices = sorted([header_names.index(h) for _, h in names])
        self.reset_headers(header_names)

        for i in indices:
            for row in self.matrix[1:]:
                row.values.insert(i, None)

        return self

    def append_columns(self, *names):
        names = standardize_variable_arity_arguments(names, depth=1)
        if not names:
            return self

        self.__validate_no_duplicate_names(names)
        self.__validate_no_names_intersect_with_headers(names, self.headers)

        v = [None for _ in names]
        self.reset_headers(self.header_names() + list(names))

        for row in self.matrix[1:]:
            row.values.extend(v)

        return self

    def delete_columns(self, *names):
        """
        method will fail if columns are jagged, do a try / except on del row.values[i]
        then length check on row values if failure?
        """
        names = standardize_variable_arity_arguments(names, depth=1)
        if not names:
            return self

        indices = self.__validate_names_as_indices(names, self.headers)
        self.__validate_no_duplicate_names(indices)

        if set(indices) == set(self.headers.values()):
            return self.reset_matrix(None)

        indices.sort(reverse=True)

        for i in indices:
            for row in self.matrix:
                del row.values[i]

        self.reset_headers()

        return self

    def insert_rows(self, i, rows):

        if self.is_empty():
            (self.headers,
             self.matrix) = self.__validate_headers_and_matrix(rows, headers=None)

            return self

        _, m = self.__validate_headers_and_matrix(rows, self.headers)
        replace_headers = (i == 0)

        if replace_headers:
            self.reset_headers(m.pop(0).values)
            i = 1
        else:
            if len(m) > len(rows):
                del m[0]

            if len(rows) != len(m):
                raise AssertionError('author error')

        self.matrix[i:i] = m

        return self

    def append_rows(self, rows):

        if self.is_empty():
            (self.headers,
             self.matrix) = self.__validate_headers_and_matrix(rows, headers=None)

            return self

        _, m = self.__validate_headers_and_matrix(rows, self.headers)
        if m[0].is_header_row():
            del m[0]

        self.matrix.extend(m)

        return self

    def join(self, other, *on_columns):
        """
        what if user wants another mapping method ?
            d = iterable.map_rows(names_b)
            d = iterable.map_rows_append(names_b)

        or different rowtype?
            d = iterable.map_rows(names_b, rowtype=namedtuple)
        """
        names = flux_cls.__validate_names_not_empty(on_columns, depth=0)

        if isinstance(names, dict):
            names_a = list(names.keys())[0]
            names_b = list(names.values())[0]
        else:
            names_a = names
            names_b = names

        self.__validate_all_names_intersect_with_headers(names_a, self.headers)

        if isinstance(other, flux_cls):
            self.__validate_all_names_intersect_with_headers(names_b, other.headers)
            d = other.map_rows(names_b)
        elif isinstance(other, dict):
            d = other
        else:
            d = {item: item for item in other}

        rva = self.row_values_accessor(names_a)

        for row in self.matrix[1:]:
            k = rva(row)
            if k in d:
                yield row, d[k]

    def sort(self, *names, reverse=None):
        """ in-place sort

        eg:
            flux.sort('col_a')
            flux.sort('col_a', 'col_b', 'col_c',
                      reverse=[True, False, True])
        """
        self.matrix[1:] = self.__sort_rows(self.matrix[1:],
                                           names,
                                           reverse)
        return self

    def sorted(self, *names, reverse=None):
        """ :return: sorted flux_cls

        eg:
            flux = flux.sorted('col_a')
            flux = flux.sorted('col_a', 'col_b', 'col_c',
                               reverse=[False, True, True])
        """
        flux = self.copy()
        flux.matrix[1:] = self.__sort_rows(flux.matrix[1:],
                                           names,
                                           reverse)
        return flux

    def __sort_rows(self, rows, names, s_orders):
        """
        names    = reversed(names)
        s_orders = reversed(s_orders)
            # sort priority proceeds in reverse s_orders of names submitted
            # rightmost name sorted first, leftmost name sorted last
        """
        if isinstance(s_orders, bool):
            s_orders = [s_orders]
        else:
            s_orders = s_orders or []

        if not isinstance(s_orders, (list, tuple)):
            raise TypeError('reverse must be a list of booleans')

        names = modify_iteration_depth(names, depth=1)
        for _ in range(len(names) - len(s_orders)):
            s_orders.append(False)

        names    = reversed(names)
        s_orders = reversed(s_orders)

        for name, s_order in zip(names, s_orders):
            rva = self.row_values_accessor(name)
            rows.sort(key=rva, reverse=bool(s_order))

        return rows

    def filter(self, f, *args, **kwargs):
        """ in-place """
        self.matrix[1:] = [row for row in self.matrix[1:]
                               if f(row, *args, **kwargs)]
        return self

    def filtered(self, f, *args, **kwargs):
        """ :return: new flux_cls """
        flux = self.copy()
        flux.matrix[1:] = [row for row in flux.matrix[1:]
                               if f(row, *args, **kwargs)]
        return flux

    def filter_by_unique(self, *names):
        return self.__filter_unique_rows(*names, in_place=True)

    def filtered_by_unique(self, *names):
        return self.__filter_unique_rows(*names, in_place=False)

    def __filter_unique_rows(self, *names, in_place):
        # region {closure functions}
        u   = set()
        rva = self.row_values_accessor(names)

        def evaluate_unique(row):
            v = rva(row)

            if v not in u:
                u.add(v)
                return True
            else:
                return False
        # endregion

        if in_place:
            self.filter(evaluate_unique)
        else:
            return self.filtered(evaluate_unique)

    def map_rows(self, *names, rowtype='flux_row_cls'):
        """ :return: dictionary of {row_value: row} """
        items = self.__map_row_items(names, rowtype=rowtype)
        return ordereddict(list(items))

    def map_rows_append(self, *names, rowtype='flux_row_cls'):
        """ :return: dictionary of {row_value: [row, ...]} """
        items = self.__map_row_items(names, rowtype=rowtype)

        d = ordereddict()
        for k, v in items:
            if k in d:
                d[k].append(v)
            else:
                d[k] = [v]

        return d

    @deprecated('Use flux_cls.map_rows() method instead')
    def index_row(self, *names, rowtype='flux_row_cls'):
        """ deprecated """
        return self.map_rows(names, rowtype=rowtype)

    @deprecated('Use flux_cls.map_rows_append() method instead')
    def index_rows(self, *names, rowtype='flux_row_cls'):
        """ deprecated """
        return self.map_rows_append(names, rowtype=rowtype)

    def __map_row_items(self, names, rowtype):
        rowtype = self.__validate_mapped_rowtype(rowtype)

        rva  = self.row_values_accessor(names)
        keys = (rva(row) for row in self.matrix[1:])

        if rowtype == 'flux_row_cls': values = (row for row in self.matrix[1:])
        elif rowtype == 'namedrow':   values = (v for v in self.namedrows())
        elif rowtype == 'namedtuple': values = (v for v in self.namedtuples())
        elif rowtype == 'list':       values = (list(row.values) for row in self.matrix[1:])
        elif rowtype == 'tuple':      values = (tuple(row.values) for row in self.matrix[1:])
        else:                         raise TypeError

        return zip(keys, values)

    def unique(self, *names):
        rva   = self.row_values_accessor(names)
        items = ((rva(row), None) for row in self.matrix[1:])

        return ordereddict(items).keys()

    def contiguous(self, *names):
        """ :return: yield (value, i_1, i_2) namedtuple where values are contiguous

        (contiguous values may only span a single row ie, i_1 == i_2)
        """
        ContiguousRows = namedtuple('ContiguousRows', ('i_1', 'i_2', 'rows'))

        i_1 = 1
        rva = self.row_values_accessor(names)
        v_1 = rva(self.matrix[i_1])

        for i_2, row in enumerate(self.matrix[i_1 + 1:], i_1 + 1):
            v_2 = rva(row)

            if v_2 != v_1:
                yield ContiguousRows(i_1, i_2 - 1, self.matrix[i_1:i_2])
                v_1 = v_2
                i_1 = i_2

        yield ContiguousRows(i_1, self.num_rows, self.matrix[i_1:])

    def label_row_indices(self, start=0):
        """ meant to assist with debugging;

        label each flux_row_cls.__dict__ with an index, which will then appear
        in each row's __repr__ function and make them easier to identify after
        filtering, sorting, etc
        """
        if 'r_i' in self.headers:
            raise ColumnNameError("'r_i' already exists as header name")

        for i, row in enumerate(self.matrix, start):
            row.__dict__['r_i'] = i

        return self

    def clear_row_indices(self):
        if 'r_i' in self.headers:
            raise ColumnNameError("'r_i' already exists as header name")

        for row in self.matrix:
            if 'r_i' in row.__dict__:
                del row.__dict__['r_i']

        return self

    def copy(self, deep=False):
        if deep:
            return deepcopy(self)

        matrix = [[*row.values] for row in self.matrix]
        flux   = self.__class__(matrix)

        for k in self.__dict__.keys() - {'headers', 'matrix'}:
            flux.__dict__[k] = self.__dict__[k]

        return flux

    def row_values_accessor(self, names):
        """ :return: a function that can be called for each row in self.matrix to retrieve column values """

        # region {closure functions}
        def row_value(row):
            return row.values[i]

        def row_values(row):
            return tuple([row.values[_] for _ in i])

        def row_values_slice(row):
            return tuple(row.values[i])

        def row_values_all(row):
            return tuple(row.values)
        # endregion

        i, rva = self.__validate_row_values_accessor(names, self.headers)

        rva = {'row_value':        row_value,
               'row_values':       row_values,
               'row_values_slice': row_values_slice,
               'row_values_all':   row_values_all} \
               .get(rva, rva)

        return rva

    def __getitem__(self, names):
        if isinstance(names, slice):
            names = self.header_names()[names]

        return self.columns(names)

    def __setitem__(self, name, values):
        """ sets values to a single column
        values are expected to exclude header row

        eg:
            flux['col'] = ['blah'] * flux.num_rows
            flux[-1]    = ['blah'] * flux.num_rows

            to insert column:
                flux[(0, 'new_col')] = ['blah'] * flux.num_rows
        """
        if isinstance(name, tuple) and len(name) == 2:
            if isinstance(name[0], int) and name[1] not in self.headers:
                i, name = name
                self.insert_columns((i, name))
            else:
                raise ColumnNameError('__setitem__ cannot be used to set values to multiple columns')

        elif isinstance(name, slice):
            raise ColumnNameError('__setitem__ cannot be used to set values to multiple columns')
        elif iteration_depth(name) > 0:
            raise ColumnNameError('__setitem__ cannot be used to set values to multiple columns')

        if name not in self.headers and not isinstance(name, int):
            self.append_columns(name)

        i = self.__validate_names_as_indices(name, self.headers)[0]
        for row, v in zip(self.matrix[1:], values):
            row.values[i] = v

    def __iter__(self):
        return (row for row in self.matrix[1:])

    def __add__(self, rows):
        flux = self.copy()
        flux.append_rows(rows)

        return flux

    def __iadd__(self, rows):
        self.append_rows(rows)

        return self

    def __getstate__(self):
        """ serialize raw matrix values, not self.__dict__
        this has advantages in speed and stability
        """
        return list(self.rows())

    def __setstate__(self, o):
        if isinstance(o, dict):
            self.__dict__ = o                   # copy attributes
        else:
            self.__init__(o)                    # call flux_cls constructor

    def __repr__(self):
        if self.is_empty():
            return format_header('')

        if self.is_jagged():
            if self.has_duplicate_pointers():
                is_jagged = '🗲jagged *duplicates🗲  '
            else:
                is_jagged = '🗲jagged🗲  '
        else:
            is_jagged = ''

        num_rows = format_integer(self.num_rows)
        num_rows = format_header_lite('1+' + num_rows)
        num_rows = '{}   '.format(num_rows)

        headers = ', '.join(str(n) for n in self.header_names())
        headers = format_header(headers)

        return ' {}{}{} '.format(is_jagged, num_rows, headers)

    # region {validation functions}
    @staticmethod
    def __validate_matrix_headers(names):
        headers = map_to_numeric_indices(names)

        conflicting = headers.keys() & set(flux_row_cls.reserved_names())
        if conflicting:
            raise ColumnNameError('column name conflict with existing headers: {}'.format(conflicting))

        return headers

    # noinspection PyProtectedMember
    @staticmethod
    def __validate_matrix(m):
        from array import array

        if (m is None) or (m == []):
            m = [[]]
        elif is_vengeance_class(m):
            m = [[*row] for row in m.rows()]
        elif is_exhaustable(m):
            m = list(m)
        elif isinstance(m, array):
            m = list(m)
        elif isinstance(m, dict):
            m = list(transpose_as_lists(m.items()))
        else:
            base_names = set(base_class_names(m))
            if 'DataFrame' in base_names:
                raise NotImplementedError('matrix as DataFrame not supported')
                # m = m.values.tolist()
            elif 'ndarray' in base_names:
                raise NotImplementedError('matrix as ndarray not supported')
                # m = m.tolist()

        if not is_subscriptable(m):
            raise IndexError('matrix must be subscriptable')

        row_first = m[0]

        # list of flux_row_cls objects
        if isinstance(row_first, flux_row_cls):
            if row_first.is_header_row():
                m = [[*row.values] for row in m]
            else:
                m = [list(row_first.header_names())] + \
                    [[*row.values] for row in m]

        # list of namedtuples
        elif hasattr(row_first, '_fields'):
            m = [[*row_first._fields]] + \
                [[*row] for row in m]

        # list of objects
        elif hasattr(row_first, '__dict__'):
            m = [list(row_first.__dict__.keys())] + \
                [list(row.__dict__.values()) for row in m]

        # list of objects (with __slots__ attributes)
        elif hasattr(row_first, '__slots__'):
            s = tuple(row_first.__slots__)
            m = [list(row_first.__slots__)] + \
                [[row.__getattribute__(_) for _ in s] for row in m]

        # list of dictionaries (json-like)
        elif isinstance(row_first, dict):
            m = [list(row_first.keys())] + \
                [list(row.values()) for row in m]

        elif iteration_depth(m, first_element_only=True) < 2:
            raise IterationDepthError('matrix must have at least two dimensions (ie, a list of lists)')

        return m

    @staticmethod
    def __validate_headers_and_matrix(matrix, headers):
        matrix = flux_cls.__validate_matrix(matrix)
        if headers is None:
            headers = flux_cls.__validate_matrix_headers(matrix[0])

        return headers, [flux_row_cls(headers, row) for row in matrix]

    @staticmethod
    def __validate_row_values_accessor(names, headers):
        names = flux_cls.__validate_names_not_empty(names, depth_offset=-1)

        if callable(names):
            i = None
            f = names
        elif isinstance(names, slice):
            i = names
            if ( i.start in (None, 0) and
                 i.stop  in (None, len(headers)) and
                 i.step  in (None, 1)):

                f = 'row_values_all'
            else:
                f = 'row_values_slice'

        elif iteration_depth(names) == 0:
            i = flux_cls.__validate_names_as_indices(names, headers)[0]
            f = 'row_value'
        else:
            i = flux_cls.__validate_names_as_indices(names, headers)
            f = 'row_values'

            i_1 = i[0]
            i_2 = i[-1]
            h_2 = len(headers) - 1

            if (i_1 == 0) and (i_2 == h_2):
                i = None
                f = 'row_values_all'
            elif are_indices_contiguous(i):
                i = slice(i_1, i_2 + 1)
                f = 'row_values_slice'

        return i, f

    @staticmethod
    def __validate_mapped_rowtype(rowtype):
        validtypes = {'flux_row_cls',
                      'namedrow',
                      'namedtuple',
                      'tuple',
                      'list'}

        if not isinstance(rowtype, str):
            rowtype = object_name(rowtype)

        rowtype = rowtype.lower()
        if rowtype not in validtypes:
            raise TypeError('rowtype parameter must be in the following: \n\t{}'.format('\n\t'.join(validtypes)))

        return rowtype

    @staticmethod
    def __are_column_names_empty(names):
        return is_collection(names) and len(names) == 0

    @staticmethod
    def __validate_names_not_empty(names, depth=None, depth_offset=None):
        names = standardize_variable_arity_arguments(names,
                                                     depth=depth,
                                                     depth_offset=depth_offset)
        if flux_cls.__are_column_names_empty(names):
            raise ColumnNameError('no column names submitted')

        return names

    @staticmethod
    def __validate_name_datatypes(names, headers=None):
        valid_datatypes = (int, 
                           str, 
                           bytes)

        names = standardize_variable_arity_arguments(names, depth=1)

        if headers is not None:
            if flux_cls.__are_column_names_empty(names):
                raise ColumnNameError('no column names submitted')

            if isinstance(names[0], slice):
                names = names[0]
                names = list(headers.values())[names]
        
        invalid = [n for n in names if not isinstance(n, valid_datatypes)]
        if invalid:
            s = ("invalid column name datatype: {} "
                 "\nvalid datatypes are ({})"
                 '\n\tMake sure any arguments following variable position parameters are submitted by keyword'
                 "\n\t\tflux.sort('column_a', 'column_b', reverse=True) "
                 '\n\tand not: '
                 "\n\t\tflux.sort('column_a', 'column_b', True)"
                 .format(invalid, ', '.join(v.__name__ for v in valid_datatypes)))
            raise TypeError(s)

        return names

    @staticmethod
    def __validate_inserted_items(inserted, headers):
        inserted = standardize_variable_arity_arguments(inserted, depth=2)

        for item in inserted:
            if iteration_depth(item) != 1 or len(item) != 2:
                raise IterationDepthError("inserted values must be ({location}, {name}) tuples \n\teg: (2, 'new_col')")

        indices, names = list(zip(*inserted))

        flux_cls.__validate_no_duplicate_names(names)
        flux_cls.__validate_no_names_intersect_with_headers(names, headers)
        flux_cls.__validate_all_names_intersect_with_headers(indices, headers)

        return inserted

    @staticmethod
    def __validate_no_duplicate_names(names):
        names = flux_cls.__validate_name_datatypes(names)

        duplicates = [n for n, count in Counter(names).items() if count > 1]
        if duplicates:
            raise ColumnNameError('duplicate column name detected: \n{}'.format(duplicates))

        return names

    @staticmethod
    def __validate_no_names_intersect_with_headers(names, headers):
        names = flux_cls.__validate_name_datatypes(names, headers)

        conflicting = headers.keys() & set(names)
        if conflicting:
            raise ColumnNameError('column names already exist: \n{}'.format(conflicting))

        return names

    @staticmethod
    def __validate_all_names_intersect_with_headers(names, headers):
        names = flux_cls.__validate_name_datatypes(names, headers)

        h_names = [*[ i for i in range(len(headers))],
                   *[-i for i in range(len(headers) + 1)]]
        h_names = headers.keys() | set(h_names)

        invalid = set(names) - h_names
        if invalid:
            s = '\n\t'.join((repr(n)[1:-1].replace(',', ':')
                                          .replace("'", '')
                                          .replace('"', '')) for n in headers.items())
            s = ("'{}' column name does not exist, available columns: "
                 "\n\t{}".format(invalid, s))

            raise ColumnNameError(s)

        return names

    @staticmethod
    def __validate_names_as_indices(names, headers):
        names = flux_cls.__validate_name_datatypes(names)
        names = flux_cls.__validate_all_names_intersect_with_headers(names, headers)

        h_indices = list(headers.values())
        indices = [headers.get(n, n) for n in names]       # lookup strings
        indices = [h_indices[i] for i in indices]          # lookup negative integers

        return indices

    @staticmethod
    def __validate_renamed_or_inserted_column(name, headers):
        is_remapped_column = isinstance(name, dict)
        is_inserted_column = (isinstance(name, str)   and name.startswith('(')  and name.endswith(')') or
                              isinstance(name, bytes) and name.startswith(b'(') and name.endswith(b')')
                              and name not in headers)

        if is_remapped_column:
            name_old, name = list(name.items())[0]
            headers[name] = headers[name_old]
        elif is_inserted_column:
            name = name[1:-1]
            if name in headers:
                raise ColumnNameError("column: '{}' already exists".format(name))

        elif name not in headers:
            raise ColumnNameError("column: '{name}' does not exist. "
                              "\nTo ensure new columns are being created intentionally (not a new column "
                              "because to a typo) inserted headers must be surrounded by parenthesis, eg: "
                              "\n '({name})', not '{name}'".format(name=name))

        return name

    def __validate_command_methods(self, commands, command_namedtuple):
        parsed = []
        for command in commands:
            args   = []
            kwargs = {}

            if isinstance(command, (list, tuple)):
                name = command[0]

                for a in command[1:]:
                    if isinstance(a, dict):
                        kwargs.update(a)
                    elif isinstance(a, (list, tuple)):
                        args.extend(a)
                    else:
                        args.append(a)
            else:
                name = command

            if name.startswith('__'):
                name = '_{}{}'.format(self.__class__.__name__, name)

            args   = tuple(args)
            method = getattr(self, name)

            parsed.append(command_namedtuple(name, method, args, kwargs))

        return parsed

    @staticmethod
    def __validate_profiler_function(use_profiler):
        if use_profiler in (None, False):
            return None

        if use_profiler is True:
            if line_profiler_installed:
                from line_profiler import LineProfiler
                return LineProfiler()
            else:
                return print_runtime

        profiler = str(use_profiler).lower()

        if profiler == 'print_runtime':
            return print_runtime

        if profiler in ('line_profiler', 'lineprofiler'):
            if line_profiler_installed is False:
                raise ImportError("'line_profiler' package not installed")

            from line_profiler import LineProfiler
            return LineProfiler()

        raise ValueError("invalid profiler: '{}', profiler should be in "
                         "\n(None, False, True, 'print_runtime', 'line_profiler')".format(profiler))
    # endregion
