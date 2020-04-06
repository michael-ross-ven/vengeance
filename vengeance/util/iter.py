
from collections import Iterable
from collections import defaultdict
from collections.abc import ItemsView

from ..conditional import ordereddict_


def modify_iteration_depth(v, depth=0):
    """
    eg:
        'a'           = modify_iteration_depth([['a']], depth=0)
        [2, 2, 2]     = modify_iteration_depth([[2, 2, 2]], depth=0)
        [[[1, 1, 1]]] = modify_iteration_depth([1, 1, 1], depth=3)
    """
    if is_exhaustable(v):
        raise TypeError('cannot mofify iteration depth of an exhaustable iterator')

    nd = iteration_depth(v, first_element_only=True)

    if nd > depth:
        for _ in range(nd - depth):
            if is_subscriptable(v) and len(v) == 1:
                v = v[0]

    elif nd < depth:
        for _ in range(depth - nd):
            v = [v]

    return v


def iterator_to_list(v):
    if set(base_class_names(v)) & {'flux_cls', 'excel_levity_cls'}:
        return list(v.rows())

    if is_exhaustable(v):
        return list(v)

    return v


def iteration_depth(v, first_element_only=True):
    """
    eg:
        0 = iteration_depth('abc')
        1 = iteration_depth(['abc'])
        1 = iteration_depth([])
        2 = iteration_depth([[2], [2]])

    eg first_element_only:
        items = [[2, 2, [3, 3, 3, [4, [5, 5, 5, 5], 4]]]]
        2 = iteration_depth(items, first_element_only=True)
        5 = iteration_depth(items, first_element_only=False)
    """
    if is_exhaustable(v):
        raise TypeError('cannot evaluate iteration depth of an exhaustable iterator')

    if not is_iterable(v):
        return 0

    if len(v) == 0:
        return 1

    if isinstance(v, dict):
        v = tuple(v.values())

    if first_element_only:
        try:
            _v_ = v[0]
        except TypeError:
            return 1

        return 1 + iteration_depth(_v_, first_element_only)

    else:
        return 1 + max(iteration_depth(_v_, first_element_only) for _v_ in v)


def divide_sequence(sequence, num_divisions):
    """ :return yield n number of divisions from sequence

    eg:
        sequence = ['a'] * 10

        [('a', 'a', 'a', 'a', 'a'),
         ('a', 'a', 'a', 'a', 'a')] = divide_sequence(sequence, 2)

         [('a', 'a', 'a', 'a'),
          ('a', 'a', 'a'),
          ('a', 'a', 'a')]         = divide_sequence(sequence, 3)

    simpler?
        n_div, remain = divmod(len(sequence), n)
        for v in range(n):
            j = v + 1
            i_1 = v * n_div + min(v, remain)
            i_2 = j * n_div + min(j, remain)
            yield sequence[i_1:i_2]
    """

    def adjust_stride_distribution():
        """
        if stride_len is not an exact multiple of number of sequence_len,
        add 1 to items in stride_lens until rounding deficit is covered
        """
        _, redistribute = divmod(sequence_len, num_divisions)
        for i in range(redistribute):
            stride_lens[i] += 1

    is_dict = False
    if isinstance(sequence, dict):
        sequence = tuple(sequence.items())
        is_dict = True
    elif isinstance(sequence, ItemsView):
        sequence = tuple(sequence)
        is_dict = True
    elif not is_subscriptable(sequence):
        sequence = list(sequence)

    sequence_len  = len(sequence)
    num_divisions = min(sequence_len, num_divisions)

    stride_len  = sequence_len // num_divisions
    stride_lens = [stride_len for _ in range(num_divisions)]
    adjust_stride_distribution()

    i_1 = 0
    for stride_len in stride_lens:
        i_2 = i_1 + stride_len

        divided_seq = sequence[i_1:i_2]
        if is_dict:
            divided_seq = dict(divided_seq)
        else:
            divided_seq = tuple(divided_seq)

        yield divided_seq

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
    if isinstance(v, (list, tuple, str)):
        return True

    try:
        # noinspection PyStatementEffect
        v[0]
        return True
    except (IndexError, TypeError):
        return False


def is_exhaustable(v):
    return hasattr(v, '__next__')


def base_class_names(o):
    return [b.__name__ for b in o.__class__.mro()]


def transpose(m):
    if iteration_depth(m) == 1:
        return tuple((v,) for v in m)

    return tuple(zip(*m))


# def transpose(m):
#     outer_values_tuples = isinstance(m, tuple)
#
#     if iteration_depth(m) == 1:
#         if outer_values_tuples:
#             return tuple((v,) for v in m)
#         else:
#             return [[v] for v in m]
#
#     inner_values_tuples = isinstance(m[0], tuple)
#
#     t = zip(*m)
#
#     if outer_values_tuples and inner_values_tuples:
#         return t
#     elif outer_values_tuples and not inner_values_tuples:
#         return tuple(list(row) for row in t)
#     elif not outer_values_tuples and inner_values_tuples:
#         return list(t)
#     else:
#         return [list(row) for row in t]


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
    indices  = ordereddict_()
    nonunique = defaultdict(int)

    for i, v in enumerate(sequence, start):
        if isinstance(v, bytes):
            v_s = v
        else:
            v_s = str(v)

        if v in nonunique:
            v_s = '{}_{}'.format(v, nonunique[v] + 1)

        indices[v_s] = i
        nonunique[v] += 1

    return indices


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

    inverted = inverted.ordereddict()
    for k, v in inverted.items():
        inverted[k] = modify_iteration_depth(v, 0)

    return inverted


class OrderedDefaultDict(ordereddict_):
    def __init__(self, func=None, items=None):

        self.default_factory = func
        if (func is list) and items:
            self.__append_values_to_list(items)
        else:
            super().__init__(items)

    def __append_values_to_list(self, items):
        """ append all (key, value) pairs if default_factory is list """
        if isinstance(items, dict):
            items = items.items()

        for item in items:
            try:
                k, v = item
            except (ValueError, TypeError) as e:
                raise type(e)('items expected to be an iterable of (key, value) pairs')

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

    def ordereddict(self):
        # super_cls = ordereddict_                 # super() not working?
        return ordereddict_(self.items())



