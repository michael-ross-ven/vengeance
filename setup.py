
import os

import setuptools
from setuptools import setup

from textwrap import dedent


__version__ = '1.0.22'
__release__ = '$release 13'

dependencies = ('comtypes',
                'pypiwin32',
                'python-dateutil',
                'pyodbc')


long_description = 'https://github.com/michael-ross-ven/vengeance/blob/master/README.md'


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


def readme_to_description():
    """ https://commonmark.org/help/tutorial/ 
    this_directory = path.abspath(path.dirname(__file__))
    """

    global long_description

    f_dir = os.path.realpath(__file__)
    f_dir = os.path.split(f_dir)[0]

    with open(f_dir + '\\README.md', encoding='utf-8') as f:
        long_description = f.read()


if __name__ == '__main__':
    write_version_file()
    # readme_to_description()

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
