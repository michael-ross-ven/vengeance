
from ... classes.flux_row_cls import flux_row_cls


# noinspection PyMissingConstructor
class lev_row_cls(flux_row_cls):
    @classmethod
    def reserved_names(cls):
        reserved = super().reserved_names() + ['address']
        return sorted(reserved)

    def __init__(self, headers, values, address=''):
        self.__dict__['_headers'] = headers
        self.__dict__['values']   = values
        self.__dict__['address']  = address


