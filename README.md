## Managing tabular data shouldn't be complicated.

#### (See https://github.com/michael-ross-ven/vengeance_unittest project for examples, start with *flux_example.py* and *excel_levity_example.py*)
\
\
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
    footprint, makes renaming or modifying columns an expensive operation,
    and row values can't be accessed by numerical index, eg
    
        [
            {'col_a': 1, 'col_b': 'b', 'col_c': 'c'},
            {'col_a': 2, 'col_b': 'b', 'col_c': 'c'},
            {'col_a': 3, 'col_b': 'b', 'col_c': 'c'}
        ]

2) Convert rows to namedtuples

    Namedtuples do not have per-instance dictionaries, so they have a 
    light memory footprint and row values can be accessed by numerical index.
    Unfortunately, tuple values are stored read-only, which makes 
    any modifications to their field names or values much more complicated. What we 
    are after is something that behaves like a namedlist

#### Doesn't a pandas DataFrame already do this?

Yes, but in a DataFrame, data is stored in column-major order (vectorized), and going row-by-row in a DataFrame 
(df.iterrows()) suffers from poor performance. Column-major organization also requires specialized methods 
for nearly every modification, which can lead to very convoluted syntax.

The most natural way to think about the data is that **each row is some entity, and each column is a property of that row**, 
Reading and modifying values along row-major iteration are much more intuitive, and doesn't require vectorization
to be taken into account.

    row-major order:
        [['col_a', 'col_b', 'col_c'],
         ['a',     'b',     'c'],
         ['a',     'b',     'c'],
         ['a',     'b',     'c']]

    column-major order
         {'col_a': ['a', 'a', 'a'],
          'col_a': ['b', 'b', 'b'],
          'col_a': ['c', 'c', 'c']}


#### Example usage for flux_cls:
    matrix = [['col_a', 'col_b', 'col_c'],
              ['a',     'b',     'c'],
              ['a',     'b',     'c'],
              ['a',     'b',     'c']]
    flux = flux_cls(matrix)

    for row in flux:
      a = row.col_a
      row.col_b = 'blah'

      a = row.values[-1]
      row.values[-1] = 'blah'

    col = flux['col_a']
    flux['col_z'] = ['blah'] * len(flux)
    rows = flux.matrix[10:20]

    flux.insert_rows(i=5, rows=[['blah', 'blah', 'blah']] * 10)
    flux.rename_columns({'col_a': 'renamed_a',
                         'col_b': 'renamed_b'})

    
    

