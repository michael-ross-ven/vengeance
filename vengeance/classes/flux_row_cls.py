
from collections import OrderedDict
from collections import namedtuple
from ..util.iter import map_numeric_indices


# noinspection DuplicatedCode
class flux_row_cls:

    class_names = {'_headers',
                   '_view_as_array',
                   'names',
                   'values',
                   'is_header_row',
                   'dict',
                   'namedtuples'}

    def __init__(self, headers, values):
        """
        :param headers: OrderedDict of {'header': index}
            headers is a single dictionary passed byref from the flux_cls to many flux_row_cls instances
            this eliminates need for all flux_row_cls objects to maintain a seprate copy of these mappings and
            allows for centralized and instantaneous updatdes
        :param values: list of underlying data

        (properties must be set on self.__dict__ instead of directly on self to prevent
         premature __setattr__ lookups)
        """
        self.__dict__['_headers'] = headers
        self.__dict__['values']   = values

    @property
    def _view_as_array(self):
        """ to help with debugging; meant to trigger a debugging feature in PyCharm

        PyCharm will recognize returned the (name, value) pairs as an ndarray
        and enable the "...view as array" option in the debugger which displays
        values in a special window as a table
        """
        import numpy
        return numpy.transpose([self.names, self.values])

    @property
    def names(self):
        return list(self._headers.keys())

    def is_header_row(self):
        """ determine if underlying values match self._headers.keys

        self.names == self.values will not always work, since map_numeric_indices()
        was used to modify self._headers values into more suitable dictionary keys,
        like modifying duplicate values to ensure they are unique, etc
        """
        header_names = list(map_numeric_indices(self.values).keys())
        return self.names == header_names

    def dict(self):
        return OrderedDict(zip(self.names, self.values))

    def namedtuples(self):
        return namedtuple('flux_row_ntc', self.names)(*self.values)

    def __getattr__(self, name):
        """  eg:
             v = row.column
        """
        try:
            i = self._headers.get(name, name)
            return self.values[i]
        except (TypeError, IndexError) as e:
            raise AttributeError(self.__attr_err_msg(name)) from e

    def __getitem__(self, name):
        """ eg:
            v = row['column']
        """
        try:
            i = self._headers.get(name, name)
            return self.values[i]
        except (TypeError, IndexError) as e:
            raise AttributeError(self.__attr_err_msg(name)) from e

    def __setattr__(self, name, value):
        """ eg:
            row.column = v
        """
        try:
            i = self._headers.get(name, name)
            self.values[i] = value
        except (TypeError, IndexError) as e:
            if name in self.__dict__:
                self.__dict__[name] = value
            else:
                raise AttributeError(self.__attr_err_msg(name)) from e

    def __setitem__(self, name, value):
        """ eg:
            row['column'] = v
        """
        try:
            i = self._headers.get(name, name)
            self.values[i] = value
        except (TypeError, IndexError) as e:
            if name in self.__dict__:
                self.__dict__[name] = value
            else:
                raise AttributeError(self.__attr_err_msg(name)) from e

    def __attr_err_msg(self, name):
        if isinstance(name, slice):
            return 'slice should be used directly on row.values\n(eg, row.values[2:5], not row[2:5])'

        names = '\n\t'.join(str(n) for n in self.names)
        return "No flux_row_cls column named '{}'\navailable columns:\n\t{}".format(name, names)

    def __getstate__(self):
        return self.__dict__

    def __setstate__(self, d):
        super().__setattr__('__dict__', d)

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

    def __repr__(self):
        i = self.__dict__.get('i', '')
        if i != '':
            i = '({:,})  '.format(i)

        return '{}{}'.format(i, repr(self.values))


class lev_row_cls(flux_row_cls):

    class_names = {'_headers',
                   '_view_as_array',
                   'names',
                   'values',
                   'address',
                   'is_header_row',
                   'dict',
                   'namedtuples'}

    def __init__(self, headers, values, address=''):
        super().__init__(headers, values)

        self.__dict__['address'] = address

    def __repr__(self):
        return '{} {}'.format(self.address, repr(self.values))

