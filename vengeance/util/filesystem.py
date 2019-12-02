
import _pickle as cpickle

import csv
import json
import os
import shutil

from datetime import datetime
from glob import glob

from .text import p_json_dumps
from .text import repr_


def read_file(path, encoding=None, mode='r'):
    """
    assumes text file unless extension is in these specialized formats:
        .csv
        .json
        .flux
        .pkl
        .pickle
    """
    assert_path_exists(path)

    extn = file_extension(path, include_dot=True)
    if extn.startswith('.xls') or extn in {'.7z', '.gzip', '.hd5'}:
        raise NotImplementedError

    if extn == '.csv':
        with open(path, mode, encoding=encoding) as f:
            return list(csv.reader(f))

    if extn == '.json':
        with open(path, mode, encoding=encoding) as f:
            return json.load(f)

    if extn in {'.flux', '.pkl', '.pickle'}:
        if not mode.endswith('b'):
            mode += 'b'

        with open(path, mode) as f:
            return cpickle.load(f)

    with open(path, mode, encoding=encoding) as f:
        return f.read()


def write_file(path, data, encoding=None, mode='w'):
    """
    assumes text file unless extension is in these specialized formats:
        .csv
        .json
        .flux
        .pkl
        .pickle
    """
    extn = file_extension(path, include_dot=True)

    if extn == '.csv':
        with open(path, mode, encoding=encoding) as f:
            csv.writer(f, lineterminator='\n').writerows(data)

        return

    if extn == '.json':
        if not isinstance(data, str):
            data = p_json_dumps(data, ensure_ascii=(encoding is None))

        with open(path, mode, encoding=encoding) as f:
            f.write(data)

        return

    if extn in {'.flux', '.pkl', '.pickle'}:
        if not mode.endswith('b'):
            mode += 'b'

        with open(path, mode) as f:
            cpickle.dump(data, f)

        return

    # convert data to string: f.write() is much faster than f.writelines()
    if not isinstance(data, str):
        data = repr_(data, concat='\n', quotes=False, wrap=False)

    with open(path, mode, encoding=encoding) as f:
        f.write(data)


def clear_dir(filedir, allow_not_exist=False):
    filedir = standardize_dir(filedir)

    if not os.path.exists(filedir):
        if allow_not_exist is True:
            return
        else:
            raise FileNotFoundError("cannot clear: '{}', directory does not exist".format(filedir))

    for file_content in os.listdir(filedir):
        path = filedir + file_content

        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)


def copy_dir(s_dir, d_dir, exclude_dirs=None):
    exclude_dirs = exclude_dirs or set()

    s_dir = standardize_dir(s_dir)
    d_dir = standardize_dir(d_dir)

    if not os.path.exists(d_dir):
        os.makedirs(d_dir)

    for file_content in os.listdir(s_dir):
        if file_content in exclude_dirs:
            continue

        s_path = s_dir + file_content
        d_path = d_dir + file_content

        if os.path.isdir(s_path):
            shutil.copytree(src=s_path, dst=d_path)
        else:
            shutil.copy(src=s_path, dst=d_path)


def file_creation_date(path):
    unix_t = os.path.getctime(path)
    return datetime.fromtimestamp(unix_t)


def file_last_modified(path):
    unix_t = os.stat(path).st_mtime
    return datetime.fromtimestamp(unix_t)


def standardize_dir(filedir, pathsep='/'):
    """ ensure directory follows predictable pattern

    pathsep=os.path.sep?
    """
    filedir = (filedir.replace('\\', pathsep)
                  .replace('/', pathsep)
                  .lower()
                  .strip())

    if not filedir.endswith(pathsep):
        filedir += pathsep

    return filedir


def standardize_file_name(filename):
    return filename.lower().strip()


def standardize_path(path):
    filedir, filename = parse_path(path)

    filedir  = standardize_dir(filedir)
    filename = standardize_file_name(filename)

    return filedir + filename


def sanatize_file_name(filename):
    """
    replace illegal Windows file name characters with '-'

    (there's an additional set of path characters that are
     illegal for Windows' built-in compression)
    """
    invalid_chrs = {'\\': '-',
                    '/':  '-',
                    ':':  '-',
                    '*':  '-',
                    '?':  '-',
                    '<':  '-',
                    '>':  '-',
                    '|':  '-',
                    '"':  '-'}

    for k, v in invalid_chrs.items():
        filename = filename.replace(k, v)

    filename = filename.strip()
    if not filename:
        raise IOError('file name is blank')

    return filename


def assert_path_exists(path):
    filedir, filename = parse_path(path)

    if not os.path.exists(filedir):
        raise FileNotFoundError("invalid directory: '{}'".format(filedir))

    if not os.path.exists(path):
        extn  = file_extension(filename, include_dot=True)
        retry = filename.replace(extn, '.*')
        path  = glob(standardize_dir(filedir) + retry)

        if path:
            msg = "invalid file extension".format(extn)
        else:
            msg = "'{}' not found within directory '{}'".format(filename, filedir)

        raise FileNotFoundError(msg)


def parse_path(path):

    if os.path.isdir(path):
        filedir  = path
        filename = ''
    else:
        filedir, filename = os.path.split(path)

    return filedir, filename


def file_extension(filename, include_dot=True):
    _, extn = os.path.splitext(filename)
    if include_dot is False:
        extn = extn.replace('.', '')

    extn = extn.lower().strip()

    return extn


def apply_file_extension(filename, extn):
    if not extn.startswith('.'):
        extn = '.' + extn

    if filename.endswith(extn):
        return filename

    return filename + extn


