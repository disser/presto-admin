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
Module for managing presto/YARN integration.
"""

import os.path

from fabric.api import env, task, abort
from fabric.decorators import runs_once
from fabric.operations import put, sudo
from fabric.tasks import execute

from prestoadmin.slider.config import requires_conf, DIR, SLIDER_MASTER

from prestoadmin.util.fabricapi import get_host_list, task_by_rolename

__all__ = ['slider_install', 'slider_uninstall']


@task
@requires_conf
@runs_once
def slider_install(slider_tarball):
    """
    Install slider on the slider master. You must provide a tar file on the
    local machine that contains the slider distribution.

    :param slider_tarball:
    """
    execute(deploy_install, slider_tarball, hosts=get_host_list())


def deploy_install(slider_tarball):
    slider_dir = env.conf[DIR]
    slider_parent = os.path.dirname(slider_dir)
    slider_file = os.path.join(slider_parent, os.path.basename(slider_tarball))

    sudo('mkdir -p %s' % (slider_dir))

    result = put(slider_tarball, os.path.join(slider_parent, slider_file))
    if result.failed:
        abort('Failed to send slider tarball to directory %s on host %s' %
              (slider_tarball, slider_dir, env.host))

    sudo('gunzip -c %s | tar -x -C %s --strip-components=1 && rm -f %s' %
         (slider_file, slider_dir, slider_file))


@task
@requires_conf
@task_by_rolename(SLIDER_MASTER)
def slider_uninstall():
    """
    Uninstall slider from the slider master.
    """
    sudo('rm -r "%s"' % (env.conf[DIR]))
