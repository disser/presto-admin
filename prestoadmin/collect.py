# -*- coding: utf-8 -*-
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


"""
Module for gathering various debug information for incident reporting
using presto-admin
"""

import logging
import json
import shutil
import tarfile

import requests
from fabric.contrib.files import exists, append
from fabric.context_managers import settings, hide
from fabric.operations import os, get, run
from fabric.tasks import execute
from fabric.api import env, runs_once, task
from fabric.utils import abort, warn

from prestoadmin.prestoclient import PrestoClient
from prestoadmin.topology import requires_topology
from prestoadmin.server import get_presto_version, get_connector_info_from
import prestoadmin.util.fabricapi as fabricapi
import prestoadmin
from util.constants import REMOTE_PRESTO_LOG_DIR, PRESTOADMIN_LOG_DIR


TMP_PRESTO_DEBUG = '/tmp/presto-debug/'
OUTPUT_FILENAME_FOR_LOGS = '/tmp/presto-debug-logs.tar.bz2'
OUTPUT_FILENAME_FOR_SYS_INFO = '/tmp/presto-debug-sysinfo.tar.bz2'
PRESTOADMIN_LOG_NAME = 'presto-admin.log'
_LOGGER = logging.getLogger(__name__)
QUERY_REQUEST_URL = "http://localhost:8080/v1/query/"
NODES_REQUEST_URL = "http://localhost:8080/v1/node"

__all__ = ['logs', 'query_info', 'system_info']


@task
@runs_once
def logs():
    """
    Gather all the server logs and presto-admin log and create a tar file.
    """

    _LOGGER.debug('LOG directory to be archived: ' + REMOTE_PRESTO_LOG_DIR)

    if not os.path.exists(TMP_PRESTO_DEBUG):
        os.mkdir(TMP_PRESTO_DEBUG)

    downloaded_logs_location = os.path.join(TMP_PRESTO_DEBUG, "logs")

    if not os.path.exists(downloaded_logs_location):
        os.mkdir(downloaded_logs_location)

    print 'Downloading logs from all the nodes...'
    execute(file_get, REMOTE_PRESTO_LOG_DIR,
            downloaded_logs_location, roles=env.roles)

    copy_admin_log(downloaded_logs_location)

    make_tarfile(OUTPUT_FILENAME_FOR_LOGS, downloaded_logs_location)
    print 'logs archive created: ' + OUTPUT_FILENAME_FOR_LOGS


def copy_admin_log(log_folder):
    shutil.copy(os.path.join(PRESTOADMIN_LOG_DIR, PRESTOADMIN_LOG_NAME),
                log_folder)


def make_tarfile(output_filename, source_dir):
    tar = tarfile.open(output_filename, 'w:bz2')

    try:
        tar.add(source_dir, arcname=os.path.basename(source_dir))
    finally:
        tar.close()


def file_get(remote_path, local_path):
    path_with_host_name = os.path.join(local_path, env.host)

    if not os.path.exists(path_with_host_name):
        os.makedirs(path_with_host_name)

    _LOGGER.debug('local path used ' + path_with_host_name)

    if exists(remote_path, True):
        get(remote_path, path_with_host_name, True)
    else:
        warn('remote path ' + remote_path + ' not found on ' + env.host)


@task
@requires_topology
def query_info(query_id):
    """
    Gather information about the query identified by the given
    query_id and store that in a JSON file.

    Parameters:
        query_id - id of the query for which info has to be gathered
    """

    if env.host not in fabricapi.get_coordinator_role():
        return

    err_msg = 'Unable to retrieve information. Please check that the ' \
              'query_id is correct, or check that server is up with ' \
              'command: server status'

    req = get_request(QUERY_REQUEST_URL + query_id, err_msg)

    query_info_file_name = os.path.join(TMP_PRESTO_DEBUG,
                                        'query_info_' + query_id + '.json')

    if not os.path.exists(TMP_PRESTO_DEBUG):
        os.mkdir(TMP_PRESTO_DEBUG)

    with open(query_info_file_name, 'w') as out_file:
        out_file.write(json.dumps(req.json(), indent=4))

    print('Gathered query information in file: ' + query_info_file_name)


def get_request(url, err_msg):
        try:
            req = requests.get(url)
        except requests.ConnectionError:
            abort(err_msg)

        if not req.status_code == requests.codes.ok:
            abort(err_msg)

        return req


@task
@runs_once
def system_info():
    """
    Gather system information like nodes in the system, presto
    version, presto-admin version, os version etc.
    """
    err_msg = 'Unable to access node information. ' \
              'Please check that server is up with command: server status'
    req = get_request(NODES_REQUEST_URL, err_msg)

    if not os.path.exists(TMP_PRESTO_DEBUG):
        os.mkdir(TMP_PRESTO_DEBUG)

    downloaded_sys_info_loc = os.path.join(TMP_PRESTO_DEBUG, "sysinfo")
    node_info_file_name = os.path.join(downloaded_sys_info_loc,
                                       'node_info.json')

    if not os.path.exists(downloaded_sys_info_loc):
        os.mkdir(downloaded_sys_info_loc)

    with open(node_info_file_name, 'w') as out_file:
        out_file.write(json.dumps(req.json(), indent=4))

    _LOGGER.debug('Gathered node information in file: ' + node_info_file_name)

    conn_file_name = os.path.join(downloaded_sys_info_loc,
                                  'connector_info.txt')
    client = PrestoClient(env.host, env.user)
    conn_info = get_connector_info_from(client)

    with open(conn_file_name, 'w') as out_file:
        out_file.write(conn_info + '\n')

    _LOGGER.debug('Gathered connector information in file: ' + conn_file_name)

    execute(get_system_info, downloaded_sys_info_loc, roles=env.roles)

    make_tarfile(OUTPUT_FILENAME_FOR_SYS_INFO, downloaded_sys_info_loc)
    print 'System info archive created: ' + OUTPUT_FILENAME_FOR_SYS_INFO


def get_system_info(download_location):

    if not exists(TMP_PRESTO_DEBUG):
        run("mkdir " + TMP_PRESTO_DEBUG)

    version_file_name = os.path.join(TMP_PRESTO_DEBUG, 'version_info.txt')

    if exists(version_file_name):
        run('rm -f ' + version_file_name)

    append(version_file_name, "platform information : " +
           get_platform_information() + '\n')
    append(version_file_name, 'Java version: ' + get_java_version() + '\n')
    append(version_file_name, 'Presto-admin version: '
           + prestoadmin.__version__ + '\n')
    append(version_file_name, 'Presto server version: '
           + get_presto_version() + '\n')

    _LOGGER.debug('Gathered version information in file: ' + version_file_name)

    file_get(version_file_name, download_location)


def get_platform_information():
    with settings(hide('warnings', 'stdout'), warn_only=True):
        platform_info = run('uname -a')
        _LOGGER.debug('platform info: ' + platform_info)
        return platform_info


def get_java_version():
    with settings(hide('warnings', 'stdout'), warn_only=True):
        version = run('java -version')
        _LOGGER.debug('java version: ' + version)
        return version
