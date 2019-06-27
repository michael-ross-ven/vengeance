
import os
import csv
import json
import shutil
import _pickle as cpickle

from glob import glob
from datetime import datetime

from . iter import generator_to_list
from . iter import assert_iteration_depth

from . text import repr_
from . text import p_json_dumps


def read_file(path, encoding=None):
    """
    explicitly handled file extensions:
        .csv
        .json
        .flux
        .pkl

    TODO:
        add .xls, .xlsx, .xlsm, .xlsb, .7z, .gzip, .hd5

    (assumes text file if extension not otherwise specified)
    """
    assert_path_exists(path)

    extn = file_extension(path)
    if extn == '.csv':
        with open(path, 'r', encoding=encoding) as f:
            return list(csv.reader(f))

    if extn == '.json':
        with open(path, 'r', encoding=encoding) as f:
            return json.load(f)

    if extn in {'.flux', '.pkl'}:
        with open(path, 'rb') as f:
            return cpickle.load(f)

    with open(path, 'r', encoding=encoding) as f:
        return f.read()


def write_file(path, data, mode='w', encoding=None):
    """
    explicitly handled file extensions:
        .csv
        .json
        .flux
        .pkl

    (assumes text file if extension not otherwise specified)
    """
    extn = file_extension(path)

    if extn == '.csv':
        data = generator_to_list(data, recurse=True)
        assert_iteration_depth(data, 2)
        with open(path, mode, encoding=encoding) as f:
            csv.writer(f, lineterminator='\n').writerows(data)

        return

    if extn == '.json':
        if not isinstance(data, str):
            data = p_json_dumps(data, ensure_ascii=(encoding is None))
        with open(path, mode, encoding=encoding) as f:
            f.write(data)

        return

    if extn in {'.flux', '.pkl'}:
        with open(path, mode + 'b') as f:
            cpickle.dump(data, f)

        return

    if not isinstance(data, str):
        data = repr_(data, concat='\n', quotes=False, wrap=False)
    with open(path, mode, encoding=encoding) as f:
        f.write(data)


def make_dirs(f_dir):
    if not os.path.isdir(f_dir):
        if not os.path.exists(f_dir):
            os.makedirs(f_dir)


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
    f_dir = (f_dir.lower()
                  .replace('\\', pathsep)
                  .replace('/', pathsep)
                  .strip(' \n'))

    if not f_dir.endswith(pathsep):
        f_dir += pathsep

    return f_dir


def standardize_file_name(f_name):
    return (f_name.lower()
                  .strip(' \n'))


def standardize_path(path):
    f_dir, f_name = parse_path(path)
    f_dir  = standardize_dir(f_dir)
    f_name = standardize_file_name(f_name)

    return f_dir + f_name


def sanatize_file_name(f_name):
    if not f_name:
        raise IOError("file name is blank: '{}'".format(f_name))

    invalid_chrs = {'\\': '-',
                    '/':  '-',
                    ':':  '-',
                    '*':  '-',
                    '?':  '-',
                    '<':  '-',
                    '>':  '-',
                    '|':  '-',
                    '"':  '-',
                    "'":  '-'}

    for k, v in invalid_chrs.items():
        f_name = f_name.replace(k, v)

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

    return extn


def apply_file_extension(f_name, extn):
    if f_name.endswith(extn):
        return f_name

    if not extn.startswith('.'):
        extn = '.' + extn

    if not f_name.endswith(extn):
        f_name = f_name + extn

    return f_name


