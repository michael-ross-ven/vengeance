
import os

import setuptools
from setuptools import setup

from textwrap import dedent


__version__ = '1.0.42'
__release__ = '$release 35'

long_description = 'https://github.com/michael-ross-ven/vengeance/blob/master/README.md (fill this out for pypi.org later)'


def write_version_file():
    f_dir = os.path.realpath(__file__)
    f_dir = os.path.split(f_dir)[0]

    with open(f_dir + '\\vengeance\\version.py', 'w') as f:
        s = '''
            # generated from setup.py
            __version__ = '{}'
            __release__ = '{}'
        '''.format(__version__, __release__)

        s = dedent(s) + '\n\n'
        f.write(s)


if __name__ == '__main__':
    write_version_file()

    setup(name='vengeance',
          version=__version__,
          description='Library focusing on row-major organization of tabular data and control over the Excel application',
          long_description=long_description,
          url='https://github.com/michael-ross-ven/vengeance',
          author='Michael Ross',
          author_email='',
          license='MIT',
          install_requires=('comtypes', 'pypiwin32', 'python-dateutil'),
          # extra_require=('numpy', 'line-profiler'),
          packages=setuptools.find_packages(),
          classifiers=[
              "Programming Language :: Python :: 3",
              "License :: OSI Approved :: MIT License",
              "Operating System :: Microsoft :: Windows"
            ]

          )
