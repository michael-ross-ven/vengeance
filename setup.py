
import os
import setuptools
from setuptools import setup


__version__ = '1.1.8'
__release__ = '$release 46'
long_description = ('https://github.com/michael-ross-ven/vengeance/blob/master/README.md'
                    '\n\n(specialize this for pypi.org later)')


def __move_win32com_gencache_folder():
    """
    move win32com gen_py cache files from temp to site-packages folder
    helps prevent win32com EnsureDispatch() call rejection due to corrupted COM files
    """
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
          description='Library focusing on row-major organization of tabular data and control over '
                      'the Excel application',
          long_description=long_description,
          url='https://github.com/michael-ross-ven/vengeance',
          author='Michael Ross',
          author_email='',
          license='MIT',
          install_requires=('comtypes',
                            'pypiwin32'),
          extra_require=('python-dateutil',
                         'ujson',
                         'numpy'),
          packages=setuptools.find_packages(),
          classifiers=[
              "Programming Language :: Python :: 3",
              "License :: OSI Approved :: MIT License"
            ]

          )

    __move_win32com_gencache_folder()

