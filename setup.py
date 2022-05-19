
import os
import sys
import setuptools
from setuptools import setup

"""
Publishing (Perfect) Python Packages on PyPi
https://youtu.be/GIF3LaRqgXo

https://markdownlivepreview.com/
https://hynek.me/articles/conditional-python-dependencies/
https://betterprogramming.pub/a-python-package-developers-cheat-sheet-3efb9e9454c7
https://itnext.io/beautify-github-repo-7348b1971899


install_requires=[
        'enum34 ; python_version<"3.4"',
        'pywin32 >= 1.0 ; platform_system=="Windows"'
    ]

pip install vengeance[comtypes]
pip install vengeance[pypiwin32]
pip install vengeance[python-dateutil]
pip install vengeance[numpy]
pip install vengeance[comtypes,pypiwin32,python-dateutil,numpy]

todo:
    publish to conda
"""

is_windows_os       = (os.name == 'nt' or sys.platform == 'win32')
is_pypy_interpreter = ('__pypy__' in sys.builtin_module_names)
loads_excel_module  = (is_windows_os and not is_pypy_interpreter)

__version__ = '1.1.29'
__release__ = '$release 66'
description = 'Library focusing on row-major organization of tabular data and control over the Excel application'

try:
    with open('README.md', 'r') as f:
        long_description = f.read()

    long_description_content_type = 'text/markdown'
except:
    long_description = 'https://github.com/michael-ross-ven/vengeance/blob/master/README.md'
    long_description_content_type = 'text'

if loads_excel_module:
    install_requires = ['comtypes',
                        'pypiwin32']
else:
    install_requires = []

extras_require = {":python_version>='3.0'": ['python-dateutil',
                                             'numpy']}


if __name__ == '__main__':
    setup(name='vengeance',
          version=__version__,
          description=description,
          long_description=long_description,
          long_description_content_type=long_description_content_type,
          url='https://github.com/michael-ross-ven/vengeance',
          author='Michael Ross',
          author_email='',
          license='MIT',
          install_requires=install_requires,
          extras_require=extras_require,
          packages=setuptools.find_packages(),
          classifiers=[
              "Programming Language :: Python :: 3",
              "License :: OSI Approved :: MIT License"
            ]

          )
