# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import json
import os


def get_data_path(
        script_path: str,
        data_path: str,
) -> str:
    """
    Get full data path for open function to read
    """
    dir_name = os.path.dirname(os.path.realpath(script_path))
    return os.path.join(dir_name, data_path)


def load_file(
        script_path: str,
        data_path: str,
):
    """
    Load binary data from the specified path
    """
    with open(get_data_path(script_path, data_path), 'rb') as fp:
        return fp.read()


def load_json(
        script_path: str,
        data_path: str,
):
    """
    Load json data from the specified path
    """
    with open(get_data_path(script_path, data_path), 'r') as fp:
        return json.load(fp)
