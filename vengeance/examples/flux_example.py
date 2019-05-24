
from string import ascii_lowercase as ascii_s
from random import choice

from vengeance import flux_cls
from vengeance import print_runtime
from vengeance.util.text import print_performance

from examples import excel_project_template as share


@print_runtime
def main():
    # help(flux_cls)

    flux = instantiate_flux()
    conflicting_header_names()

    write_to_file(flux)
    read_from_file()

    # read_from_excel()
    # write_to_excel(flux)

    modify_columns(flux)
    modify_rows(flux)

    iterate_primitive_rows(flux)
    iterate_flux_rows(flux)

    flux_sort_filter(flux)
    flux_mapping()

    flux_subclass()

    attribute_access_performance(flux)

    # compare_against_pandas()


def instantiate_flux():
    m = [['col_a', 'col_b', 'col_c']]
    for _ in range(100):
        m.append([''.join(choice(ascii_s) for _ in range(15))
                                          for _ in range(3)])
    flux = flux_cls(m)

    a = flux.headers
    a = flux.header_values

    a = flux.num_cols
    a = flux.num_rows

    a = flux.is_jagged

    return flux


def conflicting_header_names():
    """
    the flux_row_cls has certain reserved attributes (see iterate_flux_rows())

    for row in flux:
        row.names
        row.values
    """
    from vengeance.classes.flux_row_cls import flux_row_cls
    print('headers cannot be named: {}\n'.format(flux_row_cls.class_names))

    try:
        m = [['values', 'other_col', 'other_col']]
        flux_cls(m)
    except NameError as e:
        print(e)

    print()


def read_from_file():
    """ thse are CLASS METHODS, called from flux_cls not flux """
    f_dir = share.project_dir

    # flux = flux_cls.from_csv(f_dir + 'flux_file.csv')
    # flux = flux_cls.from_json(f_dir + 'flux_file.json')
    flux = flux_cls.deserialize(f_dir + 'flux_file.flux')


def write_to_file(flux):
    """ thse are INSTANCE METHODS, called from flux not flux_cls """
    f_dir = share.project_dir

    # flux.to_csv(f_dir + 'flux_file.csv')
    # flux.to_json(f_dir + 'flux_file.json')
    flux.serialize(f_dir + 'flux_file.flux')


def read_from_excel():
    share.open_project_workbook(read_only=True)
    flux = share.tab_to_flux('Sheet2')


def write_to_excel(flux):
    share.open_project_workbook(read_only=True)
    share.write_to_tab('Sheet2', flux)


def modify_columns(flux):
    flux = flux.copy(deep=True)

    del flux[3].values[2]
    del flux[4].values[2]
    del flux[5].values[2]

    if flux.is_jagged:
        flux.fill_jagged_columns()

    flux.rename_columns({'col_a': 'renamed_a',
                         'col_b': 'renamed_b'})

    # new column values are initialized to None (see docstring)
    flux.insert_columns((0,          'insert_c'),
                        ('insert_c', 'insert_b'),
                        ('insert_b', 'insert_a'),
                        ('col_c',    'insert_d'))
    flux.append_columns('append_a', 'append_b', 'append_c')

    flux.delete_columns('insert_a', 'insert_b', 'insert_c', 'insert_d')
    flux.rename_columns({'renamed_a': 'col_a',
                         'renamed_b': 'col_b'})

    # encapsulate insertion, deletion and rename within single function
    flux.matrix_by_headers('col_c',
                           '(insert_a)',
                           {'col_a': 'renamed_a'},
                           '(insert_b)',
                           '(insert_c)')

    # column assignment / retrieval
    flux['renamed_a'] = [None] * flux.num_rows
    col = flux['renamed_a']

    # appends a new column named new_col
    flux['new_col'] = ['n'] * flux.num_rows


def modify_rows(flux):
    flux_e = flux_cls()
    flux_e.append_rows([['a', 'b', 'c']] * 25)

    flux_a = flux.copy()
    flux_b = flux.copy()

    flux_b.append_rows([['a', 'b', 'c']] * 25)
    a = flux_a.num_rows
    b = flux_b.num_rows

    flux_b.insert_rows(5, [['blah', 'blah', 'blah']] * 10)

    # inserting rows at index 0 will overwrite existing headers
    flux_b.insert_rows(0, [['col_d', 'col_e', 'col_f']] +
                          [['d', 'e', 'f']] * 3)
    a = flux_a.header_values
    b = flux_b.header_values

    # add rows from another flux_cls
    flux_c = flux_a + flux_b
    
    flux_b.insert_rows(0, flux_a)
    flux_b.append_rows(flux_a[10:15])


def iterate_primitive_rows(flux):
    """ iterate rows as a list of primitive values

    .rows(r_1='*h', r_2='*l'):
        * r_1, r_2 are the start and end rows of iteration
          the default values are the specialized anchor references
          starting at header row, ending at last row
        * r_1, r_2 can also be integers

    m = list(flux.rows())
        * as full matrix, includes header row

    m = list(flux.rows(1))
        * as full matrix, excludes header row
    """
    for row in flux.rows(3):
        a = row[0]

    m = list(flux.rows(5, 10))

    # build new matrix from filtered rows
    m = [flux.header_values]
    for r, row in enumerate(flux.rows(1), 1):
        if r % 2 == 0:
            m.append(row)

    # extract single column
    b = [row[0] for row in flux.rows()]


def iterate_flux_rows(flux):
    """ iterate rows as flux_row_cls objects

    .flux_rows(r_1='*h', r_2='*l'):
        * r_1, r_2 are the start and end rows of iteration
          the default values are the specialized anchor references
          starting at header row, ending at last row
        * r_1, r_2 can also be integers

    for row in flux:
        * preferred iteration syntax
        * begins at first row, not header row

    m = flux[i_1:i_2]
        * preferred over flux.flux_rows(i_1, i_2)
        * as full matrix, slice syntax

    m = list(flux.flux_rows())
        * as full matrix, includes header row

    m = list(flux)
        * as full matrix, excludes header row

    m = flux[::10]
        * every 10th row

    offset comparisions can easily be achieved by:
        rows = iter(flux)
        row_prev = next(rows)

        for row in rows:
            # compare row_prev and row
            row_prev = row
    """
    # label rows by index to help identify them more easily
    # flux.enumerate_rows()

    for row in flux:
        # see conflicting_header_names()
        a = row.names
        a = row.values
        a = row.view_as_array       # triggers a debugging feature in PyCharm

        a = row.col_a
        a = row['col_a']
        a = row[0]

        row.col_a = a

    # slice, stride
    m = flux[5:-2]
    m = flux[::10]

    # extract single column
    col = [row.col_b for row in flux]
    col = flux['col_b']

    # extract primitive values
    m = [row.values for row in flux]

    # build new matrix from filtered rows
    m = [flux.header_values]
    for r, row in enumerate(flux):
        if r % 2 == 0:
            m.append(row.values)


def flux_sort_filter(flux):
    # filter_function
    def starts_with_a(_row):
        return (_row.col_a.startswith('a')
                or _row.col_b.startswith('a')
                or _row.col_c.startswith('a'))

    flux = flux.copy()

    # modifications return as new flux_cls
    flux_b = flux.sorted('col_a', 'col_b', 'col_c',
                         reverse=[True, True, True])
    flux_b = flux.filtered(starts_with_a)
    flux_b = flux.filtered_by_unique('col_a', 'col_b')

    # in-place modifications
    flux.sort('col_a', 'col_b', 'col_c',
              reverse=[True])
    flux.filter(starts_with_a)
    flux.filter_by_unique('col_a', 'col_b')


def flux_mapping():
    """
    notice there is a subtle difference in names between these functions
        flux.index_row  (singular)
        flux.index_rows (plural)

        .index_row
            * overwrites non-unique values
            * eg, {'a': flux_row}

        .index_rows
            * will map all rows as a lists
            * effectively, a groupby statement
            * eg, {'a': [flux_row, flux_row, flux_row]}
    """
    m = [['name_a', 'name_b', 'val_a', 'val_b']]
    m.extend([['a', 'b', 10, 20]] * 10)
    m.extend([['c', 'd', 50, 60]] * 20)
    flux = flux_cls(m)

    a = flux.unique_values('name_a')
    a = flux.unique_values('name_a', 'name_b')
    a = flux.namedtuples()

    d_1 = flux.index_row('name_a', 'name_b')
    d_2 = flux.index_rows('name_a', 'name_b')

    # notice the difference between these dictionaries
    a = d_1.__class__.__name__
    b = d_2.__class__.__name__

    k = ('a', 'b')
    a = d_1[k]          # .index_row  (singular)
    b = d_2[k]          # .index_rows (plural)

    # .index_rows() can act as a groupby / sumif
    for k, rows in d_2.items():
        v = sum(row.val_a + row.val_b for row in rows)
        print(k, v)


def flux_subclass():
    """
    the flux_custom_cls.commands variable is intended to provide a high-level description
    of the behaviors of this class, and making its state transformations explicit and modular

    flux.execute_commands(profile_performance=True)
        output performance metrics for each command (requires line_profiler site-package)
        very useful for debugging any performance issues for custom flux methods
    """
    m = [['transaction_id', 'name', 'apples_sold', 'apples_bought'],
         ['001', 'alice', 2, 0],
         ['002', 'alice', 0, 1],
         ['003', 'bob',   2, 1],
         ['004', 'chris', 2, 1],
         ['005', None,    7, 1]]

    flux = flux_custom_cls(m)

    flux.execute_commands(flux.commands)
    # flux.execute_commands(flux.commands, profile_performance=True)


class flux_custom_cls(flux_cls):

    # "behavior manifest" variable
    commands = ['_replace_nones',
                '_count_unique_names']

    def __init__(self, matrix):
        self.num_unique_names = []
        super().__init__(matrix)

    def _replace_nones(self):
        for row in self:
            if row.name is None:
                row.name = 'unknown'

    def _count_unique_names(self):
        self.num_unique_names = len(self.unique_values('name'))


@print_performance(repeat=3, number=10)
def attribute_access_performance(flux):
    # flux.bind()

    for row in flux:
        # a = row.col_a
        # b = row.col_b
        # c = row.col_c

        row.col_a = row.col_a
        row.col_b = row.col_b
        row.col_c = row.col_c


def compare_against_pandas():
    """
    https://realpython.com/fast-flexible-pandas/

    what are the tradeoffs with pandas?

    DataFrame Pros:
        performance:
            * pandas DataFrames are much more optimized for speed and memory efficiency

    flux_cls Pros:
        built on pure-python lists:
            * Python's built-in list data structure is fantastic, and is much
              less of a hassle than numpy.ndarrays or pandas.Series

            * Python's built-in list has no major inefficieny (such as appending rows to DataFrames)

            * although slower than pandas, iteration of flux_cls is every bit as fast as
              iteration over any native python list

            * if you ever HAVE to iterate rows in a DataFrame, the flux_cls can be
              70x to 7,000x faster depending on whether you use .iterrows
              or .itertuples

        clarity:
            * row-major iteration coincides with the intuitive organization of the data

            * allows for much clearer syntax; the optimizations in the DataFrame
              come at the cost of readability. The use of lambda functions, espcially,
              contribute to overly complicated syntax, like this:

                  df['c'] = df.apply(
                      lambda row: row['a']*row['b'] if np.isnan(row['c']) else row['c'],
                      axis=1
                  )
    """
    import timeit
    import pandas

    df = None
    flux = None

    def init():
        nonlocal df
        nonlocal flux

        m = [['col_a', 'col_b', 'col_c']]
        for i in range(100000):
            if i % 10 == 0:
                m.append([None, 'fill', 'missing'])
            else:
                m.append(['blah', 'blah', 'blah'])

        df = pandas.DataFrame(m[1:], columns=m[0])

        flux = flux_cls(m)

    def as_dataframe():
        nonlocal df

        def fill(_row):
            if _row[0] is None:
                return ' '.join((_row[1], _row[2]))

        # for i, row in df.iterrows():
        #     pass

        # for row in df.itertuples():
        #     pass

        # df['col_a'] = 1
        # df['col_a'] = df['col_b'] + df['col_c']
        # df['col_a'] = df.apply(fill)

        a = df[df['col_a'].notnull() & (df['col_b'] == 'blah')]

        # df_2 = pandas.DataFrame([[1, 2, 3]] * 5000)
        # df.append(df_2)

    def as_flux():
        nonlocal flux

        def f(_row):
            return _row.col_a is not None and _row.col_b == 'blah'

        # for row in flux:
        #     # pass
        #
        #     # row.col_a = 1
        #     row.col_a = row.col_b + row.col_c
            # if row.col_a is None:
            #     row.col_a = ' '.join((row.col_b, row.col_c))

        a = flux.filtered(f)

        # flux.append_matrices_rows([[1, 2, 3]] * 5000)

    init()

    # as_dataframe()
    # as_flux()

    t_1 = timeit.timeit(as_dataframe, number=10)
    t_2 = timeit.timeit(as_flux, number=10)
    print('as_dataframe: {:.4f}'.format(t_1))
    print('as_flux_cls:  {:.4f}'.format(t_2))

    if t_2 < t_1:
        print('flux_cls faster by: {:,.2f}x'.format(t_1 / t_2))
    else:
        print('dataframe faster by: {:,.2f}x'.format(t_2 / t_1))


main()

