
from ... conditional import ordereddict


class namespace_cls:
    """
    similar to types.SimpleNamespace
    """
    def __init__(self, kwargs):
        if not isinstance(kwargs, ordereddict):
            kwargs = ordereddict(kwargs)

        self.__dict__ = kwargs

    def astuple(self):
        return tuple(self.__dict__.values())

    def __iter__(self):
        return (v for v in self.__dict__.values())

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

    def __len__(self):
        return len(self.__dict__)

    def __repr__(self):
        items = ['{}={!r}'.format(k, v) for k, v in self.__dict__.items()]
        items = ', '.join(items)
        items = items.replace("'", '"')
        items = '{' + items + '}'

        return items

