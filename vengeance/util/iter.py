
from collections import Iterable
from collections import defaultdict

from ..conditional import ordereddict


class IterationDepthError(TypeError):
    pass


def modify_iteration_depth(v, depth=0):
    """
    (this function is heavily utilized to correctly un-nest
     arguments in invariable arity flux_cls methods, so make sure
     you dont fuck anything up if you change anything here !!)

    eg:
        'a'              = modify_iteration_depth([[['a']]], depth=0)
        ['a', 'b']       = modify_iteration_depth([[['a', 'b']]], depth=0)
        [['a']]          = modify_iteration_depth('a', depth=2)
        [[[['a', 'b']]]] = modify_iteration_depth(['a', 'b'], depth=4)

        required behaviors:
            must not reduce depth of any dictionary keys or values
                {'a': None} = modify_iteration_depth([{'a': None}], depth=0)

        undecided behaviors:
            how to deal with mixed iteration depths?
                [['ab', ['cd']]]
                should this return ['ab', ['cd']] or ['ab', 'cd']?

            # has_multiple_depths = set(iteration_depth(_v_, first_element_only=False) for _v_ in v)
    """
    # region {closure functions}
    def is_descendable(value):
        if not is_collection(value):
            return False
        if isinstance(value, dict):
            return False
        if any([is_exhaustable(_v_) for _v_ in value]):
            raise TypeError('cannot modify depth of an exhaustable iterator')

        return (is_subscriptable(value) and
                len(value) == 1)
    # endregion

    nd = iteration_depth(v, first_element_only=True)

    if nd > depth:
        for _ in range(nd - depth):
            if is_descendable(v):
                v = v[0]
            else:
                break
    elif nd < depth:
        for _ in range(depth - nd):
            v = [v]

    return v


def iteration_depth(v, first_element_only=True):
    """
    (this function is heavily utilized to correctly un-nest
     arguments in invariable arity flux_cls methods, so make sure
     you dont fuck anything up if you change anything here !!)

    eg:
        0 = iteration_depth('abc')
        1 = iteration_depth(['abc'])
        2 = iteration_depth([[2], [2]])

    eg: items = [1, [2, 2, [3, 3, 3, [4, [5, 5, 5, 5], 4]]]]
        2 = iteration_depth(items, first_element_only=True)
        5 = iteration_depth(items, first_element_only=False)
    """
    if is_exhaustable(v):
        raise TypeError('cannot evaluate iteration depth of an exhaustable value: {}'.format(v))
    if not is_collection(v):
        return 0
    if len(v) == 0:
        return 1

    if isinstance(v, dict):
        v = tuple(v.values())

    if first_element_only:
        return 1 + iteration_depth(v[0], first_element_only)
    else:
        return 1 + max(iteration_depth(_v_, first_element_only) for _v_ in v)


def iterator_to_list(v):
    if is_vengeance_class(v):
        return list(v.rows())

    if is_exhaustable(v):
        return list(v)

    if isinstance(v, range):
        return list(v)

    return v


def is_collection(v):
    """ determine if value is an iterable object or data structure
    function used mainly to distinguish data structures from other iterables

    eg:
        False = is_collection('mike')
        True  = is_collection(['m', 'i' 'k' 'e'])
    """
    if isinstance(v, (str, bytes, range)):
        return False

    return isinstance(v, Iterable)


# noinspection PyStatementEffect
def is_subscriptable(v):
    try:
        v[0]
        return True
    except Exception:
        return False


def is_exhaustable(v):
    return hasattr(v, '__next__')


def is_vengeance_class(v):
    bases = set(base_class_names(v))

    vengeance_bases = bases & {'flux_cls',
                               'excel_levity_cls'}
    return bool(vengeance_bases)


def base_class_names(o):
    return [b.__name__ for b in o.__class__.mro()]


def transpose(m, astype=tuple):
    if astype is tuple:
        return transpose_to_tuples(m)
    if astype is list:
        return transpose_to_lists(m)

    raise TypeError('astype parameter must be either tuple or list')


def transpose_to_tuples(m):
    if iteration_depth(m) == 1:
        return ((v,) for v in m)
    else:
        return zip(*m)


def transpose_to_lists(m):
    if iteration_depth(m) == 1:
        return ([v] for v in m)
    else:
        return (list(v) for v in zip(*m))


def map_to_numeric_indices(sequence, start=0):
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
    indices   = ordereddict()
    nonunique = defaultdict(int)

    for i, v in enumerate(sequence, start):
        if isinstance(v, bytes):
            v_s = v.decode('utf-8')
        else:
            v_s = str(v)

        if v_s in nonunique:
            v_s = '{}_{}'.format(v, nonunique[v_s] + 1)

        indices[v_s] = i
        nonunique[v_s] += 1

    return indices


class OrderedDefaultDict(ordereddict):

    def __init__(self, default):
        self.default_factory = default
        super().__init__()

    def append_items(self, items):
        """ all items that map to the same key are appended to a list """
        if self.default_factory is not list:
            raise TypeError('self.default_factory function must be list')

        if isinstance(items, dict):
            items = list(items.items())

        for item in items:
            try:
                k, v = item
            except Exception as e:
                raise IndexError('items must be (key, value) pairs') from e

            self[k].append(v)

        return self

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
        return ordereddict(self.items())
