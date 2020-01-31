
""" compact_ordereddict
starting at python 3.6, the built-in dict is insertion-ordered AND compact,
using about half the memory of OrderedDict
(Thank you Raymond Hettinger!)
"""
import sys
from collections import OrderedDict
from collections import defaultdict
from collections import Iterable

if sys.version_info < (3, 6):
    compact_ordereddict = OrderedDict
else:
    compact_ordereddict = dict


def modify_iteration_depth(v, depth=0):
    """
    eg:
        'a'           = modify_iteration_depth([['a']], depth=0)
        [2, 2, 2]     = modify_iteration_depth([[2, 2, 2]], depth=0)
        [[[1, 1, 1]]] = modify_iteration_depth([1, 1, 1], depth=3)
    """
    if is_exhaustable(v):
        raise TypeError('cannot mofify iteration depth of an exhaustable iterator')

    nd = iteration_depth(v, recurse=False)

    if nd > depth:
        for _ in range(nd - depth):
            if is_subscriptable(v) and len(v) == 1: v = v[0]
    elif nd < depth:
        for _ in range(depth - nd):                 v = [v]

    return v


def iterator_to_list(v, recurse=False):
    if not is_iterable(v):
        return v

    if is_vengeance_class(v):
        v = list(v.rows())
    elif not isinstance(v, (list, tuple)):
        v = list(v)

    if recurse:
        for i in range(len(v)):
            v[i] = iterator_to_list(v[i], recurse=True)

    return v


def iteration_depth(v, recurse=False):
    """
    eg:
        0 = iteration_depth('abc')
        1 = iteration_depth(['abc'])
        1 = iteration_depth([])
        2 = iteration_depth([[2], [2]])

    eg recurse = True:
        5 = iteration_depth([[2, 2, [3, 3, 3, [4, [5, 5, 5, 5], 4]]]], True)
    eg recurse = False:
        (only evaluates the depth of first elements)
        2 = iteration_depth([[2, 2, [3, 3, 3, [4, [5, 5, 5, 5], 4]]]], False)
    """
    if is_exhaustable(v):
        raise TypeError('cannot evaluate iteration depth of an exhaustable iterator')

    if not is_iterable(v):
        return 0

    if len(v) == 0:
        return 1

    if isinstance(v, dict):
        v = list(v.values())

    if recurse:
        return 1 + max(iteration_depth(_v_, recurse) for _v_ in v)

    try:
        return 1 + iteration_depth(v[0], recurse)
    except TypeError:
        return 1


def divide_sequence(sequence, divisions):
    """
    eg:
        [['a', 'a', 'a', 'a', 'a'],
         ['a', 'a', 'a', 'a', 'a']] = divide_sequence(['a'] * 10, 2)
    """
    num_items = len(sequence)
    if divisions > num_items:
        raise AssertionError('too many divisions')

    stride  = max(1, num_items // divisions)
    strides = [stride for _ in range(divisions)]
    undershoot = num_items - (stride * divisions)

    i = 0
    while undershoot > 0:
        strides[i] += 1
        undershoot -= 1
        i += 1

    i_1 = 0
    for stride in strides:
        i_2 = i_1 + stride
        yield sequence[i_1:i_2]
        i_1 = i_2


def is_iterable(v):
    """
    (strings are not considered to be iterable)

    eg:
        False = is_iterable('mike')
        True  = is_iterable(['m', 'i' 'k' 'e'])
    """
    is_iter   = isinstance(v, Iterable)
    is_string = isinstance(v, str)

    return is_iter and (not is_string)


def is_subscriptable(v):
    if isinstance(v, (list, tuple)):
        return True

    try:
        # noinspection PyStatementEffect
        v[0]
        return True
    except (IndexError, TypeError):
        return False


def is_exhaustable(v):
    return hasattr(v, '__next__')


def is_vengeance_class(o):
    """ all util functions should be independent from any other imports to avoid
    circular dependencies. Otherwise, isintance(o, (flux_cls, excel_levity_cls))
    would be sufficient
    """
    bases = set(base_class_names(o))
    return ('flux_cls' in bases) or ('excel_levity_cls' in bases)


def is_flux_row_class(o):
    bases = set(base_class_names(o))
    return 'flux_row_cls' in bases


def base_class_names(o):
    return [b.__name__ for b in o.__class__.mro()]


def transpose(m):
    if iteration_depth(m) == 1:
        t = [[row] for row in m]
    else:
        t = [list(row) for row in zip(*m)]

    return t


def map_numeric_indices(sequence, start=0):
    """ :return {value: index} for all items in sequence

    values are modified before they are added as keys:
        non-unique keys are coerced to string and appended with '_{num}'
        suffix to ensure that indices are incremented correctly

    eg
        {'a':   0,
         'b':   1,
         'c':   2,
         'b_2': 3} = map_numeric_indices(['a', 'b', 'c', 'b'])
    """
    indices   = OrderedDict()
    nonunique = defaultdict(int)

    for i, v in enumerate(sequence, start):
        v_s = str(v)
        if v in nonunique:
            v_s = '{}_{}'.format(v, nonunique[v] + 1)

        indices[v_s] = i
        nonunique[v] += 1

    return indices


def ordered_unique(sequence):
    d = OrderedDict((k, None) for k in sequence)
    return list(d.keys())


def invert_mapping(d):
    """
    return new mapping of
    {value: key}
        from
    {key: value}

    eg:
        {'a': [-1, -1, -1]
         'b': 2
         'c': 3
         'd': 3}
                to
        {-1: ['a', 'a', 'a']
         2:  b                      # single items not stored as list
         3:  ['c', 'd']}
    """
    if not isinstance(d, dict):
        raise TypeError('mapping must be a dictionary')

    inverted = OrderedDefaultDict(list)

    for k, v in d.items():
        _k_, _v_ = v, k
        for ki in modify_iteration_depth(_k_, 1):
            inverted[ki].append(_v_)

    inverted = inverted.compact_ordereddict()
    for k, v in inverted.items():
        inverted[k] = modify_iteration_depth(v, 0)

    return inverted


class OrderedDefaultDict(compact_ordereddict):
    def __init__(self, default_factory=None,
                       items=None):

        self.default_factory = default_factory

        if (default_factory is list) and items:
            self.__append_items(items)
        else:
            super().__init__(items)

    def __append_items(self, items):
        """ append all (key, value) pairs if default_factory is list """
        for item in items:
            try:
                if len(item) != 2:
                    raise ValueError('items expected to be (key, value) pairs')
            except TypeError as e:
                raise TypeError('items expected to be (key, value) pairs') from e

            k, v = item
            self[k].append(v)

    def __getitem__(self, key):
        try:
            return super().__getitem__(key)
        except KeyError:
            return self.__missing__(key)

    def __missing__(self, key):
        if self.default_factory is None:
            raise KeyError(key)

        self[key] = value = self.default_factory()

        return value

    def defaultdict(self):
        return defaultdict(self.default_factory, self.items())

    def compact_ordereddict(self):
        super_cls = compact_ordereddict     # super() not working?
        return super_cls(self.items())



