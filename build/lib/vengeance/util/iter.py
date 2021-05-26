
from collections import Iterable
from collections import ItemsView
from collections import KeysView
from collections import ValuesView
from collections import defaultdict
from collections import namedtuple

from itertools import chain
from typing import Generator
from typing import Union
from typing import Any
from typing import Dict
from typing import List
from typing import Tuple

from ..conditional import ordereddict


class IterationDepthError(TypeError):
    pass


class ColumnNameError(ValueError):
    pass


class namespace_cls:
    """
    similar to types.SimpleNamespace
    """
    def __init__(self, **kwargs):
        self.__dict__ = ordereddict(kwargs)

    def __iter__(self):
        return ((k, v) for k, v in self.__dict__.items())

    def __eq__(self, other):
        if (not hasattr(self, '__dict__')) or (not hasattr(other, '__dict__')):
            return NotImplemented

        return self.__dict__ == other.__dict__

    def __repr__(self):
        items = ('{}={!r}'.format(k, v) for k, v in self.__dict__.items())
        items = ', '.join(items)

        return '{{{}}}'.format(items)


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
                           first_element_only=True):
    """
    (this function is heavily utilized to correctly un-nest
     arguments in variable-arity flux_cls methods)

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

    if depth is None and depth_offset is None:
        raise ValueError('conflicting values for depth and depth_offset')

    if isinstance(depth, int) and isinstance(depth_offset, int):
        raise ValueError('conflicting values for depth and depth_offset')

    if depth_offset is None:
        value_depth  = iteration_depth(values, first_element_only=first_element_only)
        depth_offset = depth - value_depth

    if depth_offset < 0:
        for _ in range(abs(depth_offset)):

            if first_element_only:
                if is_descendable(values): values = values[0]
                else:                      break
            else:
                values = list(chain(*values))
                # values = list(chain.from_iterable(values))

    elif depth_offset > 0:
        for _ in range(depth_offset):
            values = [values]

    return values


def standardize_variable_arity_arguments(values,
                                         depth=None,
                                         depth_offset=None):
    """
    (this function is heavily utilized to correctly un-nest
     arguments in variable-arity flux_cls methods)
    """

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
        False = is_collection('bleh')
        True  = is_collection(['bleh'])

        False = is_collection(range(3))
        True  = is_collection(list(range(3)))
    """
    if isinstance(o, (str, bytes)):
        return False

    if isinstance(o, range):
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
    base_cls_names      = set(base_class_names(o))
    vengeance_cls_names = {'flux_cls',
                           'excel_levity_cls'}

    return bool(base_cls_names & vengeance_cls_names)


# def is_namedtuple_class(o):
#     return (isinstance(o, tuple) and
#             type(o) is not tuple)


def is_descendable(o):
    return (is_collection(o) and
            is_subscriptable(o) and
            len(o) == 1)


def iterator_to_collection(o):
    if is_vengeance_class(o):
        return list(o.rows())

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


# noinspection PyProtectedMember
def to_namespaces(o):
    """ recursively convert values to namespace """

    # region {closure functions}
    # noinspection PyProtectedMember
    def traverse(k, v):
        if isinstance(v, dict):
            return to_namespaces(v)
        elif hasattr(v, '_asdict'):
            return to_namespaces(v._asdict())
        elif is_collection(v):
            return [traverse(k, _) for _ in v]
        else:
            return v
    # endregion

    if hasattr(o, '_asdict'):
        o = o._asdict()

    if isinstance(o, dict):
        d = {k: traverse(k, v) for k, v in o.items()}
        return namespace_cls(**d)
    elif is_collection(o):
        return [traverse(None, v) for v in o]
    else:
        return o


# noinspection PyArgumentList,PyProtectedMember
def to_namedtuples(o):
    """ recursively convert values to namedtuples """

    # region {closure functions}
    # noinspection PyProtectedMember
    def traverse(v):
        if isinstance(v, dict):
            return to_namedtuples(v)
        elif hasattr(v, '_asdict'):
            return to_namedtuples(v._asdict())
        elif is_collection(v):
            return [traverse(_) for _ in v]
        else:
            return v
    # endregion

    if hasattr(o, '_asdict'):
        o = o._asdict()

    if isinstance(o, dict):
        nt = namedtuple('nt', o.keys())
        return nt(*[traverse(v) for v in o.values()])
    elif is_collection(o):
        return [traverse(v) for v in o]
    else:
        return o


def to_grouped_dict(flat: Dict) -> Dict[Any, Dict]:
    """ re-map flat keys to a nested dictionary structure

    eg:
        # keys should be tuples
        d = {('a₁', 'b₁', 'c₁', 'd₁'): 'v_1',
             ('a₁', 'b₂', 'c₁', 'd₂'): 'v_2',
             ('a₂', 'b₁', 'c₁', 'd₁'): 'v_4',
             ('a₂', 'b₁', 'c₁', 'd₂'): 'v_3'}

        {'a₁': {'b₁': {'c₁': {'d₁': 'v_1'}},
                'b₂': {'c₁': {'d₂': 'v_2'}}},
         'a₂': {'b₁': {'c₁': {'d₁': 'v_4',
                              'd₂': 'v_3'}}}} = to_grouped_dict(d)
    """

    # region {closures}
    class node_cls:
        def __init__(self, value=None):
            self.children = ordereddict()
            self.value    = value


    class grouped_cls:
        def __init__(self, d):
            self.children = ordereddict()

            unique_len_edges = None
            for edges, value in d.items():
                len_edges = len(edges)

                if unique_len_edges is None:
                    unique_len_edges = len_edges
                elif len_edges != unique_len_edges:
                    raise ValueError('keys have mismatched lengths: {}'.format(edges))

                self.add(edges, value, len_edges)

        def add(self, edges, value, len_edges):
            node = self

            for i, e_key in enumerate(edges, 1):
                if e_key not in node.children:
                    if i == len_edges: child = node_cls(value)
                    else:              child = node_cls(None)

                    node.children[e_key] = child
                    node = child
                else:
                    node = node.children[e_key]

        def traverse(self, node=None):
            node = node or self

            d = ordereddict()
            for k, node in node.children.items():
                if node.children == {}:
                    d[k] = node.value
                else:
                    d[k] = self.traverse(node)

            return d
    # endregion

    network = grouped_cls(flat)
    groups  = network.traverse()

    return groups


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



