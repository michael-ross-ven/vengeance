
"""
    ./files/example.xlsm, 'invoke python' tab
"""

import os
import sys

from datetime import datetime
from time import sleep

from argparse import ArgumentParser


def parse_cmd_line(fake_cli_str=None):
    print('invoked_from_excel.py')

    if fake_cli_str:
        __add_sys_args(fake_cli_str)

    parser = ArgumentParser()
    parser.add_argument('command')
    parser.add_argument('--content', default='')

    cli_args = parser.parse_args()

    if cli_args.command == 'write_file':
        write_file(cli_args.content)
    elif cli_args.command == 'write_file_and_wait':
        write_file_and_wait(cli_args.content)
    else:
        raise ValueError('invalid command {}'.format(cli_args.command))


def write_file(content):
    f_dir, _ = os.path.split(os.path.realpath(__file__))
    path = f_dir + '\\files\\python_api.txt'

    with open(path, 'w') as f:
        f.write('python script: ' + datetime.now().strftime('%Y-%m-%d %I:%M:%S %p') + ' ' + content)


def write_file_and_wait(content):
    write_file(content)
    print('sleeping ... ')
    sleep(5)


def __add_sys_args(cli_str):
    sys.argv = ['']

    s = cli_str.replace('\n', '')
    for arg in s.split(' ', 2):
        sys.argv.append(arg)


# for debugging in IDE
# parse_cmd_line('write_file_and_wait --content invoke_python_test_1')

parse_cmd_line()
