
from collections import Iterable
from collections import ItemsView
from collections import KeysView
from collections import ValuesView

from collections import defaultdict
from collections import namedtuple
from ..conditional import ordereddict


class IterationDepthError(TypeError):
    pass


class ColumnNameError(ValueError):
    pass


# class namespace(types.SimpleNamespace)
class namespace:
    def __init__(self, **kwargs):
        self.__dict__.update(**kwargs)

    def __iter__(self):
        return ((k, v) for k, v in self.__dict__.items())

    def __eq__(self, other):
        if isinstance(self, namespace) and isinstance(other, namespace):
            return self.__dict__ == other.__dict__
        return NotImplemented

    def __repr__(self):
        items = ('{}={!r}'.format(k, v) for k, v in self.__dict__.items())
        return '{}({})'.format(type(self).__name__, ', '.join(items))


def iteration_depth(values, first_element_only=True):
    """
    (this function is heavily utilized to correctly un-nest
     arguments in variable arity flux_cls methods, so make sure
     you dont fuck anything up if you change anything here !!)

    eg:
        0 = iteration_depth('abc')
        1 = iteration_depth(['abc'])
        2 = iteration_depth([[2], [2]])

        items = [1, [2, 2, [3, 3, 3, [4, [5, 5, 5, 5], 4]]]]
        1 = iteration_depth(items, first_element_only=True)
        5 = iteration_depth(items, first_element_only=False)
    """
    if is_exhaustable(values):
        raise TypeError('cannot evaluate an exhaustable iterator')

    if not is_collection(values):
        return 0
    elif isinstance(values, dict):
        values = tuple(values.values())
    elif isinstance(values, set):
        values = tuple(values)

    if len(values) == 0:
        return 1
    elif first_element_only:
        return 1 + iteration_depth(values[0], first_element_only)
    else:
        depths = [iteration_depth(_v_, first_element_only) for _v_ in values]
        return 1 + max(depths)


def modify_iteration_depth(values,
                           depth=None,
                           depth_offset=None,
                           first_element_only=True):
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
    if not first_element_only:
        raise NotImplementedError
    if depth is None and depth_offset is None:
        raise ValueError('conflicting values for depth and depth_offset')
    elif isinstance(depth, int) and isinstance(depth_offset, int):
        raise ValueError('conflicting values for depth and depth_offset')

    if depth_offset is None:
        value_depth  = iteration_depth(values, first_element_only=True)
        depth_offset = depth - value_depth

    if depth_offset < 0:
        for _ in range(abs(depth_offset)):
            if is_descendable(values):
                values = values[0]
            else:
                break

    elif depth_offset > 0:
        for _ in range(depth_offset):
            values = [values]

    return values


def standardize_variable_arity_arguments(values,
                                         depth=None,
                                         depth_offset=None):

    if depth is None and depth_offset is None:
        return values

    # region {closure functions}
    def descend_iterator(v):
        if is_descendable(v) and is_exhaustable(v[0]):
            return iterator_to_collection(v[0])
        else:
            return iterator_to_collection(v)
    # endregion

    values = descend_iterator(values)
    values = modify_iteration_depth(values, depth, depth_offset,
                                    first_element_only=True)

    return values


def are_indices_contiguous(indices):
    if len(indices) == 1:
        return False

    for i_2, i_1 in zip(indices[1:], indices):
        if i_2 - i_1 != 1:
            return False

    return True


def is_collection(o):
    """ determine if value is an iterable object or data structure
    function used mainly to distinguish data structures from other iterables

    eg:
        False = is_collection('mike')
        True  = is_collection(['m', 'i' 'k' 'e'])
    """
    if isinstance(o, (str, bytes, range)):
        return False

    return isinstance(o, Iterable)


# noinspection PyStatementEffect,PyBroadException
def is_subscriptable(o):
    """
    from typing import Sequence
    isinstance(o, Sequence)
    """
    try:
        o[0]
        return True
    except Exception:
        return False


def is_exhaustable(o):
    return (hasattr(o, '__next__') or
            isinstance(o, range))


def is_dictview(o):
    return (isinstance(o, KeysView) or
            isinstance(o, ValuesView) or
            isinstance(o, ItemsView))


def is_vengeance_class(o):
    bases = set(base_class_names(o))
    return bool(bases & {'flux_cls',
                         'excel_levity_cls'})


def is_namedtuple_class(o):
    return (isinstance(o, tuple) and
            type(o) is not tuple)


def is_descendable(o):
    return (is_collection(o) and
            is_subscriptable(o) and
            len(o) == 1)


def descend_iteration_depth(o):
    if is_descendable(o):
        return o[0]
    else:
        return o


def iterator_to_collection(o):
    if is_vengeance_class(o):
        return list(o.rows())
    elif is_exhaustable(o):
        return list(o)
    elif is_dictview(o):
        return list(o)
    elif isinstance(o, set):
        return list(o)

    return o


def base_class_names(o):
    return [b.__name__ for b in o.__class__.mro()]


def transpose(m, astype=None):
    if astype not in (None, tuple, list):
        raise TypeError('astype must be in (None, tuple, list)')

    m = iterator_to_collection(m)
    n = iteration_depth(m, first_element_only=True)
    if n == 0:
        raise IterationDepthError('matrix must have at least 1 dimension')

    if astype is None:
        if n == 1:
            astype = type(m)
        else:
            astype = type(m[0])

    if astype is list:
        if n == 1:
            t = ([row] for row in m)
        else:
            t = (list(row) for row in zip(*m))
    else:
        if n == 1:
            t = ((row,) for row in m)
        else:
            t = zip(*m)

    return t


def to_namespaces(o):
    """ recursively convert values to SimpleNamespace """
    # region {closure functions}
    def traverse(k, v):
        if isinstance(v, dict):
            return to_namespaces(v)
        elif hasattr(v, '_asdict'):
            # noinspection PyProtectedMember
            return to_namespaces(v._asdict())
        elif is_collection(v):
            return [traverse(k, _) for _ in v]
        else:
            return v
    # endregion

    if hasattr(o, '_asdict'):
        # noinspection PyProtectedMember
        o = o._asdict()

    if isinstance(o, dict):
        d = {k: traverse(k, v) for k, v in o.items()}
        return namespace(**d)
    else:
        return [traverse(None, v) for v in o]


# noinspection PyArgumentList
def to_namedtuples(o):
    """ recursively convert values to namedtuple """
    # region {closure functions}
    def traverse(v):
        if isinstance(v, dict):
            return to_namedtuples(v)
        elif hasattr(v, '_asdict'):
            # noinspection PyProtectedMember
            return to_namedtuples(v._asdict())
        elif is_collection(v):
            return [traverse(_) for _ in v]
        else:
            return v
    # endregion

    if hasattr(o, '_asdict'):
        # noinspection PyProtectedMember
        o = o._asdict()

    if isinstance(o, dict):
        nt = namedtuple('nt', o.keys())
        return nt(*[traverse(v) for v in o.values()])
    else:
        return [traverse(v) for v in o]


def inverted_enumerate(sequence, start=0):
    """ :return {unique_key: i: int} for all items in sequence

    values are modified before they are added as keys:
        * values coerced to string (if not bytes)
        * non-unique keys are appended with '_dup_{num}' suffix

    eg
        {'a':       0,
         'b':       1,
         'c':       2,
         'b_dup_2': 3,
         'b_dup_3': 4} = inverted_enumerate(['a', 'b', 'c', 'b', 'b'])
    """
    values_to_indices = ordereddict()
    duplicates = defaultdict(lambda: 0)

    for i, v in enumerate(sequence, start):
        if isinstance(v, (bytes, str)):
            _v_ = v
        else:
            _v_ = str(v)

        is_duplicate = (_v_ in duplicates)

        duplicates[_v_] += 1

        if is_duplicate:
            n_d = duplicates[_v_]

            if isinstance(_v_, bytes):
                _v_ = '{}_dup_{num}'.format(_v_.decode(), num=n_d)
                _v_ = _v_.encode()
            else:
                _v_ = '{}_dup_{num}'.format(_v_, num=n_d)

        values_to_indices[_v_] = i

    return values_to_indices


def is_header_row(values, headers):
    """ determine if underlying values match headers.keys

    checking headers.keys() == values will not always work, since inverted_enumerate()
    was used to modify names into more suitable header keys
    """
    if not headers:
        return False

    value_names  = inverted_enumerate(values).keys()
    header_names = set(headers)

    return value_names == header_names


