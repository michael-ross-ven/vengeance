
import gc

from array import array
from collections import Counter
from collections import namedtuple
from collections import ItemsView
from copy import deepcopy

from typing import Generator
from typing import List
from typing import Tuple
from typing import Dict
from typing import Union
from typing import Any

from .flux_row_cls import flux_row_cls

from ..util.filesystem import parse_file_extension
from ..util.filesystem import read_file
from ..util.filesystem import write_file
from ..util.filesystem import pickle_extensions

from ..util.iter import IterationDepthError
from ..util.iter import ColumnNameError
from ..util.iter import namespace_cls
from ..util.iter import base_class_names
from ..util.iter import is_exhaustable
from ..util.iter import is_collection
from ..util.iter import is_subscriptable
from ..util.iter import standardize_variable_arity_arguments
from ..util.iter import iteration_depth
from ..util.iter import iterator_to_collection
from ..util.iter import inverted_enumerate
from ..util.iter import are_indices_contiguous
from ..util.iter import modify_iteration_depth
from ..util.iter import transpose
from ..util.iter import to_grouped_dict

from ..util.text import print_runtime
from ..util.text import json_dumps_extended
from ..util.text import deprecated
from ..util.text import object_name
from ..util.text import format_header
from ..util.text import format_header_lite
from ..util.text import format_integer
from ..util.text import function_parameters
from ..util.text import function_name

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
        # first row used as header names (like a csv)
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

    # as_array_preview_indices
    aap_indices = [1, 5 + 1]

    def __init__(self, matrix=None):
        self.headers: Dict[str, int]
        self.matrix:  List[flux_row_cls]

        gc_enabled = gc.isenabled()
        gc.disable()

        matrix  = self.__validate_matrix(matrix)
        headers = self.__validate_names_as_headers(matrix[0])
        matrix  = [flux_row_cls(headers, row) for row in matrix]

        if gc_enabled: gc.enable()

        self.headers = headers
        self.matrix  = matrix

    @property
    def num_cols(self):
        return len(self.matrix[0].values)

    @property
    def num_rows(self):
        """ header row is not included, compare to self.__len__ """
        return len(self.matrix) - 1

    @property
    def as_array_preview(self):
        """
        to help with debugging: meant to trigger a debugging feature in PyCharm
        PyCharm will recognize the numpy array and enable the "...view as array"
        option in the debugger which displays values in a special window as a table

        self.aap_indices are class attributes
        """
        return self.as_array(self.aap_indices[0], self.aap_indices[1])

    def as_array(self, r_1=1, r_2=None):
        """
        to help with debugging: meant to trigger a debugging feature in PyCharm
        PyCharm will recognize the numpy array and enable the "...view as array"
        option in the debugger which displays values in a special window as a table
        """
        # region {closure functions}
        def start_row_index(r):
            if r is None:
                return 1
            elif r < 0:
                return len(self.matrix) + r
            else:
                return r

        def stop_row_index(r):
            if r is None:
                return len(self.matrix)
            elif r < 0:
                return len(self.matrix) + r
            else:
                return r

        def format_row_index(i):
            i = format_integer(i)
            i = format_header_lite(i)

            return i
        # endregion

        r_1 = max(start_row_index(r_1), 1)
        r_2 = min(stop_row_index(r_2), len(self.matrix))
        if r_1 > r_2:
            r_1, r_2 = r_2, r_1

        n_c  = self.num_cols
        rows = self.matrix[r_1:r_2]
        if rows:
            c_m = max(n_c, *[len(row.values) for row in rows])
            has_label = ('r_i' in rows[0].__dict__)
        else:
            c_m = n_c
            has_label = False

        is_jagged = (c_m != n_c)

        h_i = format_header_lite('address')
        h_v = [format_header(n) for n in self.header_names()]
        h_j = ['🗲'] * (c_m - len(h_v))

        if has_label:
            h_v.insert(0, format_header_lite('r_i'))
            c_m += 1

        m = [[h_i, *h_v, *h_j]]
        for r_i, row in enumerate(rows, r_1):
            r_i = format_row_index(r_i)

            if has_label:
                r_v = [format_row_index(row.__dict__.get('r_i', -1)),
                       *row.values]
            else:
                r_v = row.values

            if is_jagged:
                r_j = ['🗲jagged🗲'] * (c_m - len(r_v))
                m.append([r_i, *r_v, *r_j])
            else:
                m.append([r_i, *r_v])

        if not numpy_installed:
            m = '\n'.join([str(row) for row in m])
            return m

        return numpy.array(m, dtype=object)

    def header_names(self):
        """
        self.matrix[0].values and self.headers.keys may not always be identical
            inverted_enumerate() makes certain modifications to self.headers.keys,
            such as coercing values to strings, modifying duplicate values, etc
        """
        return list(self.headers.keys())

    def is_empty(self) -> bool:
        for row in self.matrix:
            if row.values:
                return False

        return True

    def has_duplicate_row_pointers(self) -> bool:
        """
        if row.values share pointers to the same underlying list,
        this will usually cause unwanted behaviors to any modifications of row.values
        """
        row_ids = set()

        for row in self.matrix:
            row_id = id(row.values)
            if row_id in row_ids:
                return True

            row_ids.add(row_id)

        return False

    def duplicate_row_pointers(self) -> Dict:
        enumrow_nt = namedtuple('enumrow', ('i', 'row'))

        d = ordereddict()
        for i, row in enumerate(self.matrix):
            row_id = id(row.values)
            row    = enumrow_nt(i, row)

            if row_id in d:
                d[row_id].append(row)
            else:
                d[row_id] = [row]

        d = ordereddict([('\\x{:x}'.format(row_id), rows) for row_id, rows in d.items()
                                                          if len(rows) > 1])
        return d

    def is_jagged(self) -> bool:
        num_cols = len(self.headers)

        for row in self.matrix:
            if len(row.values) != num_cols:
                return True

        return False

    def jagged_rows(self) -> Generator[namedtuple, None, None]:
        enumrow_nt = namedtuple('enumrow', ('i', 'row'))

        num_cols = self.num_cols
        for i, row in enumerate(self.matrix):
            if len(row.values) != num_cols:
                yield enumrow_nt(i, row)

    # region {filesystem methods}
    def to_file(self, path,
                      encoding=None,
                      filetype=None,
                      **kwargs):

        filetype = parse_file_extension((filetype or path), include_dot=True).lower()

        if filetype == '.csv':
            return self.to_csv(path, encoding, **kwargs)
        elif filetype == '.json':
            return self.to_json(path, encoding, **kwargs)
        elif filetype in pickle_extensions:
            return self.serialize(path, **kwargs)

        raise ValueError("invalid filetype: '{}' \nfiletype must be in {}"
                         .format(filetype, ['.csv', '.json'] + list(pickle_extensions)))

    @classmethod
    def from_file(cls, path,
                       encoding=None,
                       filetype=None,
                       **kwargs):

        filetype = parse_file_extension((filetype or path), include_dot=True).lower()

        if filetype == '.csv':
            return cls.from_csv(path, encoding, **kwargs)
        if filetype == '.json':
            return cls.from_json(path, encoding, **kwargs)
        if filetype in pickle_extensions:
            return cls.deserialize(path, **kwargs)

        raise ValueError("invalid filetype: '{}' \nfiletype must be in {}"
                         .format(filetype, ['.csv', '.json'] + list(pickle_extensions)))

    def to_csv(self, path,
                     encoding=None,
                     **kwargs):

        write_file(path, self.rows(), encoding, filetype='.csv', **kwargs)
        return self

    @classmethod
    def from_csv(cls, path,
                      encoding=None,
                      **kwargs):

        m = read_file(path, encoding, filetype='.csv', **kwargs)
        return cls(m)

    def to_json(self, path=None,
                      encoding=None,
                      **kwargs):

        h = tuple(self.header_names())
        o = [ordereddict(zip(h, row.values)) for row in self.matrix[1:]]

        if path is None:
            return json_dumps_extended(o, **kwargs)

        write_file(path, o, encoding, filetype='.json', **kwargs)
        return self

    @classmethod
    def from_json(cls, path,
                       encoding=None,
                       **kwargs):

        o = read_file(path, encoding, filetype='.json', **kwargs)
        # if isinstance(o, dict):
        #     o = [o]

        return cls(o)

    def serialize(self, path, **kwargs):
        """
        although convenient, pickle introduces significant security flaws
        you should be sure no malicious actors have access to the location of these files
        """
        write_file(path, self, filetype='.flux', **kwargs)
        return self

    @classmethod
    def deserialize(cls, path, **kwargs):
        """
        although convenient, pickle introduces significant security flaws
        you should be sure no malicious actors have access to the location of these files
        """
        return read_file(path, filetype='.flux', **kwargs)
    # endregion

    def columns(self, *names) -> Generator[Any, None, None]:
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
        if names == ():
            names = self.header_names()
        else:
            names = self.__validate_names_not_empty(names, depth_offset=-1)

        has_multiple_columns = isinstance(names, slice) or \
                               (is_collection(names) and len(names) > 1)
        rva = self.row_values_accessor(names)
        col = (rva(row) for row in self.matrix[1:])

        if has_multiple_columns:
            col = transpose(col, astype=tuple)

        return col

    def values(self, *names) -> Generator[Any, None, None]:
        """
        return a one-dimensional list if single column name:
            ['a', 'a', 'a', ...] = list(flux.values('col_a'))

        return a two-dimensional list if multiple column names:
            [('a', 'b')
             ('a', 'b'),
             ('a', 'b'), ...] = list(flux.values('col_a', 'col_b'))

        a, b, c = zip(*flux.values('col_a', 'col_b', 'col_c'))
        for a, b, c in flux.values('col_a', 'col_b', 'col_c'):
            pass
        """
        if names == ():
            names = self.header_names()

        rva = self.row_values_accessor(names)
        return (rva(row) for row in self.matrix[1:])

    def rows(self, r_1=0, r_2=None) -> Generator[Union[List, Tuple], None, None]:
        return (row.values for row in self.matrix[r_1:r_2])

    def dictrows(self, r_1=1, r_2=None) -> Generator[Dict, None, None]:
        names = tuple(self.header_names())
        for row in self.matrix[r_1:r_2]:
            yield ordereddict(zip(names, row.values))

    def namedrows(self, r_1=1, r_2=None) -> Generator[namespace_cls, None, None]:
        names = tuple(self.header_names())
        for row in self.matrix[r_1:r_2]:
            yield namespace_cls(**ordereddict(zip(names, row.values)))

    # noinspection PyArgumentList
    def namedtuples(self, r_1=1, r_2=None) -> Generator[namedtuple, None, None]:
        row_nt = namedtuple('row', self.header_names())
        for row in self.matrix[r_1:r_2]:
            yield row_nt(*row.values)

    def reset_headers(self, names=None):
        """
        simply re-assigning self.headers to a new variable (eg, self.headers = dict())
        will de-reference all flux_row_cls._headers in matrix,  so self.headers
        must be cleared, then updated
        """
        use_existing_headers = (names is None)

        if use_existing_headers:
            names = self.matrix[0].values

        headers = inverted_enumerate(names)
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
        command_nt = namedtuple('command', ('name', 'method', 'args', 'kwargs'))

        commands = self.__validate_command_methods(commands, command_nt)
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

        headers = self.headers.copy()
        names   = [self.__validate_renamed_or_inserted_column(name, headers) for name in names]
        headers = ordereddict(sorted(headers.items(), key=lambda _: _[-1]))

        all_columns  = [row.values for row in self.matrix[1:]]
        all_columns  = list(transpose(all_columns, astype=list))
        empty_column = [None] * self.num_rows

        m = []
        for n in names:
            if n in headers: column = all_columns[headers[n]]
            else:            column = empty_column

            m.append([n] + column)

        m = transpose(m)
        self.reset_matrix(m)

        return self

    def rename_columns(self, old_to_new_mapping):
        if not isinstance(old_to_new_mapping, dict):
            raise TypeError('old_to_new_mapping must be a dictionary')

        names = self.header_names()
        for h_old, h_new in old_to_new_mapping.items():
            i = self.headers[h_old]
            names[i] = h_new

        self.reset_headers(names)

        return self

    def insert_columns(self, *names, after=False):
        """ eg:
            flux.insert_columns((0,  'inserted'))        insert as first column
            flux.insert_columns((3,  'inserted'))        insert column before 4th column
            flux.insert_columns((-1, 'inserted'))        insert column at end

            flux.insert_columns((1, 'inserted_a'),       insert multiple columns before 1st column
                                (1, 'inserted_b'),
                                (1, 'inserted_c'))

            flux.insert_columns(('col_c', 'inserted'))               insert column before column 'col_c'
            flux.insert_columns(('col_c', 'inserted', after=True))   insert column after column 'col_c'

        note on inner / outer loop performance:
            because python struggles on very tight loops,
            it's faster to use the matrix loop as the inner loop

            * faster:
            for i in indices:
                for row in self.matrix[1:]:
                    ...

            * slower:
            for row in self.matrix[1:]:
                for i in indices:
                    ...
        """
        names = standardize_variable_arity_arguments(names, depth=1)
        if not names:
            return self

        names = self.__validate_inserted_items(names, self.headers)

        after = [bool(_) for _ in standardize_variable_arity_arguments(after, depth=1)]
        after.extend([False] * (len(names) - len(after)))

        names = list(reversed(names))
        after = list(reversed(after))

        header_names = self.header_names()

        for item, af in zip(names, after):
            before, header = item

            if isinstance(before, int): i = before
            else:                       i = header_names.index(before)

            if af:
                i += 1

            header_names.insert(i, header)

        indices = sorted([header_names.index(h) for _, h in names])

        for i in indices:
            for row in self.matrix[1:]:
                row.values.insert(i, None)

        self.reset_headers(header_names)

        return self

    def append_columns(self, *names):
        names = standardize_variable_arity_arguments(names, depth=1)
        if not names:
            return self

        self.__validate_no_duplicate_names(names)
        self.__validate_no_names_intersect_with_headers(names, self.headers)

        v = [None for _ in names]
        for row in self.matrix[1:]:
            row.values.extend(v)

        self.reset_headers(self.header_names() + list(names))

        return self

    def delete_columns(self, *names):
        """
        method will fail if columns are jagged, do a try / except on del row.values[i]
        then length check on row values if failure?

        note on inner / outer loop performance:
            because python struggles on very tight loops,
            it's faster to use the matrix loop as the inner loop

            * faster:
            for i in indices:
                for row in self.matrix[1:]:
                    ...

            * slower:
            for row in self.matrix[1:]:
                for i in indices:
                    ...
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
            return self.reset_matrix(rows)

        replace_headers = (i == 0)

        rows = modify_iteration_depth(iterator_to_collection(rows), depth=2)
        _, m = self.__validate_headers_and_matrix(rows, self.headers)

        if replace_headers:
            self.reset_headers(m.pop(0).values)
            i = 1
        elif m[0].is_header_row():
            del m[0]

        self.matrix[i:i] = m

        return self

    def append_rows(self, rows):
        if self.is_empty():
            return self.reset_matrix(rows)

        rows = modify_iteration_depth(iterator_to_collection(rows), depth=2)
        _, m = self.__validate_headers_and_matrix(rows, self.headers)

        if m[0].is_header_row():
            del m[0]

        self.matrix.extend(m)

        return self

    def shorten_to(self, nrows):
        if nrows == 0:
            nrows = 1
        elif nrows < 0:
            raise ValueError('nrows must be positive')

        del self.matrix[nrows + 1:]
        return self

    def join(self, other, *on_columns):
        """
        what if user wants another mapping method ?
            d = iterable.map_rows(names_b)
            d = iterable.map_rows_append(names_b)

        or different rowtype?
            d = iterable.map_rows(names_b, rowtype=namedtuple)
        """
        names = self.__validate_names_not_empty(on_columns, self.headers, depth=0)

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

    def reverse(self):
        self.matrix[1:] = list(reversed(self.matrix[1:]))
        return self

    def reversed(self):
        flux = self.copy()
        flux.matrix[1:] = list(reversed(flux.matrix[1:]))
        return flux

    def sort(self, *names, reverse=False):
        """ in-place sort

        eg:
            flux.sort('col_a')
            flux.sort('col_a', 'col_b', 'col_c',
                      reverse=[True, False, True])
        """
        names = standardize_variable_arity_arguments(names, depth=1)
        if not names:
            return self

        self.matrix[1:] = self.__sort_rows(self.matrix[1:],
                                           names,
                                           reverse)
        return self

    def sorted(self, *names, reverse=False):
        """ :return: sorted flux_cls

        eg:
            flux = flux.sorted('col_a')
            flux = flux.sorted('col_a', 'col_b', 'col_c',
                               reverse=[False, True, True])
        """
        names = standardize_variable_arity_arguments(names, depth=1)
        if not names:
            return self.copy()

        flux = self.copy()
        flux.matrix[1:] = self.__sort_rows(flux.matrix[1:],
                                           names,
                                           reverse)
        return flux

    def __sort_rows(self, rows, names, reverse):
        reverse = [bool(_) for _ in standardize_variable_arity_arguments(reverse, depth=1)]
        reverse.extend([False] * (len(names) - len(reverse)))

        all_true  = all(_ is True  for _ in reverse)
        all_false = all(_ is False for _ in reverse)

        if all_true or all_false:
            rva = self.row_values_accessor(names)
            rows.sort(key=rva, reverse=reverse[0])

            return rows

        # last name is sorted first, first name is sorted last
        names   = reversed(names)
        reverse = reversed(reverse)

        for name, rev in zip(names, reverse):
            rva = self.row_values_accessor(name)
            rows.sort(key=rva, reverse=rev)

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

    def map_rows(self, *names, rowtype='flux_row_cls') -> Dict[Any, Union[flux_row_cls, namespace_cls, Dict, Tuple,
                                                                          List]]:
        """ dictionary of {row_value: row} """
        items = self.__zip_row_items(names, rowtype=rowtype)
        return ordereddict(items)

    def map_rows_append(self, *names, rowtype='flux_row_cls') -> Dict[Any, List]:
        """ dictionary of {row_value: [rows]} """
        items = self.__zip_row_items(names, rowtype=rowtype)

        d = ordereddict()
        for k, v in items:
            if k in d:  d[k].append(v)
            else:       d[k] = [v]

        return d

    def group_rows(self, *names, rowtype='flux_row_cls') -> Dict[Any, Dict]:
        """
        names = standardize_variable_arity_arguments(names, depth=1)
        if len(names) == 1, then just return d_1?
        """
        d_1 = self.map_rows(names, rowtype=rowtype)
        d_2 = to_grouped_dict(d_1)

        return d_2

    def group_rows_append(self, *names, rowtype='flux_row_cls') -> Dict[Any, Dict]:
        """
        names = standardize_variable_arity_arguments(names, depth=1)
        if len(names) == 1, then just return d_1?
        """
        d_1 = self.map_rows_append(names, rowtype=rowtype)
        d_2 = to_grouped_dict(d_1)

        return d_2

    @deprecated('Use flux_cls.map_rows() method instead')
    def index_row(self, *names, rowtype='flux_row_cls'):
        """ deprecated """
        return self.map_rows(names, rowtype=rowtype)

    @deprecated('Use flux_cls.map_rows_append() method instead')
    def index_rows(self, *names, rowtype='flux_row_cls'):
        """ deprecated """
        return self.map_rows_append(names, rowtype=rowtype)

    def __zip_row_items(self, names, rowtype):
        rowtype = self.__validate_mapped_rowtype(rowtype)
        rva     = self.row_values_accessor(names)

        keys = (rva(row) for row in self.matrix[1:])

        if rowtype   == 'flux_row_cls': values = (row for row in self.matrix[1:])
        elif rowtype == 'dict':         values = (v for v in self.dictrows())
        elif rowtype == 'namedrow':     values = (v for v in self.namedrows())
        elif rowtype == 'namedtuple':   values = (v for v in self.namedtuples())
        elif rowtype == 'list':         values = (list(row.values)  for row in self.matrix[1:])
        elif rowtype == 'tuple':        values = (tuple(row.values) for row in self.matrix[1:])
        else:
            raise TypeError

        return zip(keys, values)

    def unique(self, *names):
        rva   = self.row_values_accessor(names)
        items = ((rva(row), None) for row in self.matrix[1:])

        return ordereddict(items).keys()

    def contiguous(self, *names):
        """ :return: yield (value, i_1, i_2) namedtuple where values are contiguous

        (contiguous values may only span a single row ie, i_1 == i_2)
        """
        contiguousrows_nt = namedtuple('contiguous', ('value', 'i_1', 'i_2', 'rows'))

        rva = self.row_values_accessor(names)

        i_1 = 1
        v_1 = rva(self.matrix[i_1])
        v_2 = v_1

        for i_2, row in enumerate(self.matrix[i_1 + 1:], i_1 + 1):
            v_2 = rva(row)

            if v_2 != v_1:
                yield contiguousrows_nt(v_2, i_1, i_2 - 1, self.matrix[i_1:i_2])
                v_1 = v_2
                i_1 = i_2

        i_2 = len(self.matrix) - 1
        yield contiguousrows_nt(v_2, i_1, i_2, self.matrix[i_1:])

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

        if self.__class__ is not flux_cls:
            return deepcopy(self)

        __dict__ = {k: v for k, v in self.__dict__.items()
                         if k not in {'headers', 'matrix'}}
        flux = self.__class__(self)
        flux.__dict__.update(__dict__)

        return flux

    def row_values_accessor(self, names):
        """ :return: a function that can be called for each row in self.matrix
        to retrieve column values
        """

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

    def __iter__(self) -> Generator[flux_row_cls, None, None]:
        return (row for row in self.matrix[1:])

    def __add__(self, rows):
        flux = self.copy()
        flux.append_rows(rows)

        return flux

    def __iadd__(self, rows):
        return self.append_rows(rows)

    def __getstate__(self):
        f = self.__class__.__init__

        constructor_params = function_parameters(f)
        constructor_repr   = '{}({})'.format(function_name(f),
                                             ', '.join(p.name for p in constructor_params))

        args   = []
        kwargs = ordereddict()
        for p in constructor_params:
            name = p.name

            if name   == 'self':      continue
            elif name == 'matrix':    p.value = [[*row.values] for row in self.matrix]
            elif name == 'headers':   p.value = ordereddict(self.headers.items())
            elif hasattr(self, name): p.value = getattr(self, name)

            elif p.value.__name__ == '_empty':
                raise ValueError("unable to resolve constructor parameter: '{}' \n"
                                 "for: {}".format(name, constructor_repr))

            kind = p.kind.lower()

            if 'positional' in kind:
                args.append(p.value)
            else:
                kwargs[name] = p.value

        args = tuple(args)

        return {'args':   args,
                'kwargs': kwargs}

    def __setstate__(self, state):
        if not isinstance(state, dict):
            return self.__init__(state)

        use_constructor = ('args'   in state and
                           'kwargs' in state)
        if use_constructor:
            self.__init__(*state['args'], **state['kwargs'])
        else:
            self.__dict__.update(state)

    def __len__(self):
        """ header row is included, see self.num_rows """
        return len(self.matrix)

    def __reversed__(self):
        return (row for row in reversed(self.matrix[1:]))

    def __repr__(self):
        if self.is_empty():
            return format_header('')

        if self.is_jagged():
            if self.has_duplicate_row_pointers(): jagged_label = '**dup**  🗲jagged🗲  '
            else:                                 jagged_label = '🗲jagged🗲  '
        else:
            jagged_label = ''

        num_rows = format_integer(len(self.matrix) - 1)
        num_rows = format_header_lite('h+' + num_rows)

        headers = ', '.join(str(n) for n in self.header_names())
        headers = format_header(headers)

        return '{}{}  {}'.format(jagged_label, num_rows, headers)

    # region {validation functions}
    @staticmethod
    def __validate_names_as_headers(names):
        headers = inverted_enumerate(names)

        conflicting = headers.keys() & set(flux_row_cls.reserved_names())
        if conflicting:
            raise ColumnNameError('column name conflict with existing headers: {}'.format(conflicting))

        return headers

    # noinspection PyProtectedMember
    @staticmethod
    def __validate_matrix(m):
        if (m is None) or (m == []):
            return [[]]

        base_cls_names = set(base_class_names(m))

        if base_cls_names & {'flux_cls', 'excel_levity_cls'}:
            return [[*row] for row in m.rows()]
        elif 'DataFrame' in base_cls_names:
            return [[*row] for row in m.values.tolist()]
        elif 'ndarray' in base_cls_names:
            return m.tolist()

        if is_exhaustable(m):
            m = list(m)
        if isinstance(m, array):
            m = list(m)
        elif isinstance(m, ItemsView):
            m = list(m)
            m = list(transpose(m, astype=list))
        elif isinstance(m, dict):
            m = list(m.items())
            m = list(transpose(m, astype=list))

        if not is_subscriptable(m):
            raise IndexError('matrix must be subscriptable')

        row_first: Union[flux_row_cls, namedtuple, dict, object]
        row:       Union[flux_row_cls, namedtuple, dict, object]

        row_first = m[0]

        # list of flux_row_cls objects
        if isinstance(row_first, flux_row_cls):
            if row_first.is_header_row():
                m = [[*row.values] for row in m]
            else:
                m = [[*row_first.header_names()]] + \
                    [[*row.values] for row in m]

        # list of dictionaries
        elif isinstance(row_first, dict):
            m = [[*row_first.keys()]] + \
                [[*row.values()] for row in m]

        # list of namedtuples
        elif hasattr(row_first, '_fields'):
            m = [[*row_first._fields]] + \
                [[*row] for row in m]

        # list of objects
        elif hasattr(row_first, '__dict__'):
            m = [[*row_first.__dict__.keys()]] + \
                [[*row.__dict__.values()] for row in m]

        # list of objects (with __slots__ attributes)
        elif hasattr(row_first, '__slots__'):
            h = tuple(row_first.__slots__)
            m = [[*h]] + \
                [[*[row.__getattribute__(n) for n in h]] for row in m]

        else:
            if iteration_depth(m, first_element_only=True) < 2:
                raise IterationDepthError('matrix must have at least two iterable dimensions (ie, a list of lists)')

        return m

    @staticmethod
    def __validate_headers_and_matrix(matrix, headers):
        matrix = flux_cls.__validate_matrix(matrix)
        if headers is None:
            headers = flux_cls.__validate_names_as_headers(matrix[0])

        return headers, [flux_row_cls(headers, row) for row in matrix]

    @staticmethod
    def __validate_row_values_accessor(names, headers):
        names = flux_cls.__validate_names_not_empty(names, depth_offset=-1)

        if callable(names):
            i = None
            f = names
        elif isinstance(names, slice):
            i = names
            if i.start in (None, 0) and \
               i.stop  in (None, len(headers)) and \
               i.step  in (None, 1):

                f = 'row_values_all'
            else:
                f = 'row_values_slice'

        elif iteration_depth(names) == 0:
            i = flux_cls.__validate_names_as_indices(names, headers)[0]
            f = 'row_value'
        else:
            i = flux_cls.__validate_names_as_indices(names, headers)
            f = 'row_values'

            if are_indices_contiguous(i):
                i = slice(i[0], i[-1] + 1)
                f = 'row_values_slice'

        return i, f

    @staticmethod
    def __validate_mapped_rowtype(rowtype):
        validtypes = {'flux_row_cls',
                      'namedrow',
                      'namedtuple',
                      'tuple',
                      'list',
                      'dict'}

        if not isinstance(rowtype, str):
            rowtype = object_name(rowtype)

        rowtype = rowtype.lower()

        if rowtype != 'flux_row_cls' and rowtype.endswith('s'):
            rowtype = rowtype[:-1]

        if rowtype not in validtypes:
            raise TypeError("invalid rowtype '{}', rowtype must be in the following: \n\t{}"
                            .format(rowtype, '\n\t'.join(validtypes)))

        return rowtype

    @staticmethod
    def __validate_names_not_empty(names,
                                   headers=None,
                                   depth=None,
                                   depth_offset=None):

        names = flux_cls.__validate_names(names, headers, depth, depth_offset)
        if is_collection(names) and len(names) == 0:
            raise ColumnNameError('no column names submitted')

        return names

    @staticmethod
    def __validate_names(names,
                         headers=None,
                         depth=None,
                         depth_offset=None):

        names = standardize_variable_arity_arguments(names,
                                                     depth=depth,
                                                     depth_offset=depth_offset)
        if isinstance(names, slice) and isinstance(headers, dict):
            names = list(headers.keys())[names]

        return names

    @staticmethod
    def __validate_name_datatypes(names, headers=None):
        valid_datatypes = (int, 
                           str, 
                           bytes)

        names = flux_cls.__validate_names(names, headers, depth=1)

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
        if isinstance(inserted, dict):
            inserted = list(inserted.items())

        inserted = standardize_variable_arity_arguments(inserted, depth=2)

        for item in inserted:
            if iteration_depth(item) != 1 or len(item) != 2:
                raise IterationDepthError("inserted values must be ({location}, {name}) tuples "
                                          "\n\teg: (2, 'new_col') "
                                          "\n\teg: [('col_a', 'new_col_a'), ('col_b', 'new_col_b')]")

        indices, names = list(zip(*inserted))

        flux_cls.__validate_name_datatypes(names)
        flux_cls.__validate_no_duplicate_names(names)
        flux_cls.__validate_no_names_intersect_with_headers(names, headers)
        flux_cls.__validate_all_names_intersect_with_headers(indices, headers)

        return inserted

    @staticmethod
    def __validate_no_duplicate_names(names):
        names = flux_cls.__validate_names(names, depth=1)

        duplicates = [n for n, count in Counter(names).items() if count > 1]
        if duplicates:
            raise ColumnNameError('duplicate column name detected: \n{}'.format(duplicates))

        return names

    @staticmethod
    def __validate_no_names_intersect_with_headers(names, headers):
        names = flux_cls.__validate_names(names, headers, depth=1)

        conflicting = headers.keys() & set(names)
        if conflicting:
            raise ColumnNameError('column names already exist: \n{}'.format(conflicting))

        return names

    @staticmethod
    def __validate_all_names_intersect_with_headers(names, headers):
        names = flux_cls.__validate_names(names, headers, depth=1)

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
