## Managing tabular data shouldn't be complicated.

If values are stored in a matrix, it should't be any harder to iterate or modify
than a normal list. One enhancement, however, would be to have row values accessible
by column names instead of by integer indeces,eg

    for row in m:
        row.header

    for row in m:
        row[17]    (did i count those columns correctly?)


#### Two naive solutions for this are:

1) Convert rows to dictionaries

    Using duplicate dictionary instances for every row has a high memory
    footprint, and makes accessing values by index more complicated, eg

        [{'col_a': 1.0, 'col_b': 'b', 'col_c': 'c'},
         {'col_a': 1.0, 'col_b': 'b', 'col_c': 'c'}]

2) Convert rows to namedtuples

    Named tuples do not have per-instance dictionaries, so they are
    lightweight and require no more memory than regular tuples,
    but their values are read-only (which makes this kinda a dealbreaker)

Another possibility would be to store the values in column-major order,
like in a database. This has a further advantage in that all values
in the same column are usually of the same data type, allowing them to
be stored more efficiently

    row-major order:
        [['coi_a', 'col_b', 'col_c'],
         [1.0,     'b',    'c'],
         [1.0,     'b',    'c'],
         [1.0,     'b',    'c']]

    column-major order:
         {'col_a': [1.0, 1.0, 1.0],
          'col_a': ['b', 'b', 'b'],
          'col_a': ['c', 'c', 'c']}


This is essentially what a pandas DataFrame is. The drawback to this
is a major conceptual overhead. 
- **Intuitively, each row is some entity, each column is a property of that row**

- DataFrames have some great features, but also require specialized syntax that can get very awkward and requires a lot of memorization

The flux_cls attempts to balance ease-of-use and performance. It has the following attributes:
- row-major iteration
- named attributes on rows
- value mutability on rows
- light memory footprint
- efficient updates and modifications