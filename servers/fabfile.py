import os

from fabtools import require, service


def munin_node():
    require.deb.packages(['munin-node'])
    require.users.user(
        'munin-node', 
        shell='/bin/bash', 
        system=True, 
        ssh_public_keys=[os.path.join(os.path.dirname(__file__), 'ssh_key_munin_node.pub')])
    service.restart('munin-node')
