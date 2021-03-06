#!/usr/bin/env python3
#
# Copyright (C) 2021 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import unittest

from vyos.configsession import ConfigSession
from vyos.ifconfig import Section
from vyos.util import cmd
from vyos.util import process_named_running

PROCESS_NAME = 'ospf6d'
base_path = ['protocols', 'ospfv3']


def getFRROSPFconfig():
    return cmd('vtysh -c "show run" | sed -n "/router ospf6/,/^!/p"')

class TestProtocolsOSPFv3(unittest.TestCase):
    def setUp(self):
        self.session = ConfigSession(os.getpid())

    def tearDown(self):
        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

        self.session.delete(base_path)
        self.session.commit()
        del self.session


    def test_ospfv3_01_basic(self):
        area = '0'
        seq = '10'
        prefix = '2001:db8::/32'
        acl_name = 'foo-acl-100'
        router_id = '192.0.2.1'

        self.session.set(['policy', 'access-list6', acl_name, 'rule', seq, 'action', 'permit'])
        self.session.set(['policy', 'access-list6', acl_name, 'rule', seq, 'source', 'any'])

        self.session.set(base_path + ['parameters', 'router-id', router_id])
        self.session.set(base_path + ['area', area, 'range', prefix, 'advertise'])
        self.session.set(base_path + ['area', area, 'export-list', acl_name])
        self.session.set(base_path + ['area', area, 'import-list', acl_name])

        interfaces = Section.interfaces('ethernet')
        for interface in interfaces:
            self.session.set(base_path + ['area', area, 'interface', interface])

        # commit changes
        self.session.commit()

        # Verify FRR ospfd configuration
        frrconfig = getFRROSPFconfig()
        self.assertIn(f'router ospf6', frrconfig)
        self.assertIn(f' area {area} range {prefix}', frrconfig)
        self.assertIn(f' ospf6 router-id {router_id}', frrconfig)
        self.assertIn(f' area {area} import-list {acl_name}', frrconfig)
        self.assertIn(f' area {area} export-list {acl_name}', frrconfig)

        for interface in interfaces:
            self.assertIn(f' interface {interface} area {area}', frrconfig)

        self.session.delete(['policy', 'access-list6', acl_name])


    def test_ospfv3_02_distance(self):
        dist_global = '200'
        dist_external = '110'
        dist_inter_area = '120'
        dist_intra_area = '130'

        self.session.set(base_path + ['distance', 'global', dist_global])
        self.session.set(base_path + ['distance', 'ospfv3', 'external', dist_external])
        self.session.set(base_path + ['distance', 'ospfv3', 'inter-area', dist_inter_area])
        self.session.set(base_path + ['distance', 'ospfv3', 'intra-area', dist_intra_area])

        # commit changes
        self.session.commit()

        # Verify FRR ospfd configuration
        frrconfig = getFRROSPFconfig()
        self.assertIn(f'router ospf6', frrconfig)
        self.assertIn(f' distance {dist_global}', frrconfig)
        self.assertIn(f' distance ospf6 intra-area {dist_intra_area} inter-area {dist_inter_area} external {dist_external}', frrconfig)


    def test_ospfv3_03_redistribute(self):
        route_map = 'foo-bar'
        route_map_seq = '10'
        redistribute = ['bgp', 'connected', 'kernel', 'ripng', 'static']

        self.session.set(['policy', 'route-map', route_map, 'rule', route_map_seq, 'action', 'permit'])

        for protocol in redistribute:
            self.session.set(base_path + ['redistribute', protocol, 'route-map', route_map])

        # commit changes
        self.session.commit()

        # Verify FRR ospfd configuration
        frrconfig = getFRROSPFconfig()
        self.assertIn(f'router ospf6', frrconfig)
        for protocol in redistribute:
            self.assertIn(f' redistribute {protocol} route-map {route_map}', frrconfig)


if __name__ == '__main__':
    unittest.main(verbosity=2)
