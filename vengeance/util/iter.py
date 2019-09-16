
from math import ceil

from collections import OrderedDict
from collections import defaultdict
from collections import Iterable


def modify_iteration_depth(v, depth=0):
    """
    eg:
        'a'               = modify_iteration_depth([['a']], depth=0)
        ['a', 'b', 'c']   = modify_iteration_depth([['a', 'b', 'c']], depth=0)
        [['a']]           = modify_iteration_depth('a', depth=2)
        [['a', 'b', 'c']] = modify_iteration_depth(['a', 'b', 'c'], depth=2)

    (but only evaluates depth of first element of iterable)
    eg:
        ['a', [['b']], [['c']]] = modify_iteration_depth(['a', [['b']], [['c']]], depth=0)
    """
    v  = iterator_to_list(v)
    nd = iteration_depth(v)

    # remove unneccesary nesting
    if nd > depth:
        for _ in range(nd - depth):
            if _is_subscriptable(v) and len(v) == 1:
                v = v[0]

    # apply additional nesting
    elif nd < depth:
        for _ in range(depth - nd):
            v = [v]

    return v


def iterator_to_list(v, recurse=False):
    if not _is_iterable(v):
        return v

    if is_vengeance_class(v):
        v = list(v.rows())
    elif not isinstance(v, (list, tuple)):
        v = list(v)

    if recurse:
        for i, _v_ in enumerate(v):
            v[i] = iterator_to_list(_v_, recurse=True)

    return v


def iteration_depth(v):
    """ determine number of nested iteration levels (number of dimensions)

    eg:
        0 = iteration_depth('abc')
        1 = iteration_depth(['abc'])
        1 = iteration_depth([])
        2 = iteration_depth([['abc'], ['bcd'] ])
        2 = iteration_depth([[]])

    (only evaluates the first element if iteration_depth > 1)
    eg:
        2 = iteration_depth([['abc'], 1, 2])
    """
    if _is_exhaustable_iterator(v):
        raise TypeError('cannot evaluate iteration depth of an exhaustable iterator')

    if isinstance(v, str):
        return 0

    if not isinstance(v, Iterable):
        return 0

    if not v:
        return 1

    if not isinstance(v, (list, tuple)):
        v = list(v)

    try:
        _v_ = v[0]
    except TypeError:
        return 1

    return 1 + iteration_depth(_v_)


def stride_sequence(sequence, stride_len):
    sequence = iterator_to_list(sequence)

    for i_1 in range(0, len(sequence), stride_len):
        i_2 = i_1 + stride_len
        yield sequence[i_1:i_2]


def divide_sequence(sequence, num_divisions):
    sequence = iterator_to_list(sequence)

    num_items  = len(sequence)
    stride_len = max(1, ceil(num_items / num_divisions))

    for i_1 in range(0, num_items, stride_len):
        i_2 = i_1 + stride_len
        yield sequence[i_1:i_2]


def is_vengeance_class(o):
    bases = set(base_class_names(o))
    if 'flux_cls' in bases or 'excel_levity_cls' in bases:
        return True

    return False


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


def append_matrices(direction, *matrices, has_header=True):
    d = direction

    if d.startswith('v') or d.startswith('row'):
        return append_vertical(*matrices, has_header=has_header)

    if d.startswith('h') or d.startswith('col'):
        return append_horizontal(*matrices)

    raise ValueError("invalid direction: '{}'".format(direction))


def append_vertical(*matrices, has_header=True):

    def append(m_1, m_2):
        m_1 = iterator_to_list(m_1)
        m_2 = iterator_to_list(m_2)

        if len(m_1[0]) != len(m_2[0]):
            raise IndexError('vertical append requires matrices to have equal number of columns')

        if is_empty(m_1):
            return m_2

        if is_empty(m_2):
            return m_1

        if has_header:
            m_2 = m_2[1:]

        return m_1 + m_2

    m_final, matrices = matrices[0], matrices[1:]
    for m in matrices:
        m_final = append(m_final, m)

    return m_final


def append_horizontal(*matrices):
    """
    this is god-awfully slow

    add all columns together in single iteration
    zip(*matrices)?
    but must assert all equal num columns
    """

    def append(m_1, m_2):
        m_1 = iterator_to_list(m_1)
        m_2 = iterator_to_list(m_2)

        if len(m_1) != len(m_2):
            raise IndexError('horizontal append requires matrices to have equal number of rows')

        if is_empty(m_1):
            return m_2

        if is_empty(m_2):
            return m_1

        return [row_1 + row_2 for row_1, row_2 in zip(m_1, m_2)]

    m_final, matrices = matrices[0], matrices[1:]
    for m in matrices:
        m_final = append(m_final, m)

    return m_final


def is_empty(v):
    """ determine if iterable is composed entirely of empty iterables, eg, [] or [[]]
    eg:
        True  = is_empty( [] )
        True  = is_empty( [[]] )
        False = is_empty( [[None]] )
        False = is_empty( [[], [], []] )
    """
    m = iterator_to_list(v)
    num_rows = len(m)
    num_cols = len(m[0])

    return (num_rows == 1) and (num_cols == 0)


def index_sequence(sequence, start=0):
    indices   = OrderedDict()
    nonunique = defaultdict(int)

    for i, v in enumerate(sequence, start):
        if v in {'', None}:
            v = '_None_'

        if v in nonunique:
            _v_ = '{} ({})'.format(v, nonunique[v] + 1)
        else:
            _v_ = str(v)

        indices[_v_]  = i
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


def _is_iterable(v):
    """ determine if value is an iteraterable data structure
    (strings are not considered to be iterable data structures in this function)

    eg:
        False = is_iterable('mike')
        True  = is_iterable(['m', 'i' 'k' 'e'])
    """
    is_iter   = isinstance(v, Iterable)
    is_string = isinstance(v, str)

    return is_iter and not is_string


def _is_subscriptable(v):
    return isinstance(v, (list, tuple))


def _is_exhaustable_iterator(v):
    return hasattr(v, '__next__')


class OrderedDefaultDict(OrderedDict):

    def __init__(self, default_factory=None, *args, **kwargs):

        if default_factory and (not callable(default_factory)):
            raise TypeError('first argument must be callable')

        self.default_factory = default_factory

        if args and (self.default_factory is list):
            self.__append_values(args[0])
        else:
            OrderedDict.__init__(self, *args, **kwargs)

    def __append_values(self, sequence):
        """
        append all values as list if constructed default_factory is list
        """

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

    def count_values(self):
        d = OrderedDict()

        for k, v in self.items():
            if _is_iterable(v):
                d[k] = len(v)
            else:
                d[k] = 1

        return d

    def modify_iteration_depth(self, depth=0):
        for k, v in self.items():
            self[k] = modify_iteration_depth(v, depth)


