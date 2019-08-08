
from math import ceil

from types import GeneratorType

from collections import OrderedDict
from collections import defaultdict
from collections import Iterable


def modify_iteration_depth(v, depth=0):
    """
    eg:
        'a' = modify_iteration_depth([['a']], depth=0)
        ['a', 'b', 'c'] = modify_iteration_depth([['a', 'b', 'c']], depth=0)

        [['a']] = modify_iteration_depth('a', depth=2)
        [['a', 'b', 'c']] = modify_iteration_depth(['a', 'b', 'c'], depth=2)
    """
    v  = generator_to_list(v)
    nd = iteration_depth(v)

    if nd > depth:
        # remove unneccesary nesting
        for _ in range(nd - depth):
            if is_subscriptable(v) and len(v) == 1:
                v = list(v)
                v = v[0]

    elif nd < depth:
        # add additional nesting
        for _ in range(depth - nd):
            v = [v]

    return v


def assert_iteration_depth(v, depth):
    """ make sure values have certain number of iterable levels """
    if iteration_depth(v) != depth:
        raise IndexError('value must have an iteration depth of {}'.format(depth))


def iteration_depth(v):
    """ determine number of nested iteration levels (number of dimensions)

    eg:
        0 = iteration_depth('abc')
        1 = iteration_depth(['abc'])
        1 = iteration_depth([])
        2 = iteration_depth([['abc'], ['bcd']])
        2 = iteration_depth([[]])

    only the first value of each iteration level is recursed
        2 = iteration_depth([[], [[[['abc'], ['bcd']]]])
    """
    if isinstance(v, GeneratorType):
        raise TypeError('cannot evaluate iteration depth of a generator')

    if not is_iterable(v):
        return 0

    if len(v) == 0:
        return 1

    if not is_subscriptable(v):
        return 1 + iteration_depth(next(iter(v)))

    return 1 + iteration_depth(v[0])


def depth_one(v):
    """ add at least one iteration depth
    iteration of string characters dont count

    eg:
        for v in depth_one('abc'):
            v = 'abc'

        for v in depth_one(['abc']):
            b = 'abc'

        for v in depth_one({'a': 0, 'b': 1, 'c': 2}):
            v = (a, 0)
    """
    if isinstance(v, (list, tuple, GeneratorType)):
        return v

    if isinstance(v, dict):
        return v.items()

    return [v]


def is_iterable(v):
    """ determine if value can be iterated
    iteration of string characters dont count

    eg:
        False = is_iterable('mike')
        True  = is_iterable(['m', 'i' 'k' 'e'])
    """
    is_iter = isinstance(v, Iterable)
    is_str  = isinstance(v, str)

    return is_iter and not is_str


def is_subscriptable(v):
    return isinstance(v, (list, tuple))


def generator_to_list(v, recurse=False):
    if is_vengeance_class(v):
        v = list(v.rows())

    if isinstance(v, GeneratorType):
        v = list(v)

    if recurse:
        for _ in range(1, iteration_depth(v)):
            v = list(v)
            for i, _v_ in enumerate(v):
                v[i] = generator_to_list(_v_)

    return v


def stride_sequence(sequence, stride_len):
    sequence = generator_to_list(sequence)

    for i_1 in range(0, len(sequence), stride_len):
        i_2 = i_1 + stride_len
        yield sequence[i_1:i_2]


def divide_sequence(sequence, num_divisions):
    sequence = generator_to_list(sequence)

    num_items  = len(sequence)
    stride_len = ceil(num_items / num_divisions)
    stride_len = max(stride_len, 1)

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
    if 'flux_row_cls' in bases or 'lev_row_cls' in bases:
        return True

    return False


def base_class_names(o):
    return [b.__name__ for b in o.__class__.mro()]


def transpose(m):
    """ what if original matrix is tuples? """
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
        m_1 = generator_to_list(m_1)
        m_2 = generator_to_list(m_2)

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
        m_1 = generator_to_list(m_1)
        m_2 = generator_to_list(m_2)

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
    m = generator_to_list(v)
    num_rows = len(m)
    num_cols = len(m[0])

    return (num_rows == 1) and (num_cols == 0)


def index_sequence(seq, start=0):
    items = []
    non_unique = defaultdict(int)

    for i, v in enumerate(seq, start):
        if v in {'', None}:
            v = '(blank)'

        v_ = v
        if v in non_unique:
            v = '{} (nonunique_{})'.format(v, non_unique[v] + 1)

        items.append((v, i))
        non_unique[v_] += 1

    return OrderedDict(items)


def ordered_unique(sequence):
    return list(OrderedDict((k, None) for k in sequence).keys())


def invert_mapping(d, inversion=None):
    """ return new mapping of
    {value: key}
    {key: value}

    eg:
        d = {'a': [-1, -1, -1]
             'b': 2
             'c': 3
             'd': 3}

        {-1: ['a', 'a', 'a']
         2: b
         3: ['c', 'd']} = invert_mapping(d)
    """
    if not isinstance(d, dict):
        raise TypeError('value must be a dictionary')

    inverted = OrderedDefaultDict(list)
    for k, v in d.items():
        _k_, _v_ = v, k

        if inversion:
            _k_ = inversion(_k_)

        for _k_ in depth_one(v):
            inverted[_k_].append(_v_)

    inverted = OrderedDict(inverted)
    for k, v in inverted.items():
        if len(v) == 1:
            inverted[k] = v[0]

    return inverted


class OrderedDefaultDict(OrderedDict):

    def __init__(self, default_factory=None, *a, **kw):
        if (default_factory is not None) and not callable(default_factory):
            raise TypeError('first argument must be callable')

        self.default_factory = default_factory

        if a and self.default_factory is list:
            self.__append_values(a[0])
        else:
            OrderedDict.__init__(self, *a, **kw)

    def __append_values(self, sequence):
        """
        special case when a sequence was submitted to constructor and
        all values should be appended as lists
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
            if is_iterable(v):
                d[k] = len(v)
            else:
                d[k] = 1

        return d

    def modify_iteration_depth(self, minimum=0):
        for k, v in self.items():
            self[k] = modify_iteration_depth(v, minimum)


