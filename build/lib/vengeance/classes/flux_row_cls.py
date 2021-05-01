
from collections import namedtuple

from typing import Dict
from typing import List

from ..util.iter import namespace_cls
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
        self._headers: Dict[str, int]
        self.values:   List

        self.__dict__['_headers'] = headers
        self.__dict__['values']   = values

    @property
    def as_array(self):
        """
        to help with debugging: meant to trigger a debugging feature in PyCharm
        PyCharm will recognize the ndarray and enable the "...view as array"
        option in the debugger which displays values in a special window as a table
        """
        names  = [format_header(n) for n in self.header_names()]
        values = list(self.__dict__['values'])

        c_m = max(len(names), len(values))
        names.extend(['🗲']          * (c_m - len(names)))
        values.extend(['🗲jagged🗲'] * (c_m - len(values)))

        if 'address' in self.__dict__:
            names.insert(0,  '⟨address⟩')
            values.insert(0, '⟨{}⟩'.format(self.__dict__['address']))
        elif 'r_i' in self.__dict__:
            names.insert(0,  '⟨address⟩')
            values.insert(0, '⟨{:,}⟩'.format(self.__dict__['r_i']).replace(',', '_'))

        m = list(zip(names, values))

        if not numpy_installed:
            _nf_ = max([len(n) for n in names])  + 1
            _nf_ = '{: <%s}' % str(_nf_)

            m = [' '.join([_nf_.format(n), v]) for n, v in m]
            m = '\n'.join(m)

            return m

        return numpy.array(m, dtype=object)

    @property
    def headers(self):
        return ordereddict(self.__dict__['_headers'].items())

    def header_names(self):
        return list(self.__dict__['_headers'].keys())

    def is_jagged(self):
        return len(self.__dict__['_headers']) != len(self.__dict__['values'])

    def is_empty(self):
        return (len(self.__dict__['_headers']) == 0) and (len(self.__dict__['values']) == 0)

    def is_header_row(self):
        """ determine if underlying values match self._headers.keys

        self.names == self.values will not always work, since inverted_enumerate()
        was used to modify self._headers values into more suitable dictionary keys,
        like modifying duplicate values to ensure they are unique, etc
        """
        return is_header_row(self.__dict__['values'],
                             self.__dict__['_headers'])

    def dict(self):
        return ordereddict(zip(self.header_names(), self.__dict__['values']))

    def namedrow(self):
        d = ordereddict(zip(self.header_names(), self.__dict__['values']))
        return namespace_cls(**d)

    # noinspection PyArgumentList
    def namedtuple(self):
        row_nt = namedtuple('row', self.header_names())
        return row_nt(*self.__dict__['values'])

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

        headers_a = self.__dict__['_headers']
        headers_b = row_b._headers

        values_a  = self.__dict__['values']
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
            i = self.__dict__['_headers'].get(name, name)
            return self.__dict__['values'][i]
        except (TypeError, IndexError):
            self.__raise_attribute_error(name, self.headers)

    def __setattr__(self, name, value):
        """ eg:
            row.column = o
        """
        try:
            i = self.__dict__['_headers'].get(name, name)
            self.__dict__['values'][i] = value
        except (TypeError, IndexError) as e:

            if name in self.__dict__:
                self.__dict__[name] = value
            elif isinstance(self.__dict__['values'], tuple):
                raise e
            else:
                self.__raise_attribute_error(name, self.headers)

    def __getitem__(self, name):
        """ eg:
            o = row['column']
        """
        try:
            i = self.__dict__['_headers'].get(name, name)
            return self.__dict__['values'][i]
        except (TypeError, IndexError):
            if isinstance(name, slice):
                return self.__dict__['values'][name]

            self.__raise_attribute_error(name, self.headers)

    def __setitem__(self, name, value):
        """ eg:
            row['column'] = o
        """
        try:
            i = self.__dict__['_headers'].get(name, name)
            self.__dict__['values'][i] = value
        except (TypeError, IndexError) as e:

            if isinstance(self.__dict__['values'], tuple):
                raise e
            elif isinstance(name, slice):
                self.__dict__['values'][name] = value
            elif name in self.__dict__:
                self.__dict__[name] = value
            else:
                self.__raise_attribute_error(name, self.headers)

    def __len__(self):
        return len(self.__dict__['values'])

    def __bool__(self):
        return bool(self.__dict__['values'])

    def __iter__(self):
        return iter(self.__dict__['values'])

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return id(self.__dict__['_headers']) + hash(tuple(self.__dict__['values']))

    def __repr__(self):
        if 'address' in self.__dict__:
            row_label = format_header_lite(self.__dict__['address'])
            row_label = ' {}   '.format(row_label)
        elif 'r_i' in self.__dict__:
            row_label = format_integer(self.__dict__['r_i'])
            row_label = format_header_lite(row_label)
            row_label = ' {}   '.format(row_label)
        else:
            row_label = ''

        if self.is_jagged():
            jagged_label = len(self.__dict__['values']) - len(self.__dict__['_headers'])
            jagged_label = format_header_lite('{:+}'.format(jagged_label))
            jagged_label = ' 🗲jagged {}🗲  '.format(jagged_label)
        else:
            jagged_label = ''

        if self.is_header_row():
            values = ', '.join(str(n) for n in self.header_names())
            values = format_header(values)
        else:
            values = (repr(self.__dict__['values']).replace('"', '')
                                                   .replace("'", ''))

        return '{}{}{}'.format(row_label, jagged_label, values)

    @staticmethod
    def __raise_attribute_error(invalid, headers):
        s = '\n\t'.join((repr(n)[1:-1].replace(',', ':')
                                      .replace("'", '')
                                      .replace('"', '')) for n in headers.items())
        s = ("'{}' column name does not exist, available columns: "
             "\n\t{}".format(invalid, s))

        raise AttributeError(s) from None

