
import copy

from collections import OrderedDict
from collections import defaultdict
from collections import Iterable
from types import GeneratorType


def reduce_extra_dimen(v, minimum=0):
    """ removes items from iterable containers if they only have a single item """
    nd = num_dimen(v)

    i = 0 + minimum
    while i < nd:
        if is_subscriptable(v) and len(v) == 1:
            v = v[0]

        i += 1

    return v


def force_two_dimen(v):
    v  = generator_to_list(v)
    nd = num_dimen(v)

    if nd > 2:
        raise ValueError('can not reduce from {} dimensions'.format(nd))

    for _ in range(2 - num_dimen(v)):
        v = [generator_to_list(v)]

    return v


# def force_two_dimen(v):
#     """
#     should one dimensional list be transposed?
#     or simply wrapped in outer list?
#     """
#     v  = generator_to_list(v)
#     nd = num_dimen(v)
#
#     if nd > 2:
#         raise ValueError('can not reduce to 2 dimensions from {} dimensions'.format(nd))
#
#     if nd == 0:
#         v = [[v]]
#     elif nd == 1:
#         v = transpose(v)
#
#     return v


def num_dimen(v):
    """ determine iteration-depth (number of dimensions)
    eg:
        0 = num_dimen('a')
        1 = num_dimen(['a'])
        1 = num_dimen([])
        2 = num_dimen(['a'], ['b']])
        2 = num_dimen([[]])
    """
    if not is_iterable(v):
        return 0

    if not is_subscriptable(v):
        return 1

    if len(v) == 0:
        return 1

    return 1 + num_dimen(v[0])


def is_iterable(v):
    """ if value is not a string, determine if it can be iterated
    eg:
        False = is_iterable('mike')
        True  = is_iterable(['m', 'i' 'k' 'e'])
    """
    is_iter = isinstance(v, Iterable)
    is_str  = isinstance(v, str)

    return is_iter and not is_str


def is_subscriptable(v):
    return isinstance(v, (list, tuple))


def generator_to_list(v):
    if is_vengeance_class(v):
        v = v.rows()

    if isinstance(v, GeneratorType):
        v = list(v)

    return v


def is_vengeance_class(o):
    bases = {b.__name__ for b in o.__class__.mro()}
    if 'flux_cls' in bases or 'excel_levity_cls' in bases:
        return True

    return False


def transpose(m):
    m = generator_to_list(m)

    if num_dimen(m) == 1:
        num_r = 1
        num_c = len(m)
        t = [[m[r] for _ in range(num_r)]
                   for r in range(num_c)]
    else:
        num_r = len(m)
        num_c = len(m[0])
        t = [[m[c][r] for c in range(num_r)]
                      for r in range(num_c)]

    return t


def append_matrices(direction, *matrices, has_header=True):
    """
    eg direction:
        'vertical',   'rows'
        'horizontal', 'columns'
    """
    # append vertically
    if direction.startswith('v') or direction.startswith('row'):
        return append_rows(*matrices, has_header=has_header)

    # append horizontally
    if direction.startswith('h') or direction.startswith('col'):
        return append_columns(*matrices)

    raise ValueError("invalid direction: '{}'".format(direction))


def append_rows(*matrices, has_header=True):

    def append(m_1, m_2):
        m_1 = force_two_dimen(m_1)
        m_2 = force_two_dimen(m_2)

        if len(m_1[0]) != len(m_2[0]):
            raise IndexError('vertical append requires matrices to have equal number of columns')

        # if either matrix is empty, return the other
        if is_empty(m_1):
            return m_2

        if is_empty(m_2):
            return m_1

        m_a = copy.copy(m_1)
        if has_header:
            m_a.extend(m_2[1:])
        else:
            m_a.extend(m_2)

        return m_a

    m_f, matrices = matrices[0], matrices[1:]
    for m in matrices:
        m_f = append(m_f, m)

    return m_f


def append_columns(*matrices):

    def append(m_1, m_2):
        m_1 = force_two_dimen(m_1)
        m_2 = force_two_dimen(m_2)

        if len(m_1) != len(m_2):
            raise IndexError('horizontal append requires matrices to have equal number of rows')

        # if either matrix is empty, return the other
        if is_empty(m_1):
            return m_2

        if is_empty(m_2):
            return m_1

        m_a = []
        for row_1, row_2 in zip(m_1, m_2):
            m_a.append(row_1 + row_2)

        return m_a

    m_f, matrices = matrices[0], matrices[1:]
    for m in matrices:
        m_f = append(m_f, m)

    return m_f


def is_empty(v):
    """ determine if iterable is composed entirely of empty iterables, eg, [] or [[]]
    eg:
        True  = is_empty( [] )
        True  = is_empty( [[]] )
        False = is_empty( [[None]] )
        False = is_empty( [[], [], []] )
    """
    m = force_two_dimen(v)
    num_rows = len(m)
    num_cols = len(m[0])

    return (num_rows == 1) and (num_cols == 0)


def make_iterable(v):
    """
    standardize values from iteration of certain datatypes
    so that the same iteration syntax can be used for multiple datatypes

    eg:
        for v in standard_iter(['abc']):
            b = 'abc'

        for v in standard_iter('abc'):
            v = 'abc'

        for v in standard_iter({'a': 0, 'b': 1, 'c': 2}):
            v = (a, 0)
    """
    if isinstance(v, (list, tuple, GeneratorType)):
        return v

    if isinstance(v, dict):
        return v.items()

    if callable(v):
        v = v()

    return [v]


def index_sequence(seq, start=0):
    items = []
    non_unique = defaultdict(int)

    for i, v in enumerate(seq, start):
        if v == '':
            v = 'None'

        if v in non_unique:
            v = '{}({})'.format(v, non_unique[v] + 1)

        items.append((v, i))
        non_unique[v] += 1

    return OrderedDict(items)


def ordered_unique(sequence):
    return list(OrderedDict((k, None) for k in sequence).keys())


def invert_mapping(d, inversion=None):
    """ return new mapping of {value: key} from {key: value}

    eg, from:
        {'a': [-1, -1, -1]
         'b': 2
         'c': 3
         'd': 3}
    to:
        {-1: ['a', 'a', 'a']
         2: b
         3: ['c', 'd']}
    """
    if not isinstance(d, dict):
        raise TypeError('value must be a dictionary')

    inverted = OrderedDefaultDict(list)
    for k, v in d.items():
        _k_, _v_ = v, k

        if inversion:
            _k_ = inversion(_k_)

        for _k_ in make_iterable(v):
            inverted[_k_].append(_v_)

    inverted = OrderedDict(inverted)
    for k, v in inverted.items():
        if len(v) == 1:
            inverted[k] = v[0]

    return inverted


class OrderedDefaultDict(OrderedDict):

    def __init__(self, default_factory=None, *a, **kw):
        if (default_factory is not None) and (not callable(default_factory)):
            raise TypeError('first argument must be callable')

        self.default_factory = default_factory

        if a and self.default_factory is list:
            self.__append_values(a[0])
        else:
            OrderedDict.__init__(self, *a, **kw)

    def __append_values(self, sequence):
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
            d[k] = len(v)

        return d

    def reduce_extra_dimen(self, minimum=0):
        """  """
        for k, v in self.items():
            self[k] = reduce_extra_dimen(v, minimum)

            # if isinstance(v, list) and len(v) == 1:
            #     self[k] = v[0]

