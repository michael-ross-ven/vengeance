##### For example usage, see:
https://github.com/michael-ross-ven/vengeance_example/blob/main/vengeance_example/flux_example.py
<br/><br/>
https://github.com/michael-ross-ven/vengeance_example/blob/main/vengeance_example/excel_example.py
<br/><br/>


##### DataFrame Advantages:
* vectorized operations on contiguous arrays are memory-efficient and *very* fast

##### DataFrame Disadvantages:
* syntax doesnt always drive intuition or conceptual understanding of the actual entity represented by a row
* often fallback to iteration by rows anyway (df.iterrows())
* machine types get away from Python's type system and must contend with several 'null' datatypes

<br/>


##### Row-Major Order:
        
        [['attribute_a', 'attribute_b', 'attribute_c'],
         ['a',           'b',           3.0],
         ['a',           'b',           3.0],
         ['a',           'b',           3.0]]

##### Column-Major Order:
        
        {'attribute_a': array(['a', 'a', 'a'], dtype='<U1'),
         'attribute_b': array(['b', 'b', 'b'], dtype='<U1'),
         'attribute_c': array([3.,   3.,  3.], dtype=float64)}


In column-major order, values in a single column are usually all of the same datatype, which means they can be packed into 
consecutive addresses in memory as an actual array and iterated extremely quickly. But this speed comes at a cost: re-organizing the
data as it's intuitively understood by humans, **where each row is some entity, and each column is a property of that row**, 
is agonizingly slow. (DataFrame.iterrows() and DataFrame.apply() incur a huge performance penalty, and can be 1_000x times 
slower to iterate than Python's built-in list.)

But the restricted use of explicit loops over a DataFrame requires pandas to provide specialized API methods for almost 
every operation and modification, which often leads to convoluted syntax, especially when method-chaining is overused.

    # wait, what exactly does this do again?
    df['column'] = np.sign(df.column.diff().fillna(0)).shift(-1).fillna(0) \
                     .apply(lambda x: (x['column'].head(1),
                                       x.shape[0],
                                       x['start'].iloc[-1] - x['start'].iloc[0]))

###### (see also ['So You Wanna Be a Pandas Expert? - James Powell'](https://youtu.be/pjq3QOxl9Ok) for how impenetrable this syntax can really get, *espcially* by less experienced developers)

<br/>



## vengeance
* Python control over live Excel applications
* similar idea behind a pandas DataFrame, but pure-Python, row-major iteration


###### Excel interaction:
    def set_project_workbook(path,
                             excel_app='any',
                             **kwargs):
        global wb

        excel_app = 'new'
        # excel_app = 'any'
        # excel_app = 'empty'
        wb = vengeance.open_workbook(path,
                                     excel_app,
                                     **kwargs)
        return wb


    def worksheet_to_flux():
        """
        lev  = share.worksheet_to_lev('Sheet1')
        flux = flux_cls(lev)
            or
        flux = share.worksheet_to_flux('Sheet1')
        """

        lev  = share.worksheet_to_lev('Sheet1')
        flux = flux_cls(lev)
        # or just
        # flux = share.worksheet_to_flux('Sheet1')
        
        flux['new_column'] = 'new'
        for row in flux:
            row.col_a = 'from flux'
    
        lev['*f *h'] = flux


###### vengeance.lev_cls
* (description coming soon...)
* (actually no, Im never putting in a description for this)


###### vengeance.flux_cls:
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


###### flux_cls: columns
    column = flux['attribute_a']

    flux.rename_columns({'attribute_a': 'renamed_a',
                         'attribute_b': 'renamed_b'})
    flux.insert_columns((0, 'inserted_a'),
                        (2, 'inserted_b'))
    flux.delete_columns('inserted_a',
                        'inserted_b')


###### flux_cls: rows
    rows = [['c', 'd', 4.0],
            ['c', 'd', 4.0],
            ['c', 'd', 4.0]]

    flux.append_rows(rows)
    flux.insert_rows(5, rows)

    flux_c = flux_a + flux_b


###### flux_cls: sort / filter / apply
    flux.sort('attribute_c')
    flux.filter(lambda row: row.attribute_b != 'c')
    u = flux.unique('attribute_a', 'attribute_b')

    # apply functions like you'd normally do in Python: with comprehensions
    flux['attribute_new'] = [some_function(v) for v in flux['attribute_a']]


###### flux_cls: group / map rows
    matrix = [['year', 'month', 'random_float'],
              ['2000', '01',     random.uniform(0, 9)],
              ['2000', '02',     random.uniform(0, 9)],
              ['2001', '01',     random.uniform(0, 9)],
              ['2001', '01',     random.uniform(0, 9)],
              ['2001', '01',     random.uniform(0, 9)],
              ['2002', '01',     random.uniform(0, 9)]]
    flux = vengeance.flux_cls(matrix)

    dict_1   = flux.map_rows_append('year', 'month')
    countifs = {k: len(rows) for k, rows in dict_1.items()}
    sumifs   = {k: sum(row.random_float for row in rows)
                                        for k, rows in dict_1.items()}

    dict_2 = flux.map_rows_nested('year', 'month')
    rows_1 = dict_1[('2001', '01')]
    rows_2 = dict_2['2001']['01']


###### read / write files
    flux.to_csv('file.csv')
    flux = flux_cls.from_csv('file.csv')

    flux.to_json('file.json')
    flux = flux_cls.from_json('file.json')

    flux.to_file('file.pickle')
    flux = flux_cls.from_file('file.pickle')




