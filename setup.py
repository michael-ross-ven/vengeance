
import os

import setuptools
from setuptools import setup

from textwrap import dedent


__version__  = '1.0.9'
__release__ = '$release 3'

dependencies = ('comtypes',
                'pypiwin32',
                'python-dateutil',
                'pyodbc')


long_description = '''
Managing tabular data shouldn't be complicated.

If values are stored in a matrix, it should't be any harder to iterate or modify
than a normal list. One enhancement, however, would be to have row values accessible
by column names instead of by integer indeces
    eg,
        for row in m:
            row.header

        for row in m:
            row[17]         # did i count those columns correctly?


Two naive solutions for this are:
    1) convert rows to a dictionaries
    Using duplicate dictionary instances for every row has a high memory
    footprint, and makes accessing values by index more complicated
    eg,
        [{'col_a': 1.0, 'col_b': 'b', 'col_c': 'c'},
        {'col_a': 1.0, 'col_b': 'b', 'col_c': 'c'}]

    2) convert rows to namedtuples
    Named tuples do not have per-instance dictionaries, so they are
    lightweight and require no more memory than regular tuples,
    but their values are read-only

Another possibility would be to store the values in column-major order,
like in a database. This has a further advantage in that all values
in the same column are usually of the same data type, allowing them to
be stored more efficiently
eg,
    row-major order
        [['coi_a', 'col_b', 'col_c'],
         [1.0,     'b',    'c'],
         [1.0,     'b',    'c'],
         [1.0,     'b',    'c']]

    column-major order
         {'col_a': [1.0, 1.0, 1.0],
          'col_a': ['b', 'b', 'b'],
          'col_a': ['c', 'c', 'c']}

This is essentially what a pandas DataFrame is. The drawback to this
is a major conceptual overhead.
***********************************************************************************
*   Intuitively, each row is some entity, each column is a property of that row   *
***********************************************************************************
    * the first thing everyone looks up for a DataFrame is "how to iterate rows",
      the first thing the documentation says is "I hope you never have to use this"

    * DataFrames have some great features, but also require specialized
      syntax that can get very awkward and requires a lot of memorization


The flux_cls attempts to balance intuitive iteration with performance

it has the following attributes:
    * row-major order
    * named attributes on rows (that are efficiently updated)
    * value mutability on rows
    * light memory footprint
'''


def write_version_file():
    f_dir = os.path.realpath(__file__)
    f_dir = os.path.split(f_dir)[0]

    with open(f_dir + '\\vengeance\\version.py', 'w') as f:
        s = '''
            # generated from setup.py
            __version__ = '{}'
            __release__ = '{}'

            dependencies = {}
        '''.format(__version__, __release__, repr(dependencies))
        
        f.write(dedent(s))


if __name__ == '__main__':
    write_version_file()

    setup(name='vengeance',
          version=__version__,
          description='Data library focusing on pure python data structures and Excel interaction',
          long_description=long_description,
          url='https://github.com/michael-ross-ven/vengeance',
          author='Michael Ross',
          author_email='michael.ross.uncc@gmail.com',
          license='MIT',
          install_requires=dependencies,
          # packages=('vengeance',),
          packages=setuptools.find_packages(),
          classifiers=[
              "Programming Language :: Python :: 3",
              "License :: OSI Approved :: MIT License",
              "Operating System :: Microsoft :: Windows"
          ]

          )
