
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

    if extn.startswith('.xls') or extn in {'.7z', '.gzip', '.hd5'}:
        raise NotImplementedError

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

    if not isinstance(data, str):
        # convert data to string: f.write() is much faster than f.writelines()
        data = repr_(data, concat='\n', quotes=False, wrap=False)

    with open(path, mode, encoding=encoding) as f:
        f.write(data)


def clear_dir(f_dir, allow_not_exist=False):
    f_dir = standardize_dir(f_dir)

    if not os.path.exists(f_dir):
        if allow_not_exist is True:
            return
        else:
            raise FileNotFoundError("cannot clear: '{}', directory does not exist".format(f_dir))

    for file_content in os.listdir(f_dir):
        path = f_dir + file_content

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


def standardize_dir(f_dir, pathsep='/'):
    """ lowercase and make sure directory follows predictable pattern
    pathsep=os.path.sep?
    """
    f_dir = (f_dir.replace('\\', pathsep)
                  .replace('/', pathsep)
                  .lower()
                  .strip())

    if not f_dir.endswith(pathsep):
        f_dir += pathsep

    return f_dir


def standardize_file_name(f_name):
    return f_name.lower().strip()


def standardize_path(path):
    f_dir, f_name = parse_path(path)

    f_dir  = standardize_dir(f_dir)
    f_name = standardize_file_name(f_name)

    return f_dir + f_name


def sanatize_file_name(f_name):
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
        f_name = f_name.replace(k, v)

    f_name = f_name.strip()
    if not f_name:
        raise IOError('file name is blank')

    return f_name


def assert_path_exists(path):
    f_dir, f_name = parse_path(path)

    if not os.path.exists(f_dir):
        raise FileNotFoundError("invalid directory: '{}'".format(f_dir))

    if not os.path.exists(path):
        extn  = file_extension(f_name, include_dot=True)
        retry = f_name.replace(extn, '.*')
        path  = glob(standardize_dir(f_dir) + retry)

        if path:
            retry_name = path[0].split('\\')[-1]
            retry_extn = file_extension(retry_name, include_dot=True)
            msg = "invalid file extension: '{}' (did you mean '{}' ?)".format(extn, retry_extn)
        else:
            msg = "'{}' not found within directory '{}'".format(f_name, f_dir)

        raise FileNotFoundError(msg)


def parse_path(path):

    if os.path.isdir(path):
        f_dir  = path
        f_name = ''
    else:
        f_dir, f_name = os.path.split(path)

    return f_dir, f_name


def file_extension(f_name, include_dot=True):
    _, extn = os.path.splitext(f_name)
    if include_dot is False:
        extn = extn.replace('.', '')

    extn = extn.lower().strip()

    return extn


def apply_file_extension(f_name, extn):
    if not extn.startswith('.'):
        extn = '.' + extn

    if f_name.endswith(extn):
        return f_name

    return f_name + extn


