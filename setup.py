
import os
import setuptools
from setuptools import setup

"""
Publishing (Perfect) Python Packages on PyPi
https://youtu.be/GIF3LaRqgXo

https://markdownlivepreview.com/
https://hynek.me/articles/conditional-python-dependencies/
https://betterprogramming.pub/a-python-package-developers-cheat-sheet-3efb9e9454c7

pip install vengeance[comtypes]
pip install vengeance[pypiwin32]
pip install vengeance[python-dateutil]
pip install vengeance[numpy]
pip install vengeance[comtypes,pypiwin32,python-dateutil,numpy]
"""

is_windows_os = (os.name == 'nt')

__version__ = '1.1.23'
__release__ = '$release 60'

description      = 'Library focusing on row-major organization of tabular data and control over the Excel application'
long_description = 'https://github.com/michael-ross-ven/vengeance/blob/master/README.md'

try:
    with open('README.md', 'r') as f:
        long_description = f.read()
except:
    pass


if is_windows_os:
    install_requires = ['comtypes',
                        'pypiwin32']
else:
    install_requires = []

extras_require = {":python_version>='3.0'": ['python-dateutil',
                                             'numpy']}


def __move_win32com_gencache_folder():
    """
    move win32com gen_py cache files from temp to site-packages folder
    helps prevent win32com EnsureDispatch() call rejection due to corrupted COM files
    """
    if not is_windows_os:
        return
        
    try:
        import shutil
        import site

        # win32com site-package installed?
        if not os.path.exists(site.getsitepackages()[1] + '\\win32com\\'):
            return

        new_gencache_folder = site.getsitepackages()[1] + '\\win32com\\gen_py\\'
        old_gencache_folder = os.environ['userprofile'] + '\\AppData\\Local\\Temp\\gen_py\\'

        if not os.path.exists(new_gencache_folder):
            os.makedirs(new_gencache_folder)
            if os.path.exists(old_gencache_folder):
                shutil.rmtree(old_gencache_folder)

    except Exception:
        pass


if __name__ == '__main__':
    setup(name='vengeance',
          version=__version__,
          description=description,
          long_description=long_description,
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

    if is_windows_os:
        __move_win32com_gencache_folder()

