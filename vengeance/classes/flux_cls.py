
from collections import Counter
from collections import namedtuple
from copy import deepcopy
from types import SimpleNamespace

from .flux_row_cls import flux_row_cls

from ..util.filesystem import parse_file_extension
from ..util.filesystem import read_file
from ..util.filesystem import write_file
from ..util.filesystem import pickle_extensions

from ..util.iter import OrderedDefaultDict
from ..util.iter import IterationDepthError
from ..util.iter import base_class_names
from ..util.iter import is_exhaustable
from ..util.iter import is_collection
from ..util.iter import is_subscriptable
from ..util.iter import is_vengeance_class
from ..util.iter import iteration_depth
from ..util.iter import map_to_numeric_indices
from ..util.iter import modify_iteration_depth
from ..util.iter import iterator_to_list
from ..util.iter import transpose_to_lists

from ..util.text import print_runtime
from ..util.text import json_dumps_extended
from ..util.text import deprecated
from ..util.text import object_name

from ..conditional import ordereddict
from ..conditional import line_profiler_installed


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
        matrix  = self.__validate_matrix(matrix)
        headers = self.__validate_matrix_headers(matrix[0])
        matrix  = [flux_row_cls(headers, row) for row in matrix]

        self.headers = headers
        self.matrix  = matrix

    def __flux_headers_and_matrix(self, matrix, headers=None):
        matrix = self.__validate_matrix(matrix)
        if headers is None:
            headers = self.__validate_matrix_headers(matrix[0])

        return headers, [flux_row_cls(headers, row) for row in matrix]

    @property
    def as_preview(self):
        """ peek at values of header row + first five rows
        acts like pandas.DataFrame.head
        """
        return [row.values for row in self.matrix[:6]]

    @property
    def header_names(self):
        """
        self.matrix[0].values and self.headers.keys may not always be identical
            map_numeric_indices() makes certain modifications to self.headers.keys,
            such as coercing values to strings, modifying duplicate values, etc
        """
        return list(self.headers.keys())

    @property
    def num_rows(self):
        """ header not counted """
        if not any(self.matrix[0].values):
            return -1

        return len(self.matrix) - 1

    def __len__(self):
        return self.num_rows

    @property
    def num_cols(self):
        return len(self.matrix[0].values)

    @property
    def min_num_cols(self):
        return min(map(len, self.matrix))

    @property
    def max_num_cols(self):
        return max(map(len, self.matrix))

    def is_empty(self):
        for row in self.matrix:
            if any(row.values):
                return False

        return True

    def is_jagged(self):
        num_cols = self.num_cols

        for row in self.matrix[1:]:
            # noinspection PyProtectedMember
            if ( len(row.values)   != num_cols or
                 len(row._headers) != num_cols ):
                return True

        return False

    # region {filesystem methods}
    def to_file(self, path,
                      encoding=None,
                      *,
                      filetype=None,
                      fkwargs=None):

        if filetype is None:
            filetype = parse_file_extension(path, include_dot=True)
        elif not filetype.startswith('.'):
            filetype += '.'

        filetype = filetype.lower()

        if filetype == '.csv':
            return self.to_csv(path, encoding, fkwargs=fkwargs)
        elif filetype == '.json':
            return self.to_json(path, encoding, fkwargs=fkwargs)
        elif filetype in pickle_extensions:
            return self.serialize(path, fkwargs=fkwargs)

        raise ValueError("invalid filetype: '{}' \nfiletype must be in {}"
                         .format(filetype, ['.csv', '.json'] + list(pickle_extensions)))

    @classmethod
    def from_file(cls, path,
                       encoding=None,
                       *,
                       filetype=None,
                       fkwargs=None):

        if filetype is None:
            filetype = parse_file_extension(path, include_dot=True)
        elif not filetype.startswith('.'):
            filetype += '.'

        filetype = filetype.lower()

        if filetype == '.csv':
            return cls.from_csv(path, encoding, fkwargs=fkwargs)
        if filetype == '.json':
            return cls.from_json(path, encoding, fkwargs=fkwargs)
        if filetype in pickle_extensions:
            return cls.deserialize(path, fkwargs=fkwargs)

        raise ValueError("invalid filetype: '{}' \nfiletype must be in {}"
                         .format(filetype, ['.csv', '.json'] + list(pickle_extensions)))

    def to_csv(self, path,
                     encoding=None,
                     *,
                     fkwargs=None):

        write_file(path, self.rows(), encoding, filetype='.csv', fkwargs=fkwargs)
        return self

    @classmethod
    def from_csv(cls, path,
                      encoding=None,
                      *,
                      fkwargs=None):

        m = read_file(path, encoding, filetype='.csv', fkwargs=fkwargs)
        return cls(m)

    def to_json(self, path=None,
                      encoding=None,
                      *,
                      fkwargs=None):

        # h = self.header_names
        # j = [ordereddict(zip(h, row.values)) for row in self.matrix[1:]]

        j = [row.dict() for row in self.matrix[1:]]
        if path is None:
            return json_dumps_extended(j, **fkwargs)

        write_file(path, j, encoding, filetype='.json', fkwargs=fkwargs)
        return self

    @classmethod
    def from_json(cls, path,
                       encoding=None,
                       *,
                       fkwargs=None):
        """
        if isinstance(j, dict):
            {"col_a": "col_b",
             "a": "b",
             "a": "b",
             "a": "b"}

            items = iter(j.items())
            m = [list(next(items))] + \
                [list(item) for item in items]
        else:
            [
                {"col_a": "a",
                 "col_b": "b"},
                {"col_a": "a",
                 "col_b": "b"}
            ]
        """
        j = read_file(path, encoding, filetype='.json', fkwargs=fkwargs)

        if isinstance(j, dict):
            raise TypeError('json data should be a list of dictionaries, eg: '
                            '\n['
                            '\n\t{"col_a": "a",'
                            '\n\t "col_b": "b"},'
                            '\n\t{"col_a": "a",'
                            '\n\t "col_b": "b"}'
                            '\n]'
                            '\n\nalternatively, json data could be converted to a matrix, eg: '
                            '\n\tj = read_file(path)'
                            '\n\tm = [list(row) for row in j.items()]'
                            '\n\tflux = flux_cls(m)')

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

    def serialize(self, path,
                        *,
                        fkwargs=None):
        """
        although convenient, pickle introduces significant security flaws
        you should be sure no malicious actors have access to the location of these files
        """
        write_file(path, self, filetype='.flux', fkwargs=fkwargs)
        return self

    @classmethod
    def deserialize(cls, path,
                         *,
                         fkwargs=None):
        """
        although convenient, pickle introduces significant security flaws
        you should be sure no malicious actors have access to the location of these files
        """
        return read_file(path, filetype='.flux', fkwargs=fkwargs)
    # endregion

    def columns(self, *names):
        names = self.__standardize_variable_arity_arguments(names, depth=1)

        rva = self.row_values_accessor(names)
        col = (rva(row) for row in self.matrix[1:])

        is_single_column = (iteration_depth(names) == 1
                            and len(names) == 1)
        if not is_single_column:
            col = list(col)
            col = transpose_to_lists(col)

        return col

    def rows(self, r_1=0, r_2=None):
        return (row.values for row in self.matrix[r_1:r_2])

    def flux_rows(self, r_1=0, r_2=None):
        return (row for row in self.matrix[r_1:r_2])

    def namedrows(self, r_1=1, r_2=None):
        h = tuple(self.header_names)
        for row in self.matrix[r_1:r_2]:
            yield SimpleNamespace(**ordereddict(zip(h, row.values)))

    # noinspection PyArgumentList
    def namedtuples(self, r_1=1, r_2=None):
        FluxRow = namedtuple('FluxRow', self.header_names)
        for row in self.matrix[r_1:r_2]:
            yield FluxRow(*row.values)

    def reset_headers(self, names=None):
        """
        simply re-assigning self.headers to a new variable, eg
        self.headers = map_to_numeric_indices(names)), will
        de-reference all flux_row_cls._headers in matrix
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
        self.headers, self.matrix = self.__flux_headers_and_matrix(m)
        return self

    def execute_commands(self, commands, profiler=False):
        commands = self.__parse_commands(commands)
        profiler = self.__validate_profiler_function(profiler)

        completed_commands = []
        for command in commands:
            flux_method = command.method
            if profiler:
                flux_method = profiler(flux_method)

            if command.num_args == 0:
                flux_method()
            elif command.num_args == 1:
                flux_method(command.args)
            else:
                flux_method(*command.args)

            completed_commands.append((command.name, command.args))

        if hasattr(profiler, 'print_stats'):
            profiler.print_stats()

        return completed_commands

    def __parse_commands(self, commands):
        Command = namedtuple('Command', 'name method args num_args')

        parsed  = []
        for command in commands:

            if isinstance(command, (list, tuple)):
                name, args = command
                if isinstance(args, dict):
                    raise NotImplementedError('keyword args not supported')

                num_args = iteration_depth(args) + 1
            else:
                name = command
                args = ()
                num_args = 0

            if name.startswith('__'):
                name = '_{}{}'.format(self.__class__.__name__, name)

            method = getattr(self, name)
            parsed.append(Command(name, method, args, num_args))

        return parsed

    @staticmethod
    def __validate_profiler_function(use_profiler):
        if use_profiler is False:
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
            else:
                from line_profiler import LineProfiler
                return LineProfiler()

        raise ValueError("invalid profiler: '{}'".format(profiler))

    def matrix_by_headers(self, *names):
        if self.is_empty():
            return self

        names = modify_iteration_depth(names, depth=1)
        if isinstance(names, dict):
            names = [names]

        m = [row.values for row in self.matrix[1:]]
        columns = list(transpose_to_lists(m))
        columns = columns or [[]]
        blank_column = [None for _ in range(self.num_rows)]

        m = []
        for name in names:
            name = self.__convert_renamed_or_inserted_header(name)

            if name in self.headers:
                column = columns[ self.headers[name] ]
            else:
                column = blank_column

            m.append([name] + column)

        m = list(transpose_to_lists(m))
        self.headers, self.matrix = self.__flux_headers_and_matrix(m)

        return self

    def __convert_renamed_or_inserted_header(self, header):
        """
        parentheses around inserted headers:
            to ensure new columns are being created intentionally and not because
            of spelling errors, inserted headers must be surrounded by parenthesis,
            eg: '(inserted_header)'
        """
        if not isinstance(header, (dict, str, bytes)):
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
            raise ValueError("'{header}' does not exist \n"
                             "inserted columns should be surrounded "
                             "by parenthesis, ie '({header})' not '{header}'".format(header=header))

        return header

    def rename_columns(self, old_to_new_mapping):
        header_names = self.header_names

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
        names = self.__standardize_variable_arity_arguments(names, depth=1)
        if not names:
            return self

        names = self.__validate_inserted_items(names, self.headers)
        names = list(reversed(names))

        header_names = self.header_names
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
        names = self.__standardize_variable_arity_arguments(names, depth=1)
        if not names:
            return self

        self.__validate_no_duplicate_names(names)
        self.__validate_no_names_intersect_with_headers(names, self.headers)

        v = [None for _ in names]
        self.reset_headers(self.header_names + list(names))

        for row in self.matrix[1:]:
            row.values.extend(v)

        return self

    def delete_columns(self, *names):
        """
        method will fail if columns are jagged, do a try / except on del row.values[i]
        then length check on row values if failure?
        """
        names = self.__standardize_variable_arity_arguments(names, depth=1)
        if not names:
            return self

        indices = self.__validate_names_as_indices(names, self.headers)
        self.__validate_no_duplicate_names(indices)

        all_columns_deleted = (set(self.headers.values()) == set(indices))
        if all_columns_deleted:
            return self.reset_matrix(None)

        indices.sort(reverse=True)
        for i in indices:
            for row in self.matrix:
                del row.values[i]

        self.reset_headers()

        return self

    def identify_jagged_rows(self):
        num_cols = self.num_cols
        for i, row in enumerate(self.matrix):
            if len(row.values) != num_cols:
                yield i, row

    def insert_rows(self, i, rows):
        if self.is_empty():
            self.headers, self.matrix = self.__flux_headers_and_matrix(rows)
            return self

        replace_headers = (i == 0)
        _, m = self.__flux_headers_and_matrix(rows, self.headers)

        if replace_headers:
            row = m.pop(0)
            self.reset_headers(row.values)

            i += 1
        else:
            if len(m) > len(rows):
                del m[0]

            if len(rows) != len(m):
                raise AssertionError('whoa, I messed something up...')

        self.matrix[i:i] = m

        return self

    def append_rows(self, rows):
        if self.is_empty():
            self.headers, self.matrix = self.__flux_headers_and_matrix(rows)
            return self

        _, m = self.__flux_headers_and_matrix(rows, self.headers)

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

        names = modify_iteration_depth(on_columns, depth=0)
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

        for n, so in zip(names, s_orders):
            rva = self.row_values_accessor(n)
            so  = bool(so)
            rows.sort(key=rva, reverse=so)

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
        self.__filter_unique_rows(*names, in_place=True)
        return self

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
        """ :return: dictionary of {row_value(row): row} """
        items = self.__map_row_items(names, rowtype=rowtype)
        return ordereddict(items)

    def map_rows_append(self, *names, rowtype='flux_row_cls'):
        """ :return: dictionary of {row_value(row): [rows]} """
        items = self.__map_row_items(names, rowtype=rowtype)

        return (OrderedDefaultDict(default=list)
                .append_items(items)
                .ordereddict())

    @deprecated('Use flux_cls.map_rows() method instead')
    def index_row(self, *names, rowtype='flux_row_cls'):
        """ deprecated """
        return self.map_rows(*names, rowtype=rowtype)

    @deprecated('Use flux_cls.map_rows_append() method instead')
    def index_rows(self, *names, rowtype='flux_row_cls'):
        """ deprecated """
        return self.map_rows_append(*names, rowtype=rowtype)

    def __map_row_items(self, names, rowtype):
        rowtype = self.__validate_mapped_rowtype(rowtype)

        rva  = self.row_values_accessor(names)
        rows = iter(self.matrix[1:])

        if rowtype == 'flux_row_cls':
            items = ((rva(row), row) for row in rows)
        elif rowtype == 'namedrow':
            items  = ((rva(row), v) for row, v in zip(rows, self.namedrows()))
        elif rowtype == 'namedtuple':
            items  = ((rva(row), v) for row, v in zip(rows, self.namedtuples()))
        elif rowtype == 'list':
            items = ((rva(row), row.values) for row in rows)
        elif rowtype == 'tuple':
            items = ((rva(row), tuple(row.values)) for row in rows)
        else:
            raise AssertionError

        return items

    def unique(self, *names):
        rva   = self.row_values_accessor(names)
        items = ((rva(row), None) for row in self.matrix[1:])

        return ordereddict(items).keys()

    def search(self, names, value, r_1=1, r_2=None):
        """ :return: yield (i, row) namedtuple where values match search value """
        Item = namedtuple('Item', 'i row')
        rva  = self.row_values_accessor(names)

        any_found = False
        for i, row in enumerate(self.matrix[r_1:r_2], r_1):
            if rva(row) == value:
                any_found = True
                yield Item(i, row)

        if not any_found:
            yield Item(None, None)

    def contiguous(self, *names):
        """ :return: yield (value, i_1, i_2) namedtuple where values are contiguous

        (contiguous values may only span a single row ie, i_1 == i_2)
        """
        Item = namedtuple('Item', 'value i_1 i_2')
        rva  = self.row_values_accessor(names)

        i_1 = 1
        v_2 = v_1 = rva(self.matrix[i_1])

        for i, row in enumerate(self.matrix[2:], 2):
            v_2 = rva(row)
            i_2 = i - 1

            if v_2 != v_1:
                yield Item(v_1, i_1, i_2)

                v_1 = v_2
                i_1 = i

        yield Item(v_2, i_1, self.num_rows)

    def label_row_indices(self, start=0):
        """ meant to assist with debugging;

        label each flux_row_cls.__dict__ with an index, which will then appear
        in each row's __repr__ function and make them easier to identify after
        filtering, sorting, etc
        """
        if 'i' in self.headers:
            raise NameError("'i' already exists as header name")

        for i, row in enumerate(self.matrix, start):
            row.__dict__['i'] = i

        return self

    def copy(self, deep=False):
        if deep:
            return deepcopy(self)

        m = [[*row.values] for row in self.matrix]
        flux = self.__class__(m)

        return flux

    def row_values_accessor(self, names):
        """ :return: a function that retrieves column values for each row in self.matrix """

        # region {closure functions}
        def were_names_submitted_as_tuples(n):
            """
            if names were submitted as tuples, row values should be returned as tuples,
            regardless if names contain only a single column

            names submitted as tuples:
                flux.map_rows(('col_a',))
            names not submitted as tuples:
                flux.map_rows('col_a')

            eg:
                True  = were_names_submitted_as_tuples( (('col_a',),) )
                False = were_names_submitted_as_tuples( ('col_a',) )
            """
            if not is_collection(n):
                return False

            return iteration_depth(n) >= 2 and isinstance(n[0], tuple)

        def are_indices_contiguous(indices):
            differences = [i_2 - i_1 for i_2, i_1 in zip(indices[1:], indices)]
            return set(differences) == {1}

        def row_slice(row):
            return tuple(row.values[i])

        def row_values(row):
            """ return muliple column values from each row """
            return tuple([row.values[_i_] for _i_ in i])

        def row_value(row):
            """ return single column value from each row """
            return row.values[i]
        # endregion

        if is_exhaustable(names):
            names = list(names)

        if were_names_submitted_as_tuples(names):
            names = modify_iteration_depth(names, depth=1)
        else:
            names = iterator_to_list(names)
            names = modify_iteration_depth(names, depth=0)
            names = iterator_to_list(names)

        if callable(names):
            f = names
        elif isinstance(names, slice):
            i = names
            f = row_slice
        elif iteration_depth(names) == 0:
            i = self.__validate_names_as_indices([names], self.headers)[0]
            f = row_value
        else:
            i = self.__validate_names_as_indices(names, self.headers)
            f = row_values

            if are_indices_contiguous(i):
                i = slice(i[0], i[-1]+1)
                f = row_slice

        return f

    def __getitem__(self, name):
        """
        MUST return a flat list if name is not a slice
            flux['col_a'] = flux['col_b']
        """
        if isinstance(name, slice):
            name = self.header_names[name]

        return self.columns(name)

    def __setitem__(self, name, values):
        """ sets values to a single column
        values are expected to exclude header row

        eg:
            flux['col'] = ['blah'] * flux.num_rows
            flux[-1]    = ['blah'] * flux.num_rows

            to insert column:
                flux[(0, 'new_col')] = ['blah'] * flux.num_rows
        """
        if isinstance(values, str):
            raise IterationDepthError('column values need to be an iterable')

        if isinstance(name, tuple) and len(name) == 2:
            self.insert_columns(name)
            name = name[-1]
        elif isinstance(name, slice):
            raise ValueError('__setitem__ cannot be used to set values to multiple columns')
        elif iteration_depth(name) > 0:
            raise ValueError('__setitem__ cannot be used to set values to multiple columns')

        if name not in self.headers and not isinstance(name, int):
            self.append_columns(name)

        i = self.__validate_names_as_indices([name], self.headers)[0]

        for row, v in zip(self.matrix[1:], values):
            row.values[i] = v

    def __bool__(self):
        return self.is_empty()

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
            return '()'

        if self.is_jagged():
            is_jagged = '🗲jagged🗲   '
        else:
            is_jagged = ''

        headers = ', '.join(str(n) for n in self.header_names)
        headers = '{' + headers + '}'

        return '{}{}  ({:,})'.format(is_jagged, headers, self.num_rows)

    # region {validation functions}
    @staticmethod
    def __validate_matrix_headers(names):
        names = map_to_numeric_indices(names)

        conflicting = names.keys() & set(flux_row_cls.reserved_names())
        if conflicting:
            raise ValueError('column name(s) conflict with existing headers: {}'.format(conflicting))

        return names

    # noinspection PyUnresolvedReferences
    @staticmethod
    def __validate_matrix(m):
        """ validate matrix datatype and has at least 2 dimensions;
        convert matrix to list of lists if neccessary
        """
        if m is None:
            return [[]]
        elif is_vengeance_class(m):
            return [[*row] for row in m.rows()]

        if is_exhaustable(m):
            m = list(m)

        base_names = set(base_class_names(m))
        if 'DataFrame' in base_names:
            raise NotImplementedError('matrix as DataFrame not supported')
        elif 'ndarray' in base_names:
            raise NotImplementedError('matrix as ndarray not supported')
        elif not is_subscriptable(m):
            raise TypeError("invalid type: <'{}'> matrix expected to be a list of lists".format(type(m)))

        first_row = m[0]

        if isinstance(first_row, flux_row_cls):
            m = [[*row.values] for row in m]
            if not first_row.is_header_row():
                m.insert(0, first_row.header_names)

        elif hasattr(first_row, '__dict__'):
            m = [list(row.__dict__.values()) for row in m]

            __dict__ = first_row.__dict__
            names  = list(__dict__.keys())
            values = map_to_numeric_indices(__dict__.values())
            values = list(values.keys())
            is_header_row = (names == values)

            if not is_header_row:
                m.insert(0, names)

        elif iteration_depth(m, first_element_only=True) < 2:
            raise IterationDepthError('matrix must have at least two dimensions (ie, a list of lists)')

        return m

    @staticmethod
    def __validate_mapped_rowtype(rowtype):
        validtypes = {'flux_row_cls',
                      'namedrow',
                      'namedtuple',
                      'tuple',
                      'list'}

        if not isinstance(rowtype, str):
            rowtype = object_name(rowtype)

        if rowtype.lower() not in validtypes:
            raise TypeError('rowtype parameter must be in the following: \n'
                            '{}'.format('\n\t'.join(validtypes)))

        return rowtype

    @staticmethod
    def __standardize_variable_arity_arguments(names, depth):
        if is_subscriptable(names) and is_exhaustable(names[0]):
            names = iterator_to_list(names[0])
        else:
            names = iterator_to_list(names)

        names = modify_iteration_depth(names, depth)

        if is_subscriptable(names) and is_exhaustable(names[0]):
            names = iterator_to_list(names[0])
        else:
            names = iterator_to_list(names)

        return names

    @staticmethod
    def __validate_name_datatypes(names, headers=None):
        valid_datatypes = (int, 
                           str, 
                           bytes)
        
        names = flux_cls.__standardize_variable_arity_arguments(names, depth=1)

        if headers is not None:
            flux_cls.__validate_names_not_empty(names)

            if isinstance(names[0], slice):
                names = names[0]
                names = list(headers.values())[names]
        
        invalid = [n for n in names if not isinstance(n, valid_datatypes)]
        if invalid:
            s = ("invalid column name datatype: '{}' "
                 "\nvalid datatypes are {}"
                 '\n'
                 '\n\t(make sure any arguments following variable position parameters are submitted by keyword)'
                 "\n\t\tflux.sort('column_a', 'column_b', reverse=True) "
                 '\n\tand not: '
                 "\n\t\tflux.sort('column_a', 'column_b', True)"
                 "\n".format(invalid, valid_datatypes))
            
            raise TypeError(s)

        return names

    @staticmethod
    def __validate_names_not_empty(names):
        if len(names) == 0:
            raise ValueError('no column names submitted')

    @staticmethod
    def __validate_inserted_items(inserted, headers):
        inserted = flux_cls.__standardize_variable_arity_arguments(inserted, depth=2)

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
            raise ValueError('duplicate column name(s) detected: \n{}'.format(duplicates))

        return names

    @staticmethod
    def __validate_no_names_intersect_with_headers(names, headers):
        names = flux_cls.__validate_name_datatypes(names, headers)

        conflicting = headers.keys() & set(names)
        if conflicting:
            raise ValueError('column name(s) conflict with existing headers: \n{}'.format(conflicting))

        return names

    @staticmethod
    def __validate_all_names_intersect_with_headers(names, headers):
        names = flux_cls.__validate_name_datatypes(names, headers)

        h_names = [*[ i for i in range(len(headers))],
                   *[-i for i in range(len(headers) + 1)]]
        h_names = headers.keys() | set(h_names)

        invalid = set(names) - h_names
        if invalid:
            raise ValueError(flux_cls.__names_not_exist_message(invalid, headers))

        return names

    @staticmethod
    def __validate_names_as_indices(names, headers):
        names = flux_cls.__validate_all_names_intersect_with_headers(names, headers)

        h_indices = list(headers.values())
        indices = [headers.get(n, n) for n in names]       # lookup strings
        indices = [h_indices[i] for i in indices]          # lookup negative integers

        return indices

    @staticmethod
    def __names_not_exist_message(invalid_names, headers):
        invalid_names = str(invalid_names)
        header_names  = '\n\t'.join(str(n) for n in headers.keys())

        s = ("\ncolumn name(s) not found: '{}' "
             "\n\tavailable columns: "
             "\n\t{}".format(invalid_names, header_names))
    
        return s
    
    @staticmethod
    def __invalid_names_message(invalid_names):
        invalid_names = str(invalid_names)

        s = ("invalid column name(s): '{}' "
             '\n\n\t(make sure arguments following variable position parameters are submitted as explicit keywords) '
             "\n\t\tflux.sort('column_a', 'column_b', reverse=True) "
             '\n\tand not: '
             "\n\t\tflux.sort('column_a', 'column_b', True)\n"
             .format(invalid_names))

        return s
    # endregion
