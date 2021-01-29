#!/usr/bin/env python3
#
# Copyright (C) 2020 VyOS maintainers and contributors
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

import jmespath
import json
import os

from sys import exit
from netifaces import interfaces

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.template import render
from vyos.util import cmd
from vyos.util import check_kmod
from vyos.util import dict_search
from vyos.template import is_ipv6
from vyos.template import is_ipv4
from vyos.xml import defaults
from vyos import ConfigError
from vyos import airbag
airbag.enable()

lvs_config='/tmp/ipvsadm.rules'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    
    base = ['load-balancing','backend']
    conf = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)
    
    if 'rule' in conf:
        default_values = defaults(base + ['rule'])
        for rule in conf['rule']:
            conf['rule'][rule] = dict_merge(default_values,conf['rule'][rule])
    
    return conf

def verify(config):
    if not config:
        return None
    
    if 'rule' in config:
        ip_type = None
        for rule,rule_config in conf['rule'].items():
            if 'disable' in rule_config or 'virtual_ip' in rule_config or 'virtual_port' in rule_config:
                continue
            
            err_msg = f'Error in the configuration of rule {rule}. '
            
            if not ip_type:
                if is_ipv4(rule_config['virtual_ip']):
                    ip_type = 4
                elif is_ipv6(rule_config['virtual_ip']):
                    ip_type = 6
            else:
                if 'backend' in rule_config:
                    for backend,backend_config in rule_config['backend'].items():
                        if 'disable' in backend_config or 'backend_ip' in backend_config or 'backend_port' in backend_config:
                            return None
                        
                        if (ip_type == 4 and not is_ipv4(backend_config['backend_ip'])) or (ip_type == 6 and not is_ipv6(backend_config['backend_ip'])):
                            raise ConfigError(err_msg + f'The IP of the backend server {backend} of rule {rule} must be in the same address family as the virtual server IP')
            
            if 'algorithm' not in rule_config and 'mode' in rule_config:
                raise ConfigError(err_msg + 'mode and algorithm must be configured')
            
            if dict_search('mode',rule_config) == 'tun' and dict_search('tun_option.type',rule_config) =='gue' and not dict_search('tun_option.port',rule_config):
                raise ConfigError(err_msg + 'Port specification is required if GUE tunneling is used in lvs-tun mode')

def generate(config):
    if not config:
        return None
    
    render(lvs_config, 'load-balancing/ipvsadm.rules.tmpl', config, permission=0o644)

def apply(config):
    if not config:
        return None
    
    if os.path.isfile(lvs_config):
        cmd(f'ipvsadm -R < {lvs_config}')
        os.unlink(lvs_config)

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
