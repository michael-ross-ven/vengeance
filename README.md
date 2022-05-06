##### For example usage, see:
https://github.com/michael-ross-ven/vengeance_example/blob/main/vengeance_example/flux_example.py
<br/>
<br/>
https://github.com/michael-ross-ven/vengeance_example/blob/main/vengeance_example/excel_example.py
<br/>
<br/>

## Managing data stored as rows and columns shouldn't be complicated.

When given a list of lists in Python, your first instinct is to loop over rows and modify column values, in-place. It's the most 
natural way to think about the data, because **conceptually, each row is some entity, and each column is a property of that row**, 
much like a list of objects.

A headache when dealing with list of lists however, is having to keep track of columns by integer elements; it would be nice to 
replace the indices on each row with named attributes, and have these applied even when the columns are not known ahead of time, 
such as when pulling data from a sql table or csv file.

    for row in matrix:
        row[17]            # what's in that 18th column again?

    for row in matrix:
        row.customer_id    # oh, duh


### Doesn't the pandas DataFrame already already solve this?
In a DataFrame, data is taken out of its native nested list format and is organized in column-major order, which comes with some 
advantages as well as drawbacks.

##### Row-major order:
        
        [['attribute_a', 'attribute_b', 'attribute_c'],
         ['a',           'b',           3.0],
         ['a',           'b',           3.0],
         ['a',           'b',           3.0]]

##### Column-major order:
        
        {'attribute_a': array(['a', 'a', 'a'], dtype='<U1'),
         'attribute_b': array(['b', 'b', 'b'], dtype='<U1'),
         'attribute_c': array([3.,   3.,  3.], dtype=float64)}


In column-major order, values in a single column are usually all of the same datatype, and can be packed into consecutive 
addresses in memory as an actual array, which can be iterated extremely quickly. But in a DataFrame, the ability to organize 
data more intuitively, *where each row is some entity, and each column is a property of that row*, is mind-numbingly slow. 
(DataFrame.iterrows() and DataFrame.apply() incur a huge performance penalty, and can be 1,000x times slower than a built-in list)

DataFrames are intended to make heavy use of vectorization, where operations can be applied to an entire set of values at once, 
performed as instructions at the microprocessor level. But removal of explicit loops requires specialized methods for almost 
every operation and modification, which often makes the syntax convoluted. The restricted ability to iterate a DataFrame makes 
its transformations counter-inituitive to write and more effortful to read, especially when method-chaining is overused.

    # wait, what exactly does this do again?
    df['column'] = np.sign(df.column.diff().fillna(0)).shift(-1).fillna(0) \
                   .apply(lambda x: (x['column'].head(1),
                                     x.shape[0],
                                     x['start'].iloc[-1] - x['start'].iloc[0]))


##### DataFrame Advantages:
* vectorized operations on contiguous arrays are very fast

##### DataFrame Disadvantages:
* syntax doesnt always drive intuition
* iteration by rows is almost completely out of the question \
  (& working with json files is notoriously difficult)
* harder to debug / inspect when vectorized operations return an error

##### But I mean, why are we working in Python to begin with?
* emphasis on code readability
* less concerned about hyper-optimized execution times
* datatypes are abstracted away

##### [So does the DataFrame really reinforce what makes Python so great?](https://en.wikipedia.org/wiki/Zen_of_Python)
>"Explicit is better than implicit" \
"Sparse is better than dense" \
"Readability counts" \
"There should be one– and preferably only one –obvious way to do it"
>

<br/>

### vengeance.flux_cls
* similar idea behind a pandas DataFrame, but is more closely aligned with Python's design philosophy
* when you're willing to trade for a little bit of speed for a lot simplicity
* a lightweight, pure-python wrapper class around list of lists
* applies named attributes to rows; attribute values are mutable during iteration
* provides convenience aggregate operations (sort, filter, groupby, etc)
* excellent for prototyping and data-wrangling

###### Row-Major Iteration
    
    # organized like csv data, attribute names are provided in first row
    matrix = [['attribute_a', 'attribute_b', 'attribute_c'],
              ['a',           'b',           3.0],
              ['a',           'b',           3.0],
              ['a',           'b',           3.0]]
    flux = vengeance.flux_cls(matrix)

    # row attributes can be accessed by name or by sequential index
    for row in flux:
        a = row.attribute_a
        a = row['attribute_a']
        a = row[-1]
        a = row.values[:-2]

        row.attribute_a    = None
        row['attribute_a'] = None
        row[-1]            = None
        row.values[:2]     = [None, None]

    # transformations are compositional and self-documenting
    for row in flux:
        row.hypotenuse = math.sqrt(row.side_a**2 +,
                                   row.side_b**2)

    matrix = list(flux.values())


###### Columns
    column = flux['attribute_a']

    flux.rename_columns({'attribute_a': 'renamed_a',
                         'attribute_b': 'renamed_b'})
    flux.insert_columns((0, 'inserted_a'),
                        (2, 'inserted_b'))
    flux.delete_columns('inserted_a',
                        'inserted_b')


###### Rows
    rows = [['c', 'd', 4.0],
            ['c', 'd', 4.0],
            ['c', 'd', 4.0]]

    flux.append_rows(rows)
    flux.insert_rows(5, rows)

    flux_c = flux_a + flux_b


###### Sort / Filter / Apply
    flux.sort('attribute_c')
    flux.filter(lambda row: row.attribute_b != 'c')
    u = flux.unique('attribute_a', 'attribute_b')

    # apply functions like you'd normally do in Python: with comprehensions
    flux['attribute_new'] = [some_function(v) for v in flux['attribute_a']]


###### Groupby
    matrix = [['year', 'month', 'random_float'],
              ['2000', '01',     random.uniform(0, 9)],
              ['2000', '02',     random.uniform(0, 9)],
              ['2001', '01',     random.uniform(0, 9)],
              ['2001', '01',     random.uniform(0, 9)],
              ['2001', '01',     random.uniform(0, 9)],
              ['2002', '01',     random.uniform(0, 9)]]
    flux = flux_cls(matrix)

    dict_1 = flux.map_rows_append('year', 'month')
    countifs = {k: len(rows) for k, rows in dict_1.items()}
    sumifs   = {k: sum(row.random_float for row in rows)
                                        for k, rows in dict_1.items()}

    dict_2 = flux.map_rows_nested('year', 'month')
    rows_1 = dict_1[('2001', '01')]
    rows_2 = dict_2['2001']['01']


###### Read / Write Files
    flux.to_csv('file.csv')
    flux = flux_cls.from_csv('file.csv')

    flux.to_json('file.json')
    flux = flux_cls.from_json('file.json')

