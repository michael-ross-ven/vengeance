
import os

import setuptools
from setuptools import setup

from textwrap import dedent


__version__  = '1.0.5'
__release__ = '$release 2'

dependencies = ('comtypes',
                'pypiwin32',
                'python-dateutil',
                'pyodbc')


long_description = '''
    need to fill this out later
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
