
from collections import OrderedDict
from collections import namedtuple


class flux_row_cls:

    class_names = {'_headers',
                   'values',
                   'names',
                   'dict',
                   'namedtuples'}

    def __init__(self, headers, values):
        """
        :param headers: OrderedDict of {'header': index}

            * headers is a single dictionary passed byref from the
              flux_cls to many flux_row_cls instances
            * this eliminates need for all flux_row_cls objects
              to maintain a seprate copy of these mappings and
              allows for centralized and instantaneous updatdes

        :param values: list of underlying data

        self.__dict__ is used to set attributes in __init__ so as to avoid
        premature __setattr__ lookups
        """
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

    def dict(self):
        return OrderedDict(zip(self.names, self.values))

    def namedtuples(self, nt_cls=None):
        try:
            if nt_cls is None:
                nt_cls = namedtuple('flux_row_nt', self.names)

            return nt_cls(*self.values)
        except ValueError as e:
            import re

            names = [n for n in self.names if re.search('^[^a-z]|[ ]', str(n), re.I)]
            if names:
                raise ValueError('invalid field(s) for namedtuple constructor: {}'.format(names)) from e
            else:
                raise e

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
            raise AttributeError(self.__attr_err_msg(name)) from e

    def __setitem__(self, name, value):
        """ eg:
            row['column'] = v
        """
        try:
            i = self._headers.get(name, name)
            self.values[i] = value
        except (TypeError, IndexError) as e:
            raise AttributeError(self.__attr_err_msg(name)) from e

    def __attr_err_msg(self, name):
        if isinstance(name, slice):
            return 'slice should be used on row.values\n(eg, row.values[2:5], not row[2:5])'

        names = '\n\t'.join(self.names)
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
                   'values',
                   'names',
                   'dict',
                   'namedtuples',
                   'address'}

    def __init__(self, headers, values, address):
        super().__init__(headers, values)
        self.__dict__['address'] = address

    def __repr__(self):
        return '{} {}'.format(self.address, repr(self.values))

