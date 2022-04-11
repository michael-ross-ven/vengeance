
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

todo:
    publish to conda
"""

is_windows_os = (os.name == 'nt')

__version__ = '1.1.25'
__release__ = '$release 62'
description = 'Library focusing on row-major organization of tabular data and control over the Excel application'

try:
    with open('README.md', 'r') as f:
        long_description = f.read()

    long_description_content_type = 'text/markdown'
except:
    long_description = 'https://github.com/michael-ross-ven/vengeance/blob/master/README.md'
    long_description_content_type = 'text'

if is_windows_os:
    install_requires = ['comtypes',
                        'pypiwin32']
else:
    install_requires = []

extras_require = {":python_version>='3.0'": ['python-dateutil',
                                             'numpy']}


def __move_win32com_gencache_folder():
    """
    move win32com gen_py cache files to site-packages folder
    from
        %userprofile%/Local/Temp/gen_py/
    to
        %python_folder%/Lib/site-packages/win32com/gen_py/
    
    helps prevent win32com EnsureDispatch() call rejection due to corrupted COM files
    """
    if not is_windows_os:
        return
    
    # win32com site-package installed?
    try:
        import win32com
    except (ModuleNotFoundError, ImportError):
        return

    try:
        import shutil
        import site
        
        # win32com site-package where its supposed to be?
        if not os.path.exists(site.getsitepackages()[1] + '\\win32com\\'):
            return

        appdata_gcf = os.environ['userprofile'] + '\\AppData\\Local\\Temp\\gen_py'
        site_gcf    = site.getsitepackages()[1] + '\\win32com\\gen_py'

        if not os.path.exists(appdata_gcf):
            appdata_gcf = win32com.__gen_path__
            if appdata_gcf.lower() == site_gcf.lower():
                return
        
        if not os.path.exists(site_gcf):
            os.makedirs(site_gcf)
            if os.path.exists(appdata_gcf):
                shutil.rmtree(appdata_gcf)

    except Exception:
        pass


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

    if is_windows_os:
        __move_win32com_gencache_folder()

