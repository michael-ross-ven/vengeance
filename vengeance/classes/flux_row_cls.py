
import textwrap

from collections import OrderedDict
from collections import namedtuple

from .. util.text import repr_iter


class flux_row_cls:

    def __init__(self, headers, values):
        """ basically, a mutable namedtuple

        :param headers: OrderedDict of {'header': index}
        :param values:  list of underlying data

        headers is a single dictionary passed *byref* from the
        flux_cls to all flux_row_cls instances, reducing unneccesary
        memory usage and allowing all mapping updates to be made
        instantaneously

            namedtuples may be more efficient, but too much of a headache to deal
            with their immutability

            maybe __slots__ or weakref / metaclass would be better?
            Effective Python: Item 35: Annotate Class Attributes with Metaclasses
        """
        # cannot call attributes directly in __init__ as this invokes __setattr__ lookup too early
        self.__dict__['_headers'] = headers
        self.__dict__['values']   = values

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

    def bind(self):
        """ bind headers / values directly to object, avoiding need for subsequent __getattr__ lookups
        ooooooooooh this is dangerous to flux_cls tho
        """
        self.__dict__.update(zip(self.names, self.values))

    def dict(self):
        return OrderedDict(zip(self.names, self.values))

    def namedtuples(self):
        nt_cls = namedtuple('flux_row_nt', self.names)
        return nt_cls(*self.values)

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

        names = repr_iter(self.names, concat=',\n', quotes=True)
        names = textwrap.indent(names, '  ')

        return "flux_row_cls\nno column named: '{}' from\n{}".format(name, names)

    def __len__(self):
        return len(self.values)

    def __iter__(self):
        return iter(self.values)

    def __repr__(self):
        return '<flux_row> ' + repr(self.values)


class lev_row_cls(flux_row_cls):

    def __init__(self, headers, values, address):
        super().__init__(headers, values)
        self.__dict__['address'] = address

    def __repr__(self):
        return self.address + ' ' + repr(self.values)
