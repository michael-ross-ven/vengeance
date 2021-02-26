
from copy import copy
from collections import namedtuple

from ..util.iter import namespace
from ..util.iter import is_header_row
from ..util.text import format_header
from ..util.text import format_header_lite
from ..util.text import format_integer

from ..conditional import ordereddict
from ..conditional import numpy_installed

if numpy_installed:
    import numpy


class flux_row_cls:

    @classmethod
    def reserved_names(cls):
        return ['_headers', 'values'] + dir(cls)

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
        """
        to help with debugging: meant to trigger a debugging feature in PyCharm
        PyCharm will recognize the ndarray and enable the "...view as array"
        option in the debugger which displays values in a special window as a table
        """
        if not numpy_installed:
            raise ImportError('numpy site-package not installed')

        names  = [format_header(n) for n in self.header_names()]
        values = list(self.values)

        c_m = max(len(names), len(values))
        names.extend(['🗲']          * (c_m - len(names)))
        values.extend(['🗲jagged🗲'] * (c_m - len(values)))

        if 'address' in self.__dict__:
            names.insert(0,  '⟨address⟩')
            values.insert(0, '⟨{}⟩'.format(self.__dict__['address']))

        if 'r_i' in self.__dict__:
            names.insert(0,  '⟨r_i⟩')
            values.insert(0, '⟨{:,}⟩'.format(self.__dict__['r_i']).replace(',', '_'))

        # noinspection PyUnresolvedReferences
        return numpy.transpose([numpy.array(names,  dtype=object),
                                numpy.array(values, dtype=object)])

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

        self.names == self.values will not always work, since map_values_to_enum()
        was used to modify self._headers values into more suitable dictionary keys,
        like modifying duplicate values to ensure they are unique, etc
        """
        return is_header_row(self.values, self._headers)

    def namedrow(self):
        d = ordereddict(zip(self.header_names(), self.values))
        return namespace(**d)

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
            self.__raise_attribute_error(name, self.headers)

    def __setattr__(self, name, value):
        """ eg:
            row.column = o
        """
        try:
            i = self._headers.get(name, name)
            self.values[i] = value
        except (TypeError, IndexError) as e:

            if name in self.__dict__:
                self.__dict__[name] = value
            elif isinstance(self.values, tuple):
                raise e
            else:
                self.__raise_attribute_error(name, self.headers)

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

            self.__raise_attribute_error(name, self.headers)

    def __setitem__(self, name, value):
        """ eg:
            row['column'] = o
        """
        try:
            i = self._headers.get(name, name)
            self.values[i] = value
        except (TypeError, IndexError) as e:

            if isinstance(self.values, tuple):
                raise e
            elif isinstance(name, slice):
                self.values[name] = value
            elif name in self.__dict__:
                self.__dict__[name] = value
            else:
                self.__raise_attribute_error(name, self.headers)

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
            row_label = format_integer(self.__dict__['r_i'])
            row_label = format_header_lite(row_label)
            row_label = '{}   '.format(row_label)
        elif 'address' in self.__dict__:
            row_label = format_header_lite(self.__dict__['address'])
            row_label = '{}   '.format(row_label)
        else:
            row_label = ''

        if self.is_jagged():
            is_jagged = '🗲jagged🗲  '
        else:
            is_jagged = ''

        if self.is_header_row():
            values = ', '.join(str(n) for n in self.header_names())
            values = format_header(values)
        else:
            values = (repr(self.values).replace('"', '')
                                       .replace("'", ''))

        return ' {}{}{}'.format(row_label, is_jagged, values)

    @staticmethod
    def __raise_attribute_error(invalid, headers):
        s = '\n\t'.join((repr(n)[1:-1].replace(',', ':')
                                      .replace("'", '')
                                      .replace('"', '')) for n in headers.items())
        s = ("'{}' column name does not exist, available columns: "
             "\n\t{}".format(invalid, s))

        raise AttributeError(s) from None




