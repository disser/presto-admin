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
Module for installing prestoadmin on a cluster.
"""

import errno
import fnmatch
import shutil
import os

import prestoadmin

from tests.product.constants import LOCAL_RESOURCES_DIR, \
    BASE_TD_DOCKERFILE_DIR, BASE_IMAGE_NAME, BASE_TD_IMAGE_NAME

from tests.docker_cluster import DockerCluster, DockerClusterException, \
    DEFAULT_LOCAL_MOUNT_POINT, DEFAULT_DOCKER_MOUNT_POINT


class PrestoadminInstaller(object):
    def __init__(self, testcase):
        self.testcase = testcase

    @staticmethod
    def get_dependencies():
        return []

    def install(self, cluster=None, dist_dir=None):
        # Passing in a cluster supports the installation tests. We need to be
        # able to try an installation against an unsupported OS, and for that
        # testcase, we create a cluster that is local to the testcase and then
        # run the install on it. We can't replace self.cluster with the local
        # cluster in the test, because that would prevent the test's "regular"
        # cluster from getting torn down.
        if not cluster:
            cluster = self.testcase.cluster

        if not dist_dir:
            dist_dir = self._build_dist_if_necessary(cluster)
        self._copy_dist_to_host(cluster, dist_dir, cluster.master)
        cluster.copy_to_host(
            LOCAL_RESOURCES_DIR + "/install-admin.sh", cluster.master)
        cluster.exec_cmd_on_host(
            cluster.master,
            'chmod +x ' + cluster.mount_dir + "/install-admin.sh"
        )
        cluster.exec_cmd_on_host(
            cluster.master, cluster.mount_dir + "/install-admin.sh")

    @staticmethod
    def assert_installed(testcase, msg=None):
        cluster = testcase.cluster
        cluster.exec_cmd_on_host(cluster.get_master(),
                                 'test -x /opt/prestoadmin/presto-admin')

    def get_keywords(self):
        return {}

    def _build_dist_if_necessary(self, cluster, unique=False):
        if (not os.path.isdir(cluster.get_dist_dir(unique)) or
                not fnmatch.filter(
                    os.listdir(cluster.get_dist_dir(unique)),
                    'prestoadmin-*.tar.bz2')):
            self._build_installer_in_docker(cluster, unique=unique)
        return cluster.get_dist_dir(unique)

    def _build_installer_in_docker(self, cluster, online_installer=False,
                                   unique=False):
        container_name = 'installer'
        installer_container = DockerCluster(
            container_name, [], DEFAULT_LOCAL_MOUNT_POINT,
            DEFAULT_DOCKER_MOUNT_POINT)
        try:
            installer_container.create_image(
                BASE_TD_DOCKERFILE_DIR,
                BASE_TD_IMAGE_NAME,
                BASE_IMAGE_NAME
            )
            installer_container.start_containers(
                BASE_TD_IMAGE_NAME
            )
        except DockerClusterException as e:
            installer_container.tear_down()
            self.testcase.fail(e.msg)

        try:
            shutil.copytree(
                prestoadmin.main_dir,
                os.path.join(
                    installer_container.get_local_mount_dir(container_name),
                    'presto-admin'),
                ignore=shutil.ignore_patterns('tmp', '.git', 'presto*.rpm')
            )
            installer_container.run_script_on_host(
                '-e\n'
                'pip install --upgrade pip\n'
                'pip install --upgrade wheel\n'
                'pip install --upgrade setuptools\n'
                'mv %s/presto-admin ~/\n'
                'cd ~/presto-admin\n'
                'make %s\n'
                'cp dist/prestoadmin-*.tar.bz2 %s'
                % (installer_container.mount_dir,
                   'dist' if not online_installer else 'dist-online',
                   installer_container.mount_dir),
                container_name)

            try:
                os.makedirs(cluster.get_dist_dir(unique))
            except OSError, e:
                if e.errno != errno.EEXIST:
                    raise
            local_container_dist_dir = os.path.join(
                prestoadmin.main_dir,
                installer_container.get_local_mount_dir(container_name)
            )
            installer_file = fnmatch.filter(
                os.listdir(local_container_dist_dir),
                'prestoadmin-*.tar.bz2')[0]
            shutil.copy(
                os.path.join(local_container_dist_dir, installer_file),
                cluster.get_dist_dir(unique))
        finally:
            installer_container.tear_down()

    @staticmethod
    def _copy_dist_to_host(cluster, local_dist_dir, dest_host):
        for dist_file in os.listdir(local_dist_dir):
            if fnmatch.fnmatch(dist_file, "prestoadmin-*.tar.bz2"):
                cluster.copy_to_host(
                    os.path.join(local_dist_dir, dist_file),
                    dest_host)
