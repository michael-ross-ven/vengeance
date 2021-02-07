
from collections import Iterable
from collections import defaultdict

from ..conditional import ordereddict


class IterationDepthError(TypeError):
    pass


class ColumnNameError(ValueError):
    pass


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
        raise TypeError('cannot evaluate iteration depth of an exhaustable value')
    elif not is_collection(values):
        return 0
    elif len(values) == 0:
        return 1

    if isinstance(values, dict):
        values = tuple(values.values())

    if first_element_only:
        return 1 + iteration_depth(values[0], first_element_only)
    else:
        return 1 + max(iteration_depth(_v_, first_element_only) for _v_ in values)


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
    try:
        o[0]
        return True
    except Exception:
        return False


def is_exhaustable(o):
    return (hasattr(o, '__next__') or
            isinstance(o, range))


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

    return o


def base_class_names(o):
    return [b.__name__ for b in o.__class__.mro()]


def transpose(m, astype=None):
    m = iterator_to_collection(m)
    if astype is None:
        astype = type(m[0])

    if astype is tuple:
        return transpose_as_tuples(m)
    else:
        return transpose_as_lists(m)


def transpose_as_tuples(m):
    m = iterator_to_collection(m)

    if iteration_depth(m, first_element_only=True) == 1:
        return ((v,) for v in m)
    else:
        return zip(*m)


def transpose_as_lists(m):
    m = iterator_to_collection(m)

    if iteration_depth(m, first_element_only=True) == 1:
        return ([v] for v in m)
    else:
        return (list(v) for v in zip(*m))


def map_to_numeric_indices(sequence, start=0):
    """ :return {value: index} for all items in sequence

    values are modified before they are added as keys:
        * values coerced to string (if not bytes)
        * non-unique keys are appended with '_{num}' suffix

    eg
        {'a':   0,
         'b':   1,
         'c':   2,
         'b_2': 3,
         'b_3': 4} = map_numeric_indices(['a', 'b', 'c', 'b', 'b'])
    """
    indices   = ordereddict()
    nonunique = defaultdict(lambda: 1)

    for i, v in enumerate(sequence, start):
        is_bytes = isinstance(v, bytes)

        if is_bytes:
            v_s = v.decode('utf-8')
        else:
            v_s = str(v)

        if v_s in indices:
            nonunique[v_s] += 1
            v_s = '{}_{}'.format(v_s, nonunique[v_s])

        if is_bytes:
            v_s = v_s.encode('utf-8')

        indices[v_s] = i

    return indices


def is_header_row(values, headers):
    """ determine if underlying values match headers.keys

    headers.keys() == values will not always work, since map_to_numeric_indices()
    was used to modify names into more suitable dictionary keys, such as
        * values coerced to string (if not bytes)
        * non-unique keys are appended with '_{num}' suffix
    """
    if not headers:
        return False

    value_names  = map_to_numeric_indices(values).keys()
    header_names = set(headers)

    return value_names == header_names



