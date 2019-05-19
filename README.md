## Managing tabular data shouldn't be complicated.

Values stored as list of lists shouldn't require a massive or complex library just to help manage the data. 
There shouldn't be a need to diverge very much from Python's native data structures and iteration syntax.

One nice-to-have, however, would be to make each row in the matrix accessible by column names instead 
of by integer indices, eg

    for row in matrix:
        row.field_a

    for row in matrix:
        row[17]              (did I count those columns correctly? what if the columns get re-ordered later on?)


#### Two possible approaches for implementing this nice-to-have are:

1) Convert rows to dictionaries (a JSON-like approach)

    However, using duplicate dictionary instances for every row has a high memory
    footprint, makes renaming or modifying columns an expensive operation, 
    and when needing to access values by numerical index, requires a 
    conversion of the data into dictionary keys and values

    eg
        [
            {'col_a': 1, 'col_b': 'b', 'col_c': 'c'},
            {'col_a': 2, 'col_b': 'b', 'col_c': 'c'},
            {'col_a': 3, 'col_b': 'b', 'col_c': 'c'}
        ]

2) Convert rows to namedtuples

    Namedtuples do not have per-instance dictionaries, so they are
    lightweight and require no more memory than regular tuples.
    Unfortunately, tuple values are stored read-only, which makes 
    any modifications to their field names or values much more complicated

Another possibility would be to abandon a JSON-like format (a series of rows), 
for a database-like format (a series of columns). This has the further advantage 
in that the values of the same column are usually of the same datatype, allowing 
them to be stored more efficiently

    row-major order:
        [['col_a', 'col_b', 'col_c'],
         [1,       'b',    'c'],
         [2,       'b',    'c'],
         [3,       'b',    'c']]

    column-major order:
         {'col_a': [1,   2,    3],
          'col_a': ['b', 'b', 'b'],
          'col_a': ['c', 'c', 'c']}


This is essentially what a pandas DataFrame is, but comes at the cost of huge conceptual overhead.
**Intuitively, each row is some entity, and each column is a property of that row**.
The DataFrame inverts this organization, and makes iteration by rows a frustratingly 
discouraged operation. Pandas is extremely efficient and has many other reasons 
why it has become the *de facto* data science library in Python, but for cases which aren't extremely
performance sensitive or don't involve the top 1% largest of all datasets, there are reasons 
to use a supplementary library:

- Instead of using a limited set of generic, compositional operations, the DataFrame requires specialized 
syntax for specialized operations, which can get very convoluted and awkward for ostensibly simple and common transformations. 
(Antithetical to the Python principle "there should be one — and preferably only one — obvious way to do it").

- Until performance becomes a deciding factor, it would be desirable to develop with a library 
that offers the simplest organization of the data and is easiest to debug. (The same philosophy is used to design 
Python itself, where performance is often sacrificed for clarity).

The flux_cls in vengeance attempts to maximize ease-of-use, but is still highly performant up to mid-sized data.
It has the following characteristics:
- Light memory footprint
- Intuitive and efficient iteration
- Named attribute access on each row (read as well as write)


