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

import os

from nose.plugins.attrib import attr

from tests.product.base_product_case import BaseProductTestCase, docker_only
from tests.product.standalone.presto_installer import StandalonePrestoInstaller


class TestServerUpgrade(BaseProductTestCase):

    def setUp(self):
        super(TestServerUpgrade, self).setUp()
        self.setup_cluster(self.STANDALONE_PRESTO_CLUSTER)
        self.installer = StandalonePrestoInstaller(self)

    def start_and_assert_started(self):
        cmd_output = self.run_prestoadmin('server start')
        process_per_host = self.get_process_per_host(cmd_output.splitlines())
        self.assert_started(process_per_host)

    def assert_upgraded_to_dummy_rpm(self, hosts):
        for container in hosts:
            # Still should have the same configs
            self.installer.assert_installed(self, container)
            self.assert_has_default_config(container)
            self.assert_has_default_connector(container)

            # However, dummy_rpm.rpm removes /usr/lib/presto/lib and
            # /usr/lib/presto/lib/plugin
            self.assert_path_removed(container, '/usr/lib/presto/lib')
            self.assert_path_removed(container, '/usr/lib/presto/lib/plugin')

            # And adds /usr/lib/presto/README.txt
            self.assert_path_exists(container, '/usr/lib/presto/README.txt')

            # And modifies the text of the readme in
            # /usr/shared/doc/presto/README.txt
            self.assert_file_content_regex(
                container,
                '/usr/shared/doc/presto/README.txt',
                r'.*New line of text here.$'
            )

    @attr('smoketest')
    def test_upgrade(self):
        self.start_and_assert_started()

        self.run_prestoadmin('configuration deploy')
        for container in self.cluster.all_hosts():
            self.installer.assert_installed(self, container)
            self.assert_has_default_config(container)
            self.assert_has_default_connector(container)

        path_on_cluster = self.copy_upgrade_rpm_to_cluster()
        self.upgrade_and_assert_success(path_on_cluster)

    def upgrade_and_assert_success(self, path_on_cluster):
        self.run_prestoadmin('server upgrade ' + path_on_cluster)
        self.assert_upgraded_to_dummy_rpm(self.cluster.all_hosts())

    @docker_only
    def test_rolling_upgrade(self):
        # Test that if a node is down, and then you upgrade again, it works
        self.run_prestoadmin('configuration deploy')

        self.cluster.stop_host(self.cluster.slaves[0])
        path_on_cluster = self.copy_upgrade_rpm_to_cluster()
        self.run_prestoadmin('server upgrade ' + path_on_cluster)
        running_hosts = self.cluster.all_hosts()[:]
        running_hosts.remove(self.cluster.slaves[0])
        self.assert_upgraded_to_dummy_rpm(running_hosts)

        self.cluster.start_host(self.cluster.slaves[0])
        self.retry(lambda: self.upgrade_and_assert_success(path_on_cluster))

    def copy_upgrade_rpm_to_cluster(self):
        rpm_name = self.installer.copy_presto_rpm_to_master()
        return os.path.join(self.cluster.mount_dir, rpm_name)
