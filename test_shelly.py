#!/usr/bin/python

import unittest
import shlex
import shelly


class ShellyTest(unittest.TestCase):

    def test_cmd_pkg(self):
        cmd = shelly.cmd_pkg(['install', 'bar'])
        res = {
            '.pkg.bar': {
                'pkg.installed': [
                    {'name': 'bar'}
                ]
            }
        }
        self.assertDictEqual(cmd, res)

    def test_cmd_mkdir(self):
        cmd = shelly.cmd_mkdir(shlex.split(
            '-m 0750 bar'
        ))
        res = {
            '.file.bar': {
                'file.directory': [
                    {'name': 'bar'},
                    {'mode': '0750'}
                ]
            }
        }
        self.assertDictEqual(cmd, res)

    def test_cmd_chown(self):
        cmd = shelly.cmd_chown(shlex.split(
            'user:group /tmp/bar'
        ))
        res = {
            '.file./tmp/bar': {
                'file.directory': [
                    {'name': '/tmp/bar'},
                    {'user': 'user'},
                    {'group': 'group'}
                ]
            }
        }
        self.assertDictEqual(cmd, res)

    def test_cmd_curl(self):
        cmd = shelly.cmd_curl(shlex.split(
            'salt://influxdb/f.j2 | jinja > /tmp/f'
        ))
        res = {
            '.file./tmp/f': {
                'file.managed': [
                    {'source': 'salt://influxdb/f.j2'},
                    {'template': 'jinja'},
                    {'name': '/tmp/f'},
                ]
            }
        }
        self.assertDictEqual(cmd, res)

    def test_cmd_curl_hash(self):
        cmd = shelly.cmd_curl(shlex.split(
            '--hash sha256=123 salt://influxdb/f.j2 > /tmp/f'
        ))
        res = {
            '.file./tmp/f': {
                'file.managed': [
                    {'source_hash': 'sha256=123'},
                    {'source': 'salt://influxdb/f.j2'},
                    {'name': '/tmp/f'},
                ]
            }
        }
        self.assertDictEqual(cmd, res)

    def test_cmd_useradd(self):
        self.maxDiff = None
        cmd = shelly.cmd_useradd(shlex.split(
            '-d /opt/influxdb -s /bin/bash -c InfluxDBServiceUser influxdb'
        ))
        res = {
            '.user.influxdb': {
                'user.present': [
                    {'home': '/opt/influxdb'},
                    {'shell': '/bin/bash'},
                    {'fullname': 'InfluxDBServiceUser'},
                    {'name': 'influxdb'},
                ]
            }
        }
        self.assertDictEqual(cmd, res)

    def test_cmd_iptables(self):
        cmd = shelly.cmd_iptables(shlex.split(
            '-P INPUT DROP --comment "default drop"'
        ))
        res = {
            '.iptables.default drop': {
                'iptables.set_policy': [
                    {'chain': 'INPUT'},
                    {'policy': 'DROP'},
                    {'save': True},
                ]
            }
        }
        self.assertDictEqual(cmd, res)

    def test_cmd_systemctl_start(self):
        cmd = shelly.cmd_systemctl(shlex.split(
            'start postfix dovecot'
        ))
        res = {
            '.svc.postfix': {
                'service.running': [
                    {'name': 'postfix'},
                ]
            },
            '.svc.dovecot': {
                'service.running': [
                    {'name': 'dovecot'},
                ]
            },
        }
        self.assertDictEqual(cmd, res)

    def test_cmd_systemctl_enabled(self):
        cmd = shelly.cmd_systemctl(shlex.split(
            'enable postfix dovecot'
        ))
        res = {
            '.svc.postfix': {
                'service.enabled': [
                    {'name': 'postfix'},
                    {'enable': True},
                ]
            },
            '.svc.dovecot': {
                'service.enabled': [
                    {'name': 'dovecot'},
                    {'enable': True},
                ]
            },
        }
        self.assertDictEqual(cmd, res)

    def test_cmd_ldso(self):
        cmd = shelly.cmd_ldso(['/sbin/foo', 'bar'])
        self.assertDictEqual(cmd,
                             {'/sbin/foo bar': 'cmd.run'})

    def test_merge_resources(self):
        new = {
            '.svc.postfix': {
                'service.enabled': [
                    {'name': 'postfix'},
                ]
            }
        }
        merging = {
            '.svc.dovecot': {
                'service.enabled': [
                    {'name': 'dovecot'},
                ]
            },
        }
        shelly.merge_resources(new, merging)
        res = {
            '.svc.postfix': {
                'service.enabled': [
                    {'name': 'postfix'},
                ]
            },
            '.svc.dovecot': {
                'service.enabled': [
                    {'name': 'dovecot'},
                ]
            },
        }
        self.assertDictEqual(merging, res)

    def test_merge_resources_file(self):
        new = {
            '.file./tmp/a': {
                'file.directory': [
                    {'name': '/tmp/a'},
                    {'user': 'gerhard'},
                    {'group': 'gerhard'},
                ]
            }
        }
        merging = {
            '.file./tmp/a': {
                'file.managed': [
                    {'name': '/tmp/a'},
                    {'source': 'salt://a'},
                ]
            },
        }
        shelly.merge_resources(new, merging)
        res = {
            '.file./tmp/a': {
                'file.managed': [
                    {'name': '/tmp/a'},
                    {'source': 'salt://a'},
                    {'user': 'gerhard'},
                    {'group': 'gerhard'},
                ]
            },
        }
        self.assertDictEqual(merging, res)


if __name__ == '__main__':
    unittest.main()
