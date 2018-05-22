#!/usr/bin/python
from __future__ import print_function
__author__ = 'effie mouzeli'
import argparse
import os
import shutil
import time
import hashlib
import sys
import subprocess
from shutil import move

# NOTE: This script assumes that latest/, current/, archive/ directories are present
# TODO: Remove jar from variable names, use "jar" extention as default though
# TODO: Try dbus
# TODO: check if service exists before performing any actions
# TODO: Fix arguments

global LATEST_DIR, ARCHIVE_DIR, CURRENT_DIR, TMP_DIR
DEFAULT_PATH = '/etc/default'
APP_DATA = {}


def set_global_vars(app_id):
    # Read /etc/default/app_id and get paths
    global LATEST_DIR, ARCHIVE_DIR, CURRENT_DIR, APP_DATA
    try:
        with open(os.path.join(DEFAULT_PATH, app_id)) as default_file:
            for line in default_file:
                line_ = line.rstrip('\n').split("=")
                if line_[0] in ['BINARY', 'APP_ROOT', 'PORT']:
                    APP_DATA[line_[0].lower()] = line_[1].strip('"')
        LATEST_DIR = '{0}/latest'.format(APP_DATA['app_root'])
        ARCHIVE_DIR = '{0}/archive'.format(APP_DATA['app_root'])
        CURRENT_DIR = '{0}/current'.format(APP_DATA['app_root'])
    except EnvironmentError:
        print('Application {0} is not here, file {1} does not exist.\n'.format(app_id, os.path.join(DEFAULT_PATH, app_id)))
        sys.exit(1)


def calc_md5(file_):
    with open(file_, "rb") as this_file:
        md5 = hashlib.md5()
        while True:
            bf = this_file.read(1024)
            if not bf:
                break
            md5.update(bf)
    return md5.hexdigest()


def service_status(service):
    status_cmd = '/bin/systemctl status {0}.service'.format(service)
    status_run = subprocess.Popen(status_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    status_out = status_run.communicate()
    status_err = status_out[1].decode("utf-8")
    if 'could not be found' in status_err:
        print('\nService COULD NOT be found, have you run systemctl daemon-reload?\n')
        sys.exit(1)
    status_std = status_out[0].decode("utf-8").split('\n')# Python3 compatibility
    for line in status_std:
        if 'Active:' in line:
            if '(running)' in line:
                return True
            else:
                return False


# Pass commands to systemd

def systemd(command, service):
    # Check service status, if service does not exist, we exit.
    status = service_status(service)
    if command == 'status':
        return service_status(service)
    if command == "stop":
        if status:
            stop_cmd = '/bin/systemctl stop {0}.service'.format(service)
            stop_run = subprocess.Popen(stop_cmd, shell=True, stdout=subprocess.PIPE)
            stop_run.communicate()
            print('Service {0} stopped'.format(service))
            return True
        else:
            print('Service {0} is already stopped'.format(service))
            return False
    if command == "start":
        if status:
            print('Service {0} is already running'.format(service))
            return False
        else:
            start_cmd = '/bin/systemctl start {0}.service'.format(service)
            start_run = subprocess.Popen(start_cmd, shell=True, stdout=subprocess.PIPE)
            start_run.communicate()
            if service_status(service):
                print('Service {0} started'.format(service))
                return True
            else:
                print('Service {0} did NOT start'.format(service))
                # This is bad, we exit
                sys.exit(1)


# Only check files with "jar" and "app_id" in their filename
# Returns an ordered list of matching files, Index 0 being the newest.

def order_files(path, app_id, type_="jar"):
    mtime = lambda file_: os.stat(os.path.join(path, file_)).st_mtime
    file_list = list(sorted(os.listdir(path), key=mtime, reverse=True))
    for f in list(file_list):
        if type_ not in f:
            file_list.remove(f)
        else:
            if app_id not in f:
                file_list.remove(f)
    return file_list


# Compare the newest file in /tmp with the newest in latest/
# Returns a source_file, destination_file tuple or exits if there is nothing to do
# destination filename formati is app_id-build_id.jar

def find_candidate_files(app_id, build_id, type_="jar"):
    destination = os.path.join(LATEST_DIR, '{0}-{1}.{2}'.format(app_id, build_id, type_))
    try:
        source = os.path.join(TMP_DIR, order_files(TMP_DIR, app_id)[0])
    except IndexError:
        print('No deployment candidates found in {0}, exiting'.format(TMP_DIR))
        sys.exit(1)
    try:
        latest = os.path.join(LATEST_DIR, order_files(LATEST_DIR, app_id)[0])
        source_hash = calc_md5(source)
        latest_hash = calc_md5(latest)
    except IndexError:
        print('{0} is empty, this is First Deployment'.format(LATEST_DIR))
        return source, destination
    if source_hash == latest_hash:
        print(source_hash, source)
        print(latest_hash, latest)
        print('Nothing to deploy, source file in {0} is same as {1}'.format(source, latest))
        return False
    else:
        return source, destination


def cleanup(archive_dir_, latest_dir_, app_id):
    # TODO: make sure that ARCHIVE_DIR has only the 2 newest files
    latest_jars = order_files(latest_dir_, app_id_)
    archive_jars = order_files(archive_dir_, app_id)
    try:
        for file_ in archive_jars[1:]:
            os.remove(os.path.join(archive_dir_, file_))
    except IndexError:
        print('Nothing to remove in {0}'.format(archive_dir_))
        pass
    try:
        for file_ in latest_jars[3:]:
            os.remove(os.path.join(latest_dir_, file_ ))
    except IndexError:
        print('Nothing to remove in {0}'.format(latest_dir_))
        pass
    try:
        print('moving {0} to {1}'.format(os.path.join(latest_dir_, latest_jars[2]), os.path.join(archive_dir_, latest_jars[2])))
        move(os.path.join(latest_dir_, latest_jars[2]), os.path.join(archive_dir_, latest_jars[2]))
    except IndexError:
        print('Nothing to move from latest to archive')
        pass


# Copy from TMP_DIR to LATEST_DIR
def copy_to_latest(src_dest):
    source = src_dest[0]
    destination = src_dest[1]
    try:
        shutil.copyfile(source, destination)
        print('Copying {0} to {1}'.format(source, destination))
        return True
    except shutil.Error:
        print("Destination file exists or something bad happened")
        return True # test


def create_symlink(current_jar, latest_jar):
    try:
        if os.readlink(current_jar) == latest_jar:
            print('Symlink {0} points to {1}, nothing to do'.format(current_jar, latest_jar))
            return False
        else:
            os.remove(current_jar)
            os.symlink(latest_jar, current_jar)
            print('Symlinked {0} to {1}'.format(current_jar, latest_jar))
            return True
    except OSError:
        os.symlink(latest_jar, current_jar)
        print('Created new symlink {0} to {1}'.format(current_jar, latest_jar))
        return True


# Actions

# Returns false if no files were copied
def copy_only(app_id, build_id):
    src_dest_ = find_candidate_files(app_id, build_id)
    if src_dest_:
        return copy_to_latest(src_dest_)
    else:
        return False


def link_only(current_jar, app_id):
    latest_jar = os.path.join(LATEST_DIR, order_files(LATEST_DIR, app_id)[0])
    create_symlink(current_jar, latest_jar)


def latest_build(current_jar, app_id, build_id):
    if copy_only(app_id, build_id):
        systemd("stop", app_id)
        link_only(current_jar, app_id)
        systemd("start", app_id)
        cleanup(ARCHIVE_DIR, LATEST_DIR, app_id)
    else:
        latest_jar = os.path.join(LATEST_DIR, order_files(LATEST_DIR, app_id)[0])
        if os.readlink(current_jar) == latest_jar:
            systemd("start", app_id)
            cleanup(ARCHIVE_DIR, LATEST_DIR, app_id)
        else:
            if systemd("status", app_id_):
                systemd("stop", app_id)
            link_only(current_jar, app_id)
            systemd("start", app_id)
            cleanup(ARCHIVE_DIR, LATEST_DIR, app_id)


build_number = time.strftime('%Y%m%d%H%M%S')
parser = argparse.ArgumentParser()
parser.add_argument("action", choices=['copy_only', 'link_only', 'latest_build', 'cleanup'], type=str, help="action")
parser.add_argument("arg_app_id", type=str, help="application id")
parser.add_argument('-bid', '--buildid', action="store", dest="bid", default=build_number)
parser.add_argument('-sd', '--searchdir', action="store", default='/tmp')

if __name__ == "__main__":
    print('')
    args = parser.parse_args()
    action = args.action
    app_id_ = args.arg_app_id
    build_id_ = args.bid
    TMP_DIR = args.searchdir
    set_global_vars(app_id_)
    current_jar_ = os.path.join(CURRENT_DIR, APP_DATA['binary'])
    if args.action == "latest_build":
        latest_build(current_jar_, app_id_, build_id_)
    if args.action == "copy_only":
        copy_only(app_id_, build_id_)
    if args.action == "link_only":
        link_only(current_jar_, app_id_)
    if args.action == "cleanup":
        cleanup(ARCHIVE_DIR, LATEST_DIR, app_id_)
    print('')
