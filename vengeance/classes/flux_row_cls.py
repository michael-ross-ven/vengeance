
from collections import namedtuple
from copy import copy
from copy import deepcopy
from typing import Dict
from typing import List
from typing import Union

from ..util.classes.namespace_cls import namespace_cls
from ..util.iter import is_header_row
from ..util.iter import values_as_strings

from ..util.text import surround_double_brackets
from ..util.text import surround_single_brackets
from ..util.text import format_integer

from ..conditional import ordereddict
from ..conditional import numpy_installed

if numpy_installed:
    import numpy


class flux_row_cls:

    @classmethod
    def reserved_names(cls):
        n_1 = ['headers', 'values', 'row_label']
        n_2 = list(sorted(dir(cls), reverse=True))

        return n_1 + n_2

    def __init__(self, headers, values, row_label=None):
        """
        :param headers: OrderedDict of {'header': int}
            headers is a single dictionary passed byref from the flux_cls to many flux_row_cls instances
            this eliminates need for all flux_row_cls objects to maintain a seprate copy of these mappings and
            allows for centralized and instantaneous updatdes
        :param values: list of underlying data

        properties must be set on self.__dict__ instead of directly on self to prevent
        premature __setattr__ lookups
        """
        ''' @types '''
        self.headers:   Dict[Union[str, bytes], int]
        self.values:    List
        self.row_label: Union[int, str]

        self.__dict__['headers']   = headers
        self.__dict__['values']    = values
        self.__dict__['row_label'] = row_label

    @property
    def _preview_as_tuple(self) -> List:
        """ to help with debugging """
        names  = [surround_double_brackets(n) for n in self.header_names()]
        values = list(self.values)

        c_m = max(len(names), len(values))
        names.extend(['🗲missing🗲']  * (c_m - len(names)))
        values.extend(['🗲missing🗲'] * (c_m - len(values)))

        label = self.__dict__['row_label']

        if isinstance(label, int):
            names.insert(0,  '{label}')
            label = format_integer(label)
            label = surround_single_brackets(label)

            values.insert(0, label)
        elif isinstance(label, str):
            names.insert(0,  '{label}')
            label = surround_single_brackets(label)

            values.insert(0, label)

        m = list(zip(names, values))

        return m

    @property
    def _preview_as_array(self):
        """
        to help with debugging: meant to trigger a debugging feature in PyCharm
        PyCharm will recognize the ndarray and enable the "...view as array"
        option in the debugger which displays values in a special window as a table
        """
        m = self._preview_as_tuple
        if numpy_installed:
            m = numpy.array(m, dtype=object)

        return m

    def header_names(self, as_strings=True) -> List[Union[str, bytes]]:
        """
        self.values and self.headers.keys may not always be identical
            map_values_to_enum() makes certain modifications to self.headers.keys,
            such as coercing values to str, modifying duplicate values, etc
        """
        names = list(self.headers.keys())
        if as_strings:
            names = list(values_as_strings(names))

        return names

    def is_jagged(self):
        return len(self.headers) != len(self.values)

    def is_empty(self):
        return (len(self.headers) == 0) and (len(self.values) == 0)

    def is_header_row(self):
        """ determine if underlying values match self.headers.keys

        self.names == self.values will not always work, since map_values_to_enum()
        was used to modify self.headers values into more suitable dictionary keys,
        like modifying duplicate values to ensure they are unique, etc
        """
        return is_header_row(self.values,
                             self.headers)

    def dict(self):
        return ordereddict(zip(self.header_names(), self.values))

    def namedrow(self):
        return namespace_cls(zip(self.header_names(), self.values))

    def namedtuple(self):
        row_nt = namedtuple('Row', self.header_names(as_strings=True))
        return row_nt(*self.values)

    def join_values(self, other, names=None):
        """ copies all values where header names are shared with row_b
        :type other: flux_row_cls
        :type names: list[str]
        """
        ''' @types '''
        other: flux_row_cls
        names: Union[str, List]

        if not isinstance(other, flux_row_cls):
            raise TypeError('row expected to be flux_row_cls')

        headers_self  = self.__dict__['headers']
        headers_other = other.__dict__['headers']

        names_both = names or (headers_self.keys() & headers_other.keys())
        if not names_both:
            raise ValueError('no intersecting column names')

        if isinstance(names_both, str):
            names_both = [names_both]

        values_self  = self.__dict__['values']
        values_other = other.__dict__['values']

        for name in names_both:
            i_s = headers_self[name]
            i_o = headers_other[name]

            values_self[i_s] = values_other[i_o]

    def copy(self, deep=False):
        """
        # other_attributes = {k: v for k, v in self.__dict__.items()
        #                          if k not in {'headers', 'values', 'row_label'}}
        # flux_row.__dict__.update(other_attributes)
        """

        if deep:
            headers   = deepcopy(self.__dict__['headers'])
            values    = deepcopy(self.__dict__['values'])
            row_label = None
        else:
            headers   = copy(self.__dict__['headers'])
            values    = copy(self.__dict__['values'])
            row_label = self.__dict__['row_label']

        flux_row = self.__class__(headers,
                                  values,
                                  row_label)
        return flux_row

    def __getattr__(self, name):
        """  eg:
             o = row.column
        """
        try:
            i = self.headers.get(name, name)
            return self.values[i]
        except (TypeError, IndexError):
            self.__raise_attribute_error(name, self.headers)

    def __setattr__(self, name, value):
        """ eg:
            row.column = o
        """
        try:
            i = self.headers.get(name, name)
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
            i = self.headers.get(name, name)
            return self.values[i]
        except (TypeError, IndexError):
            if isinstance(name, slice):
                return self.values[name]
            else:
                self.__raise_attribute_error(name, self.headers)

    def __setitem__(self, name, value):
        """ eg:
            row['column'] = o
        """
        try:
            i = self.headers.get(name, name)
            self.values[i] = value
        except (TypeError, IndexError) as e:
            if name in self.__dict__:
                self.__dict__[name] = value
            elif isinstance(name, slice):
                self.values[name] = value
            elif isinstance(self.values, tuple):
                raise e
            else:
                self.__raise_attribute_error(name, self.headers)

    def __len__(self):
        return len(self.values)

    def __bool__(self):
        return bool(self.values)

    def __iter__(self):
        return iter(self.values)

    def __eq__(self, other):
        a = id(self.__dict__['headers'])  + hash(tuple(self.__dict__['values']))
        b = id(other.__dict__['headers']) + hash(tuple(other.__dict__['values']))

        return a == b

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        row_label    = self.__dict__['row_label']
        jagged_label = ''

        if isinstance(row_label, int):
            row_label = format_integer(row_label)
            row_label = surround_single_brackets(row_label)
            row_label = '{} '.format(row_label)
        elif isinstance(row_label, str):
            row_label = surround_single_brackets(row_label)
            row_label = '{} '.format(row_label)
        else:
            row_label = ''

        if self.is_jagged():
            jagged_label = len(self.values) - len(self.headers)
            jagged_label = '{' + '{:+}'.format(jagged_label) + '}'
            jagged_label = '🗲jagged {}🗲  '.format(jagged_label)

        if self.is_header_row():
            values = self.header_names(as_strings=True)
            values = ', '.join(values)
            values = surround_double_brackets(values)
        else:
            values = repr(self.values).replace('"', "'")

        return '{}{}{}'.format(row_label, jagged_label, values)

    @staticmethod
    def __raise_attribute_error(invalid, headers):
        indices = [str(i) for i in headers.values()]
        _nf_    = max(len(n) for n in indices)
        _nf_    = '{: <%i}' % _nf_
        indices = [_nf_.format(n) for n in indices]

        err_msg = ["{}: '{}'".format(i, n) for i, n in zip(indices, headers.keys())]
        err_msg = '\n\t'.join(err_msg)
        err_msg = ("Name, '{}' is not in existing columns: "
                   "\n\t{}".format(invalid, err_msg))

        raise AttributeError(err_msg) from None

