## Managing tabular data shouldn't be complicated.
---
##### See https://github.com/michael-ross-ven/vengeance_unittest project for examples.
##### Start with *flux_example.py* and *excel_levity_example.py*
\
\
Values stored as list of lists (ie, a matrix) should be able to be easily managed with pure Python,  
without the need for a massive or complex library. An additional nice-to-have with these matrices however, 
would be to make values in each row accessible by column names instead of by integer indices, eg

    for row in matrix:
        row[17]              # What's in that 18th column again? Did any of the columns get reordered?

    for row in matrix:
        row.customer_id      # Oh, duh


#### Two possible approaches for implementing this "nice-to-have" feature are:

1) Convert rows to dictionaries (a JSON-like approach)

    However, using duplicate dictionary instances for every row has a high memory
    footprint, and makes renaming or modifying columns an expensive operation, eg
    
        [
            {'col_a': 'a', 'col_b': 'b', 'col_c': 'c'},
            {'col_a': 'a', 'col_b': 'b', 'col_c': 'c'},
            {'col_a': 'a', 'col_b': 'b', 'col_c': 'c'}
        ]

2) Convert rows to namedtuples

    Namedtuples do not have per-instance dictionaries, so they have a 
    light memory footprint. Unfortunately, tuple values are stored read-only, which makes 
    any modifications tricky. What we are really after is something that 
    behaves more like a namespace.

#### Isn't this just a reinvention of a pandas DataFrame?

In a DataFrame, data is stored in column-major order, and there is a huge performance penalty 
for any row-by-row iteration. A DataFrame also requires specialized methods 
for nearly every operation (to take advantage of vectorization), which can lead to very convoluted syntax, 
and makes it less clear to see the one-- and preferably only one --obvious way to do it.

    # wait, do I have this right?
    df.groupby('subgroup', as_index=False).apply(lambda x: (x['col1'].head(1), 
                                                            x.shape[0], 
                                                            x['start'].iloc[-1] - x['start'].iloc[0]))

Row-major order is the most natural way to think about the data, where **each row is some entity, and each column is a property of that row**. Reading and modifying values along row-by-row iteration is much more intuitive, and doesn't require vectorization optimzation 
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


#### Example usage for vengeance.flux_cls:
    matrix = [['col_a', 'col_b', 'col_c'],
              ['a',     'b',     'c'],
              ['a',     'b',     'c'],
              ['a',     'b',     'c']]
    flux = vengeance.flux_cls(matrix)

    for row in flux:
      a = row.col_a
      row.col_b = 'bleh'

      a = row[-1]
      row[-1] = 'bleh'


    col = flux['col_a']
    flux['col_z'] = ['bleh'] * len(flux)
    rows = flux.matrix[10:20]

    flux.insert_rows(i=5, rows=[['bleh', 'bleh', 'bleh']] * 10)
    flux.rename_columns({'col_a': 'renamed_a',
                         'col_b': 'renamed_b'})

    
    

