#### (See https://github.com/michael-ross-ven/vengeance_unittest project for usage)


## Managing tabular data shouldn't be complicated.
(TODO: cleanup typos in this readme)

Values stored as list of lists (ie, a matrix) should be able to be easily managed with pure Python,  
without the need for a massive or complex library.

One nice-to-have in this kind of data however, would be to make each row in the matrix accessible by column names instead 
of by integer indices, eg

    for row in matrix:
        row.field_a

    for row in matrix:
        row[17]              (did I count those columns correctly?)


#### Two possible approaches for implementing this nice-to-have are:

1) Convert rows to dictionaries (a JSON-like approach)

    However, using duplicate dictionary instances for every row has a high memory
    footprint, makes renaming or modifying columns an expensive operation. 
    In the case that row values dd need to be accessed by numerical index, this requires an extra layer of 
    complexity, whereby items first need to be converted into dictionary keys and values 
    (where their original order must be guaranteed)

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

- The DataFrame requires specialized syntax for specialized operations, instead of using a limited set of generic, 
compositional operations, which can become very convoluted and awkward for ostensibly simple and common scenarios. 
(Antithetical to the Python principle "there should be one — and preferably only one — obvious way to do it").

- Until performance becomes a deciding factor, it would be desirable to develop with a library 
that offers the simplest organization of the data and is easiest to debug. (The same philosophy is used to design 
Python itself, where performance is often sacrificed for clarity).

The flux_cls in vengeance attempts to maximize ease-of-use, but is still highly performant up to mid-sized data.
It has the following characteristics:
- Light memory footprint
- Intuitive and efficient iteration
- Named attribute access on each row (read as well as write)


#### Example usage for flux_cls:
    flux = flux_cls(matrix)

    for row in flux:
      a = row.col_a
      row.col_b = 'b'
      row.values[1:] = ['blah', 'blah', 'blah']

    flux.rename_columns({'col_a': 'renamed_a',
                         'col_b': 'renamed_b'})

    flux.insert_rows(i=5, rows=[['blah', 'blah', 'blah']] * 10)

