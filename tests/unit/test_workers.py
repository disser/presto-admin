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
Tests the workers module
"""
from fabric.api import env
from mock import patch

from prestoadmin import workers
from prestoadmin.util.exception import ConfigurationError
from tests.base_test_case import BaseTestCase


class TestWorkers(BaseTestCase):
    def test_build_defaults(self):
        env.roledefs['coordinator'] = 'a'
        env.roledefs['workers'] = ['b', 'c']
        actual_default = workers.build_defaults()
        expected = {'node.properties':
                    {'node.environment': 'presto',
                     'node.data-dir': '/var/lib/presto/data',
                     'plugin.config-dir': '/etc/presto/catalog',
                     'plugin.dir': '/usr/lib/presto/lib/plugin'},
                    'jvm.config': ['-server',
                                   '-Xmx2G',
                                   '-XX:-UseBiasedLocking',
                                   '-XX:+UseG1GC',
                                   '-XX:+ExplicitGCInvokesConcurrent',
                                   '-XX:+HeapDumpOnOutOfMemoryError',
                                   '-XX:+UseGCOverheadLimit',
                                   '-XX:OnOutOfMemoryError=kill -9 %p',
                                   '-DHADOOP_USER_NAME=hive'],
                    'config.properties': {'coordinator': 'false',
                                          'discovery.uri': 'http://a:8080',
                                          'http-server.http.port': '8080',
                                          'query.max-memory': '50GB',
                                          'query.max-memory-per-node': '1GB'}
                    }

        self.assertEqual(actual_default, expected)

    def test_validate_valid(self):
        conf = {'node.properties': {},
                'jvm.config': [],
                'config.properties': {'coordinator': 'false',
                                      'discovery.uri': 'http://host:8080'}}

        self.assertEqual(conf, workers.validate(conf))

    def test_validate_default(self):
        env.roledefs['coordinator'] = 'localhost'
        conf = workers.build_defaults()
        self.assertEqual(conf, workers.validate(conf))

    def test_invalid_conf(self):
        conf = {'node.propoerties': {}}
        self.assertRaisesRegexp(ConfigurationError,
                                'Missing configuration for required file: ',
                                workers.validate, conf)

    def test_invalid_conf_coordinator(self):
        conf = {'node.properties': {},
                'jvm.config': [],
                'config.properties': {'coordinator': 'true',
                                      'discovery.uri': 'http://uri'}
                }

        self.assertRaisesRegexp(ConfigurationError,
                                'Coordinator must be false in the '
                                'worker\'s config.properties',
                                workers.validate, conf)

    @patch('prestoadmin.workers._get_conf')
    def test_get_conf_empty_is_default(self, get_conf_mock):
        env.roledefs['coordinator'] = ['j']
        get_conf_mock.return_value = {}
        self.assertEqual(workers.get_conf(), workers.build_defaults())

    @patch('prestoadmin.workers.get_presto_conf')
    def test_get_conf(self, get_presto_conf_mock):
        env.roledefs['coordinator'] = ['j']
        file_conf = {'node.properties': {'my-property': 'value',
                                         'node.environment': 'test'}}
        get_presto_conf_mock.return_value = file_conf
        expected = {'node.properties':
                    {'my-property': 'value',
                     'node.environment': 'test',
                     'node.data-dir': '/var/lib/presto/data',
                     'plugin.config-dir': '/etc/presto/catalog',
                     'plugin.dir': '/usr/lib/presto/lib/plugin'},
                    'jvm.config': ['-server',
                                   '-Xmx2G',
                                   '-XX:-UseBiasedLocking',
                                   '-XX:+UseG1GC',
                                   '-XX:+ExplicitGCInvokesConcurrent',
                                   '-XX:+HeapDumpOnOutOfMemoryError',
                                   '-XX:+UseGCOverheadLimit',
                                   '-XX:OnOutOfMemoryError=kill -9 %p',
                                   '-DHADOOP_USER_NAME=hive'],
                    'config.properties': {'coordinator': 'false',
                                          'discovery.uri': 'http://j:8080',
                                          'http-server.http.port': '8080',
                                          'query.max-memory': '50GB',
                                          'query.max-memory-per-node': '1GB'}
                    }
        self.assertEqual(workers.get_conf(), expected)

    @patch('prestoadmin.workers._get_conf')
    @patch('prestoadmin.workers.util.get_coordinator_role')
    def test_worker_not_localhost(self, coord_mock, get_conf_mock):
        get_conf_mock.return_value = {}
        coord_mock.return_value = ['localhost']
        env.roledefs['all'] = ['localhost', 'remote-host']
        self.assertRaisesRegexp(ConfigurationError,
                                'discovery.uri should not be localhost in a '
                                'multi-node cluster', workers.get_conf)

    def test_invalid_discovery_uri(self):
        conf = {'node.properties': {},
                'jvm.config': [],
                'config.properties': {'coordinator': 'false'}
                }

        self.assertRaisesRegexp(ConfigurationError,
                                'Must have discovery.uri defined in '
                                'config.properties.',
                                workers.validate, conf)
        conf['config.properties']['discovery.uri'] = 'thrift://foo'
        self.assertRaisesRegexp(ConfigurationError,
                                'discovery.uri must start with http://, '
                                'current URI is: thrift://foo',
                                workers.validate, conf)
