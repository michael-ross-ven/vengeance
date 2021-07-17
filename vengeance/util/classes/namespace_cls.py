
from ... conditional import ordereddict


class namespace_cls:
    """
    similar to types.SimpleNamespace
    """
    def __init__(self, **kwargs):
        self.__dict__ = ordereddict(kwargs)

    def __iter__(self):
        return ((k, v) for k, v in self.__dict__.items())

    def __eq__(self, other):
        if (not hasattr(self, '__dict__')) or (not hasattr(other, '__dict__')):
            return NotImplemented

        return self.__dict__ == other.__dict__

    def __repr__(self):
        items = ('{}={!r}'.format(k, v) for k, v in self.__dict__.items())
        items = ', '.join(items)

        return '{{{}}}'.format(items)

