
from ... conditional import ordereddict


class namespace_cls:
    """
    similar to types.SimpleNamespace
    """
    def __init__(self, **kwargs):
        self.__dict__ = ordereddict(kwargs)

    @property
    def _namespace_attributes(self):
        return self.__dict__

    @property
    def _namespace_pformat(self):
        keys = ['{!r}: '.format(k) for k in self.__dict__.keys()]
        _padding_right_  = '{: <%i}' % max(len(k) for k in keys)

        keys  = [_padding_right_.format(k) for k in keys]
        items = ['{} {!r}'.format(k, v) for k, v in zip(keys, self.__dict__.values())]
        items = '\n'.join(items)
        items = items.replace("'", '"')

        return items

    def __iter__(self):
        return ((k, v) for k, v in self.__dict__.items())

    def __eq__(self, other):
        if (not hasattr(self, '__dict__')) or (not hasattr(other, '__dict__')):
            return NotImplemented

        return self.__dict__ == other.__dict__

    def __getitem__(self, name):
        if name in self.__dict__:
            return self.__dict__[name]

        raise AttributeError("attribute: '{}' not found".format(name))

    def __setitem__(self, name, value):
        self.__dict__[name] = value

    def __repr__(self):
        items = ['{}={!r}'.format(k, v) for k, v in self.__dict__.items()]
        items = ', '.join(items)
        items = items.replace("'", '"')
        items = '{' + items + '}'

        return items

