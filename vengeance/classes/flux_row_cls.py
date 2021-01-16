
from copy import copy
from collections import namedtuple
from types import SimpleNamespace

from ..util.iter import map_to_numeric_indices
from ..util.text import format_vengeance_header

from ..conditional import ordereddict
from ..conditional import numpy_installed

if numpy_installed:
    import numpy


class flux_row_cls:
    @classmethod
    def reserved_names(cls):
        reserved = [v for v in vars(flux_row_cls).keys()
                      if not v.startswith('_flux_row_cls')]
        reserved.append('_headers')
        reserved.append('values')

        reserved.sort()

        return reserved

    def __init__(self, headers, values):
        """
        :param headers: OrderedDict of {'header': int}
            headers is a single dictionary passed byref from the flux_cls to many flux_row_cls instances
            this eliminates need for all flux_row_cls objects to maintain a seprate copy of these mappings and
            allows for centralized and instantaneous updatdes
        :param values: list of underlying data

        properties must be set on self.__dict__ instead of directly on self to prevent
        premature __setattr__ lookups
        """
        self.__dict__['_headers'] = headers
        self.__dict__['values']   = values

    @property
    def as_array(self):
        """ to help with debugging: meant to trigger a debugging feature in PyCharm

        PyCharm will recognize the ndarray and enable the "...view as array"
        option in the debugger which displays values in a special window as a table
        """
        if not numpy_installed:
            raise ImportError('numpy site-package not installed')

        names   = [format_vengeance_header(n) for n in self.header_names()]
        values  = list(self.values)
        max_len = max(len(names), len(values))

        names.extend(['🗲'] * (max_len - len(names)))
        values.extend(['🗲jagged🗲'] * (max_len - len(values)))

        names  = numpy.array(names,  dtype=object)
        values = numpy.array(values, dtype=object)

        return numpy.transpose([names, values])

    @property
    def headers(self):
        return copy(self._headers)

    def header_names(self):
        return list(self._headers.keys())

    def is_jagged(self):
        return len(self._headers) != len(self.values)

    def is_empty(self):
        return (len(self._headers) == 0) and (len(self.values) == 0)

    def is_header_row(self):
        """ determine if underlying values match self._headers.keys

        self.names == self.values will not always work, since map_numeric_indices()
        was used to modify self._headers values into more suitable dictionary keys,
        like modifying duplicate values to ensure they are unique, etc
        """
        if not self._headers:
            return False

        names = map_to_numeric_indices(self.values)
        return self._headers.keys() == names.keys()

    def dict(self):
        names = self.header_names()
        return ordereddict(zip(names, self.values))

    def namedrow(self):
        return SimpleNamespace(**self.dict())

    # noinspection PyArgumentList
    def namedtuple(self):
        FluxRow = namedtuple('FluxRow', self.header_names())
        return FluxRow(*self.values)

    # noinspection PyProtectedMember,PyUnusedLocal
    def join_values(self, row_b, on_columns=None):
        """ copies all values where header names are shared with row_b
        :type row_b: flux_row_cls
        :type on_columns: shared column names
        """
        # region {closure function}
        def intersecting_names(_names_):
            if not _names_:
                _names_ = headers_a.keys() & headers_b.keys()
                if not _names_:
                    raise ValueError('no intersecting column names')

            return _names_
        # endregion

        if not isinstance(row_b, flux_row_cls):
            raise TypeError('row expected to be flux_row_cls')

        headers_a = self._headers
        headers_b = row_b._headers

        values_a  = self.values
        values_b  = row_b.values

        names = intersecting_names(on_columns)

        for name in names:
            i_b = headers_b[name]
            i_a = headers_a[name]

            values_a[i_a] = values_b[i_b]

    def __getattr__(self, name):
        """  eg:
             o = row.column
        """
        try:
            i = self._headers.get(name, name)
            return self.values[i]
        except (TypeError, IndexError):
            raise AttributeError(self.__name_not_exist_message(name, self.header_names())) from None

    def __getitem__(self, name):
        """ eg:
            o = row['column']
        """
        try:
            i = self._headers.get(name, name)
            return self.values[i]
        except (TypeError, IndexError):
            if isinstance(name, slice):
                return self.values[name]

            raise AttributeError(self.__name_not_exist_message(name, self.header_names())) from None

    def __setattr__(self, name, value):
        """ eg:
            row.column = o
        """
        try:
            i = self._headers.get(name, name)
            self.values[i] = value
        except (TypeError, IndexError):
            if name in self.__dict__:
                self.__dict__[name] = value
            else:
                raise AttributeError(self.__name_not_exist_message(name, self.header_names())) from None

    def __setitem__(self, name, value):
        """ eg:
            row['column'] = o
        """
        try:
            i = self._headers.get(name, name)
            self.values[i] = value
        except (TypeError, IndexError):
            if name in self.__dict__:
                self.__dict__[name] = value
            elif isinstance(name, slice):
                self.values[name] = value
            else:
                raise AttributeError(self.__name_not_exist_message(name, self.header_names())) from None

    def __len__(self):
        return len(self.values)

    def __bool__(self):
        return bool(self.values)

    def __iter__(self):
        return iter(self.values)

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return id(self._headers) + hash(tuple(self.values))

    def __getstate__(self):
        return self.__dict__

    def __setstate__(self, d):
        self.__dict__ = d

    def __repr__(self):
        if 'r_i' in self.__dict__:
            row_index = 'r_i: {:,}    '.format(self.__dict__['r_i']).replace(',', '_')
        else:
            row_index = ''

        if self.is_jagged():
            is_jagged = '🗲jagged🗲  '
        else:
            is_jagged = ''

        if self.is_header_row():
            values = ', '.join(str(n) for n in self.header_names())
            values = format_vengeance_header(values)
        else:
            values = (repr(self.values).replace('"', '')
                                       .replace("'", ''))

        return '{}{}{}'.format(row_index, is_jagged, values)

    @staticmethod
    def __name_not_exist_message(invalid_name, header_names):
        if isinstance(invalid_name, slice):
            return 'slice should be used directly on row.values\n(eg, row.values[2:5], not row[2:5])'

        s = '\n\t'.join(str(n) for n in header_names)
        s = ("\ncolumn name not found: '{}' "
             "\navailable columns: "
             "\n\t{}".format(invalid_name, s))

        return s



