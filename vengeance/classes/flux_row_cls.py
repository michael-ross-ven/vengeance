
import textwrap

from collections import OrderedDict
from collections import namedtuple

from .. util.text import repr_


class flux_row_cls:

    class_names = {'_headers',
                   'is_bound',
                   'values'}

    def __init__(self, headers, values):
        """
        :param headers: OrderedDict of {'header': index}
        :param values:  list of underlying data

        headers is a single dictionary passed *byref* from the
        flux_cls to all flux_row_cls instances, reducing unneccesary
        memory usage and allowing all mapping updates to be made
        instantaneously

        namedtuples may be more efficient, but too much of a headache to deal
        with their immutability
        """
        # cannot set attributes directly in __init__ as this invokes __setattr__ lookup too early
        self.__dict__['_headers'] = headers
        self.__dict__['values']   = values
        self.__dict__['is_bound'] = False

    @property
    def names(self):
        return list(self._headers.keys())

    @property
    def view_as_array(self):
        """ for development purposes; used purely to trigger a debugging feature in PyCharm

        PyCharm will recognize returned the (name, value) pairs as an ndarray
        and enable the "...view as array" option in the debugger which displays
        values in a special window
        """
        import numpy
        return numpy.transpose([self.names, self.values])

    def dict(self):
        return OrderedDict(zip(self.names, self.values))

    def namedtuples(self):
        try:
            nt_cls = namedtuple('flux_row_nt', self.names)
            return nt_cls(*self.values)
        except ValueError as e:
            import re

            names = [n for n in self.names
                       if re.search('^[^a-z]|[ ]', n, re.IGNORECASE)]
            raise ValueError("invalid headers for namedtuple: {}".format(names)) from e

    def bind(self):
        """ bind headers / values directly to instance, avoiding need for subsequent __getattr__ lookups
        (only use this if you know the side-effects)
        """
        self.__dict__.update(zip(self.names, self.values))

        self.__dict__['values']   = '(values bound to __dict__)'
        self.__dict__['is_bound'] = True

    def unbind(self, instance_names=None):
        """ ehhh, this could still require some work if headers have been substantially modified ... """
        if not self.__dict__['is_bound']:
            return

        if instance_names is None:
            instance_names = self.__dict__.keys() - self.class_names

        values = self.__dict__['values'] = []
        for k in instance_names:
            v = self.__dict__.pop(k)
            values.append(v)

        self.__dict__['is_bound'] = False

    def __getattr__(self, name):
        """  eg:
             v = row.header

        self.__dict__ is empty when being deserialized from a binary file
        '__setstate__' key must be called with self.__getattribute__
        """
        if not self.__dict__:
            return self.__getattribute__(name)

        return self.__getitem__(name)

    def __getitem__(self, name):
        """ eg:
            v = row['header']

        list index is translated from self._headers dictionary
        self._headers.get(name, name) is a shortcut for avoiding an isinstance(name, int) check

        i *could* handle slices here eg, row[1:], but it would just be easier
        for client to call row.values[1:] instead
        """
        try:
            i = self.__dict__['_headers'].get(name, name)
            return self.__dict__['values'][i]
        except (TypeError, IndexError):
            pass

        raise AttributeError(self.__attr_err_msg(name))

    def __setattr__(self, name, value):
        """ eg:
            row.header = v
        """
        if name in self.__dict__:               # a flux_row_cls property
            self.__dict__[name] = value
        else:                                   # a {self._headers: self.values} pair
            self.__setitem__(name, value)

    def __setitem__(self, name, value):
        """ eg:
            row['header'] = v
        """
        try:
            i = self.__dict__['_headers'].get(name, name)
            self.__dict__['values'][i] = value
            return
        except (TypeError, IndexError):
            pass

        raise AttributeError(self.__attr_err_msg(name))

    def __attr_err_msg(self, name):
        if isinstance(name, slice):
            return 'slice should be used on row.values\n(eg, row.values[2:5], not row[2:5])'

        names = repr_(self.names, concat=',\n', quotes=True)
        names = textwrap.indent(names, '  ')

        return "flux_row_cls\nno column named: '{}' from\n{}".format(name, names)

    def __len__(self):
        return len(self.values)

    def __iter__(self):
        return iter(self.values)

    def __repr__(self):
        return 'flux_row: ' + repr(self.values)


class lev_row_cls(flux_row_cls):

    class_names = {'_headers',
                   'is_bound',
                   'values',
                   'address'}

    def __init__(self, headers, values, address):
        super().__init__(headers, values)
        self.__dict__['address'] = address

    def __repr__(self):
        return self.address + ' ' + repr(self.values)
