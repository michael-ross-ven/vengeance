
from typing import Dict
from ... conditional import ordereddict

'''
re-map flat dictionary keys to a nested dictionary structure

eg:
    "flat" dict keys
    d = {('a₁', 'b₁', 'c₁', 'd₁'): 'v_1',
         ('a₁', 'b₂', 'c₁', 'd₂'): 'v_2',
         ('a₂', 'b₁', 'c₁', 'd₁'): 'v_4',
         ('a₂', 'b₁', 'c₁', 'd₂'): 'v_3'}

    {'a₁': {'b₁': {'c₁': {'d₁': 'v_1'}},
            'b₂': {'c₁': {'d₂': 'v_2'}}},
     'a₂': {'b₁': {'c₁': {'d₁': 'v_4',
                          'd₂': 'v_3'}}}} = tree_cls(d).traverse()
'''


class node_cls:
    def __init__(self, value=None):
        self.children = ordereddict()
        self.value    = value


class tree_cls:
    def __init__(self, flat_dict: Dict):
        self.root = node_cls()

        if flat_dict:
            self.build(flat_dict)

    def build(self, flat_dict):
        if not isinstance(flat_dict, dict):
            raise TypeError('flat_dict must be a dictionary')

        for flat_keys, value in flat_dict.items():
            self.insert(flat_keys, value)

    def insert(self, flat_keys, value):
        node = self.root

        if not isinstance(flat_keys, (list, tuple)):
            flat_keys = [flat_keys]

        for e_key in flat_keys:
            if e_key not in node.children:
                child = node_cls(value)

                node.children[e_key] = child
                node                 = child
            else:
                node = node.children[e_key]

    def traverse_nested(self, node=None):
        node = node or self.root

        d = ordereddict()
        for k, node in node.children.items():
            if not node.children:
                d[k] = node.value
            else:
                d[k] = self.traverse_nested(node)

        return d

