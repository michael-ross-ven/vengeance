##### For example usage, see:
https://github.com/michael-ross-ven/vengeance_example/blob/main/flux_example.py
<br/>
https://github.com/michael-ross-ven/vengeance_example/blob/main/excel_example.py
<br/>
<br/>
<br/>

## Managing data stored as rows and columns shouldn't be complicated.

When given a list of lists in python (ie, a matrix), your first instinct is to loop over rows and modify values, in-place. It's the most 
natural way to think about the data, because conceptually, **each row is some entity, and each column is a property of that row**, much 
like a list of objects.

A headache when dealing with list of lists however, is having to keep track of columns by integer elements; it would be nice to replace 
the indices on each row with named attributes, and have these applied even when the columns are not known ahead of time, such as when 
pulling data from a sql table or csv file.

    for row in matrix:
        row[17]          # what's in that 18th column again?

    for row in matrix:
        row.customer_id  # oh, duh


#### Doesn't the pandas DataFrame already already solve this?
In a DataFrame, data is taken out of its native list of list format and is organized in column-major order, which comes with some 
advantages as well as drawbacks.

    Row-major order:
        [['attribute_a', 'attribute_b', 'attribute_c'],
         ['a',           'b',           3.0],
         ['a',           'b',           3.0],
         ['a',           'b',           3.0]]

    Column-major order:
        {'attribute_a': array(['a', 'a', 'a'], dtype='<U1'),
         'attribute_b': array(['b', 'b', 'b'], dtype='<U1'),
         'attribute_c': array([3.,   3.,  3.], dtype=float64)}


In column-major order, values in a single column are usually all of the same datatype, so can be packed into continuous 
addresses in memory as an actual array. These contiguous elements in memory along a single column can be iterated very quickly, 
but the ability to organize data where each row is some entity, and each column is a property of that row, is mind-numbingly slow 
in a DataFrame. (DataFrame.iterrows() incurs a *huge* performance penalty, and can be 1,000x times slower to iterate than a built-in list)

DataFrames also take advantage of vectorization, where operations can be applied to an entire set of values at once. 
But removing explicit loops requires specialized method calls for almost *every* operation and modification (when was 
the last time you needed to call the .kurtosis() method on a Series?) This also makes the syntax much more convoluted, 
less intuitive, and usually involves digging through a lot of documentation. 

    # wait, what exactly does this do again?
    df.groupby('subgroup', as_index=False).apply(lambda x: (x['col1'].head(1), 
                                                            x.shape[0], 
                                                            x['start'].iloc[-1] - x['start'].iloc[0]))


###### DataFrame Advantages:
* vectorized operations on contiguous arrays are very fast

###### DataFrame Disadvantages:
* syntax doesnt always make sense or drive intuition
* iteration by rows is almost completely out of the question
* working with json is notoriously difficult
* managing datatypes can sometimes be problematic
* harder to debug / inspect


#### I mean, why are we working in Python to begin with?
###### The whole purpose of Python is:
* don't have to worry about datatypes (interpreted,dynamic typing)
* emphasis on code readability
* less concerned about program execution times


#### vengeance.flux_cls:
* similar idea behind a pandas DataFrame, but is more closely aligned with Python's design philosophy
* when you're willing to trade for a little bit of speed for a lot simplicity
* a lightweight, pure-python wrapper class around list of lists
* applies named attributes to rows; values are mutable during iteration
* provides convenience aggregate operations (sort, filter, groupby, etc)


Example usage:

    # matrix organized like csv data, attribute names are provided in first row
    matrix = [['attribute_a', 'attribute_b', 'attribute_c'],
              ['a',           'b',           3.0],
              ['a',           'b',           3.0],
              ['a',           'b',           3.0]]
    flux = vengeance.flux_cls(matrix)

    for row in flux:
        a = row.attribute_a
        a = row['attribute_a']
        a = row[-1]
        a = row.values[:-2]

        row.attribute_a    = None
        row['attribute_a'] = None
        row[-1]            = None
        row.values[:2]     = [None, None]

    row    = flux.matrix[-5]
    column = flux['attribute_a']
    matrix = list(flux.values())
    
    flux['attribute_a']   = [some_function(v) for v in flux['attribute_a']]
    flux['attribute_new'] = ['blah'] * flux.num_rows

    flux.rename_columns({'attribute_a': 'renamed_a',
                         'attribute_b': 'renamed_b'})
    flux.insert_columns((0, 'inserted_a'),
                        (2, 'inserted_b'))
    flux.delete_columns('inserted_a',
                        'inserted_b')

    flux.sort('attribute_c')
    flux.filter(lambda row: row.attribute_b != 'c')
    u = flux.unique('attribute_a', 'attribute_b')

    flux['attribute_new'] = [random.uniform(0, 9) for _ in range(flux.num_rows)]
    d_1 = flux.map_rows_append('attribute_a', 'attribute_b')
    d_2 = flux.map_rows_nested('attribute_a', 'attribute_b')

    countifs = {k: len(rows) for k, rows in d_1.items()}
    sumifs   = {k: sum([row.attribute_new for row in rows])
                                          for k, rows in d_1.items()}

    flux.to_csv('file.csv')
    flux = flux_cls.from_csv('file.csv')

    flux.to_json('file.json')
    flux = flux_cls.from_json('file.json')

