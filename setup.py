
import os

import setuptools
from setuptools import setup

from textwrap import dedent


__version__ = '1.0.44'
__release__ = '$release 37'

long_description = 'https://github.com/michael-ross-ven/vengeance/blob/master/README.md (fill this out for pypi.org later)'


if __name__ == '__main__':
    setup(name='vengeance',
          version=__version__,
          description='Library focusing on row-major organization of tabular data and control over the Excel application',
          long_description=long_description,
          url='https://github.com/michael-ross-ven/vengeance',
          author='Michael Ross',
          author_email='',
          license='MIT',
          install_requires=('comtypes', 'pypiwin32'),
          extra_require=('numpy', 'python-dateutil', 'ujson', 'line-profiler'),
          packages=setuptools.find_packages(),
          classifiers=[
              "Programming Language :: Python :: 3",
              "License :: OSI Approved :: MIT License",
              "Operating System :: Microsoft :: Windows"
            ]

          )
