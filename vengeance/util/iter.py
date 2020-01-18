
from collections import OrderedDict
from collections import defaultdict
from collections import Iterable


def modify_iteration_depth(v, depth=0):
    """
    eg:
        'a'           = modify_iteration_depth([['a']], depth=0)
        [2, 2, 2]     = modify_iteration_depth([[2, 2, 2]], depth=0)
        [[[1, 1, 1]]] = modify_iteration_depth([1, 1, 1], depth=3)
    """
    # v  = iterator_to_list(v, recurse=False)
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
    except IndexError:
        return True
    except TypeError:
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


def index_sequence(sequence, start=0):
    """ :return {value: index} for all items in sequence

    values are modified before they are added as keys:
        all values coerced to string
        non-unique keys are appended with '_n' suffix
    """
    indices   = OrderedDict()
    nonunique = defaultdict(int)

    for i, v in enumerate(sequence, start):
        _v_ = str(v)
        if _v_ == '':
            _v_ = 'None'

        if v in nonunique:
            _v_ = '{}_{}'.format(_v_, nonunique[v]+1)

        indices[_v_] = i
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
         2:  b                      # single items not in list
         3:  ['c', 'd']}
    """
    if not isinstance(d, dict):
        raise TypeError('value must be a dictionary')

    inverted = OrderedDefaultDict(list)
    for k, v in d.items():
        _k_, _v_ = v, k

        for _k_ in modify_iteration_depth(v, 1):
            inverted[_k_].append(_v_)

    inverted = OrderedDict(inverted)
    for k, v in inverted.items():
        if len(v) == 1:
            inverted[k] = v[0]

    return inverted


class OrderedDefaultDict(OrderedDict):
    def __init__(self, default_factory=None,
                       *args,
                       **kwargs):

        if default_factory and (not callable(default_factory)):
            raise TypeError('first argument must be callable')

        self.default_factory = default_factory

        if args and (self.default_factory is list):
            self.__append_values(args[0])
        else:
            OrderedDict.__init__(self, *args, **kwargs)

    def __append_values(self, sequence):
        """ append all values as list if constructed default_factory is list """

        if isinstance(sequence, dict):
            sequence = OrderedDict(sequence.items()).items()
        elif not isinstance(sequence, (list, tuple)):
            raise ValueError

        for item in sequence:
            if len(item) == 2:
                self[item[0]].append(item[1])
            elif len(item) < 2:
                raise ValueError('need more than 1 value to unpack')
            elif len(item) > 2:
                raise ValueError('too many values to unpack (expected 2)')

    def __getitem__(self, key):
        try:
            return OrderedDict.__getitem__(self, key)
        except KeyError:
            return self.__missing__(key)

    def __missing__(self, key):
        if self.default_factory is None:
            raise KeyError(key)

        self[key] = value = self.default_factory()

        return value

    def defaultdict(self):
        return defaultdict(self.default_factory, self.items())

    def ordereddict(self):
        return OrderedDict(self)



