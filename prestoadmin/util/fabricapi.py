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
Module to add extensions and helpers for fabric api methods
"""

from functools import wraps

from fabric.api import env
from fabric.utils import abort


def get_host_list():
    return [host for host in env.hosts if host not in env.exclude_hosts]


def get_coordinator_role():
    return env.roledefs['coordinator']


def get_worker_role():
    return env.roledefs['worker']


def task_by_rolename(rolename):
    def inner_decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            by_rolename(env.host, rolename, f, *args, **kwargs)
        return wrapper
    return inner_decorator


def by_rolename(host, rolename, f, *args, **kwargs):
    if rolename is None:
        f(*args, **kwargs)
    else:
        if rolename not in env.roledefs.keys():
            abort("Invalid role name %s. Valid rolenames are %s" %
                  (rolename, env.roledefs.keys()))
        if host in env.roledefs[rolename]:
            f(*args, **kwargs)


def by_role_coordinator(host, f, *args, **kwargs):
    if host in get_coordinator_role():
        f(*args, **kwargs)


def by_role_worker(host, f, *args, **kwargs):
    if host in get_worker_role() and host not in get_coordinator_role():
        f(*args, **kwargs)
