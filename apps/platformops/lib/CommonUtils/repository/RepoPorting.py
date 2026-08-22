import os
import os.path
import shutil
from distutils.dir_util import copy_tree
from pathlib import Path


def RepoPorting_mkdir(dir_path):
    try:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
        return True
    except OSError as e:
        if e.errno == 17:
            print(f"Directory '{dir_path}' already exists.")
        else:
            print(f"Error creating dghirectory '{dir_path}': {e}")
        return False


def RepoPorting_copy_folder(source_path, destination_path):
    try:
        for file_name in os.listdir(source_path):
            # construct full file path
            source = os.path.join(source_path, file_name)
            destination = os.path.join(destination_path, file_name)
            # copy only files
            if os.path.isfile(source):
                shutil.copy(source, destination)
    except Exception as e:
        print(f"Error occured {e}")


def RepoPorting_copy_dir(source_path, destination_path):
    try:
        copy_tree(source_path, destination_path)
        RepoPorting_delete_dir(source_path)
    except Exception as e:
        print(f"Error occured {e}")


def RepoPorting_delete_file(file_path):
    try:
        # delete only files
        if os.path.isfile(file_path):
            os.remove(file_path)
    except Exception as e:
        print(f"Error occured {e}")


def RepoPorting_delete_dir(dir_path):
    try:
        os.remove(dir_path)
    except Exception as e:
        print(f"Error occured in RepoPorting_delete_dir{e}")
