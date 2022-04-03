## Managing tabular data shouldn't be complicated.
---
##### See
##### https://github.com/michael-ross-ven/vengeance_example/blob/main/flux_example.py
##### https://github.com/michael-ross-ven/vengeance_example/blob/main/excel_example.py
##### for examples
\
\
Values stored as list of lists (ie, a matrix) should be easily managed without the need to install a 
massive or complex library. A drawback of using pure python list of lists however, 
is that each column is accessed by integer indices, instead of by a more meaningful column name, eg

    for row in matrix:
        row[17]              # What's in that 18th column again? Did any of the columns get reordered?

    for row in matrix:
        row.customer_id      # Oh, duh


#### Two possible approaches for adding column attribute to each row are:

1) Convert rows to dictionaries (a JSON-like approach)?

    However, using duplicate dictionary instances for every row has a high memory
    footprint, and makes renaming or modifying columns an expensive operation, eg
    
        [
            {'col_a': 'a', 'col_b': 'b', 'col_c': 'c'},
            {'col_a': 'a', 'col_b': 'b', 'col_c': 'c'},
            {'col_a': 'a', 'col_b': 'b', 'col_c': 'c'}
        ]

        for row in matrix:
            row['col_a']


2) Or, convert rows to namedtuples?

    Namedtuples do not have per-instance dictionaries, so they have a much
    lighter memory footprint. Unfortunately, tuple values are stored read-only, which makes 
    any modifications tricky.

        [
            row(col_a='a', col_b='b', col_c='c'),
            row(col_a='a', col_b='b', col_c='c'),
            row(col_a='a', col_b='b', col_c='c')
        ]

        for row in matrix:
            row.col_a = 'a'             # uh oh...


#### Doesn't the pandas DataFrame already already solve this?

In a DataFrame, data is stored in column-major order, and there is a huge performance penalty 
for any row-by-row iteration. Row-major order is the most natural way to think about the data, 
where **each row is some entity, and each column is a property of that row**. 

    row-major order:
        [['col_a', 'col_b', 'col_c'],
         ['a',     'b',     'c'],
         ['a',     'b',     'c'],
         ['a',     'b',     'c']]

    column-major order
         {'col_a': ['a', 'a', 'a'],
          'col_a': ['b', 'b', 'b'],
          'col_a': ['c', 'c', 'c']}


A DataFrame also requires specialized methods for nearly every operation (to take advantage of vectorization), 
which can lead to very convoluted syntax, and makes it harder to see the one -- and preferably only one -- obvious way to do something.

    # wait, what exactly does this do again?
    df.groupby('subgroup', as_index=False).apply(lambda x: (x['col1'].head(1), 
                                                            x.shape[0], 
                                                            x['start'].iloc[-1] - x['start'].iloc[0]))



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

    
    

