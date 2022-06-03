
import re
from collections import namedtuple
from typing import Generator
from typing import Union
from typing import Any
from typing import Dict
from typing import List
from typing import Tuple
from typing import Iterable
from typing import ItemsView
from typing import KeysView
from typing import ValuesView

from ..conditional import ordereddict
from .classes.tree_cls import tree_cls
from .classes.namespace_cls import namespace_cls


vengeance_cls_names = {'flux_cls',
                       'lev_cls',
                       'excel_levity_cls'}


class IterationDepthError(TypeError):
    pass


class ColumnNameError(ValueError):
    pass


def standardize_variable_arity_values(values,
                                      depth=None,
                                      depth_offset=None):
    """
    this function is heavily utilized to correctly un-nest function arguments
    in flux_cls methods

    eg flux_cls:
        def append_columns(self, *names):
            names = standardize_variable_arity_values(names, depth=1)

    # while is_descendable(values):
    #     values = values[0]
    """

    # convert iterators, even if they are nested
    if is_descendable(values) and is_exhaustable(values[0]):
        values = iterator_to_collection(values[0])
    else:
        values = iterator_to_collection(values)

    values = modify_iteration_depth(values, depth, depth_offset,
                                    first_element_only=True)

    return values


def iteration_depth(values, first_element_only=False):
    """
    this function is heavily utilized to correctly un-nest function arguments
    in flux_cls methods

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

    if isinstance(values, dict):
        values = tuple(values.values())

    if not is_collection(values):
        return 0

    if len(values) == 0:
        return 1

    if first_element_only:
        return 1 + iteration_depth(values[0], first_element_only)
    else:
        return 1 + max([iteration_depth(v, first_element_only) for v in values])


def modify_iteration_depth(values,
                           depth=None,
                           depth_offset=None,
                           first_element_only=False):
    """
    this function is heavily utilized to correctly un-nest function arguments
    in flux_cls methods

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

            if is_descendable(values):
                values = values[0]
            else:
                break

            # if first_element_only:
            #     if is_descendable(values): values = values[0]
            #     else:                      break
            # else:
            #     values = list(chain.from_iterable(values))
    """
    if depth is None and depth_offset is None:
        raise ValueError('conflicting values for depth and depth_offset')

    if isinstance(depth, int) and isinstance(depth_offset, int):
        raise ValueError('conflicting values for depth and depth_offset')

    if depth_offset is None:
        value_depth  = iteration_depth(values, first_element_only)
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


def are_indices_contiguous(indices):
    if len(indices) == 1:
        return False

    for i_1, i_2 in zip(indices, indices[1:]):
        if i_2 - i_1 != 1:
            return False

    return True


def is_collection(o):
    """ determine if value is an iterable object or data structure
    function used mainly to distinguish data structures from other
    iterables

    eg:
        False = is_collection('bleh')
        True  = is_collection(['bleh'])

        False = is_collection(range(3))
        True  = is_collection(list(range(3)))
    """
    if isinstance(o, (str, bytes, range, dict, ItemsView)):
        return False
    else:
        return isinstance(o, Iterable)


# noinspection PyStatementEffect,PyBroadException
def is_subscriptable(o):
    try:
        o[0]
        return True
    except:
        return False


def is_exhaustable(o):
    """
    return (hasattr(o, '__next__') or
            isinstance(o, range))
    """
    return hasattr(o, '__next__')


def is_dictview(o):
    return (isinstance(o, KeysView) or
            isinstance(o, ValuesView) or
            isinstance(o, ItemsView))


def is_vengeance_class(o):
    base_cls_names = set(base_class_names(o))

    return bool(base_cls_names & vengeance_cls_names)


def is_descendable(o):
    return (is_collection(o) and
            is_subscriptable(o) and
            len(o) == 1)


def iterator_to_collection(o):
    if is_vengeance_class(o):
        return list(o.values())

    if isinstance(o, (range, set)) or \
       is_exhaustable(o) or \
       is_dictview(o):

        return list(o)

    return o


def base_class_names(o):
    return [b.__name__ for b in o.__class__.mro()]


def transpose(m, astype=None) -> Generator[Union[List, Tuple], None, None]:
    m = iterator_to_collection(m)
    n = iteration_depth(m, first_element_only=True)

    if n == 0:
        raise IterationDepthError('matrix must have at least 1 iterable dimension')

    if astype is None:
        if n == 1: astype = type(m)
        else:      astype = type(m[0])

    if astype is list:
        if n == 1: t = ([row] for row in m)
        else:      t = (list(row) for row in zip(*m))
    else:
        if n == 1: t = ((row,) for row in m)
        else:      t = zip(*m)

    return t


def to_grouped_dict(flat_dict: Dict) -> Dict[Any, Dict]:
    """ re-map keys (tuples) to a nested structure

    eg:
        # "flat" keys
        d = {('a₁', 'b₁', 'c₁', 'd₁'): 'v_1',
             ('a₁', 'b₂', 'c₁', 'd₂'): 'v_2',
             ('a₂', 'b₁', 'c₁', 'd₁'): 'v_4',
             ('a₂', 'b₁', 'c₁', 'd₂'): 'v_3'}

        {'a₁': {'b₁': {'c₁': {'d₁': 'v_1'}},
                'b₂': {'c₁': {'d₂': 'v_2'}}},
         'a₂': {'b₁': {'c₁': {'d₁': 'v_4',
                              'd₂': 'v_3'}}}} = to_grouped_dict(d)
    """
    nested_dict = tree_cls(flat_dict).traverse_nested()

    return nested_dict


def is_header_row(values, headers):
    """ determine if underlying values match headers.keys

    checking headers.keys() == values will not always work, since map_values_to_enum()
    was used to modify names into more suitable header keys,
    like modifying duplicate values to ensure they are unique

    eg:
        True = is_header_row(['a', 'b', 'c'],
                             {'a': 0, 'b': 1, 'c': 2})
        True = is_header_row(['a', 'b', 'b'],
                             {'a': 0, 'b': 1, 'b__2': 2})

    """
    if not headers:
        return False

    value_names  = map_values_to_enum(values).keys()
    header_names = set(headers)

    return value_names == header_names


def map_values_to_enum(sequence, start=0, as_snake_case=False) -> Dict[Union[str, bytes], int]:
    """ :return {unique_key: i: int} for all items in sequence

    values are modified before they are added as keys:
        * values coerced to string (if not bytes)
        * non-unique keys are appended with '__{num}' suffix

    eg
        {'a':    0,
         'b':    1,
         'c':    2,
         'b__2': 3,
         'b__3': 4} = map_values_to_enum(['a', 'b', 'c', 'b', 'b'])
    """
    duplicates = {}
    values_to_indices = ordereddict()

    for i, v in enumerate(sequence, start):
        is_bytes = isinstance(v, bytes)

        if is_bytes:
            v_str = v.decode()
        else:
            v_str = str(v)

        if as_snake_case:
            v_str = snake_case(v_str)

        is_duplicate = (v_str in duplicates)

        if not is_duplicate:
            duplicates[v_str] = 1
        else:
            duplicates[v_str] += 1
            v_str = '{}__{}'.format(v_str, duplicates[v_str])

        if is_bytes:
            v_str = v_str.encode()

        values_to_indices[v_str] = i

    return values_to_indices


# noinspection PyProtectedMember
def to_namespaces(o, as_snake_case=False):
    """ recursively convert values to namespaces """

    if hasattr(o, '_fields'):
        if as_snake_case:
            fields = [snake_case(k) for k in o._fields]
        else:
            fields = o._fields

        d = [(k, to_namespaces(v)) for k, v in zip(fields, o)]
        return namespace_cls(d)

    elif isinstance(o, dict):
        if as_snake_case:
            d = [(snake_case(k), to_namespaces(v)) for k, v in o.items()]
        else:
            d = [(k, to_namespaces(v)) for k, v in o.items()]

        return namespace_cls(d)

    elif is_collection(o):
        return [to_namespaces(v) for v in o]
    else:
        return o


# noinspection PyArgumentList, PyProtectedMember
def to_namedtuples(o, as_snake_case=False):
    is_namedtuple = (isinstance(o, tuple) and
                     type(o) is not tuple)

    if is_namedtuple:
        if as_snake_case:
            fields = [snake_case(k) for k in o._fields]
        else:
            fields = o._fields

        nt = namedtuple(type(o).__name__, fields)
        return nt(*[to_namedtuples(v) for v in o])

    if isinstance(o, dict):
        if as_snake_case:
            fields = [snake_case(n) for n in o.keys()]
        else:
            fields = o.keys()

        nt = namedtuple('NT', fields)
        return nt(*[to_namedtuples(v) for v in o.values()])

    elif is_collection(o):
        return [to_namedtuples(v) for v in o]
    else:
        return o


# noinspection DuplicatedCode
def snake_case(s):
    """ eg:
        'some_value' = snake_case('someValue')

    circular dependencies?
        from .text import snake_case as _snake_case_
        return _snake_case_(s)
    """
    camel_re = re.compile('''
        (?<=[a-z])[A-Z](?=[a-z])
    ''', re.VERBOSE)

    s = s.strip()
    s = '_'.join(s.split())

    matches = camel_re.finditer(s)
    matches = list(matches)

    _s_ = list(s)

    for match in reversed(matches):
        i_1 = match.span()[0]
        i_2 = i_1 + 1
        c = match.group().lower()

        _s_[i_1:i_2] = ['_', c]

    return ''.join(_s_).lower()

