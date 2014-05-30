# coding=utf-8
# vim: tabstop=4 shiftwidth=4 softtabstop=4

#
#    Copyright (c) 2012, Intel Performance Learning Solutions Ltd.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
Network resource backend.
"""

#W0613:unused arguments,R0201:mth could be func,R0903:too few pub mthd.
#W0232:no init
#pylint: disable=W0613,R0201,R0903,W0232


from occi import backend
from occi.extensions import infrastructure

from occi_os_api.nova_glue import neutron


class NetworkBackend(backend.KindBackend, backend.ActionBackend):
    """
    Backend to handle network resources.
    """

    def create(self, entity, extras):
        """
        Creates new network resources.
        """
        ctx = extras['nova_ctx']
        iden = neutron.create_network(ctx)

        entity.identifier = infrastructure.NETWORK.location + iden
        entity.attributes['occi.core.id'] = iden

    def retrieve(self, entity, extras):
        ctx = extras['nova_ctx']
        iden = entity.attributes['occi.core.id']
        tmp = neutron.retrieve_network(ctx, iden)

        entity.attributes = {'occi.core.id': iden,
                             'occi.network.vlan': '1',
                             'occi.network.label': tmp['name'],
                             'occi.network.state': 'active'}

    def update(self, old, new, extras):
        """
        Not supported for now.
        """
        raise AttributeError('Currently not supported.')

    def delete(self, entity, extras):
        """
        Delete a network.
        """
        ctx = extras['nova_ctx']
        iden = entity.attributes['occi.core.id']

        neutron.delete_network(ctx, iden)

    def action(self, entity, action, attributes, extras):
        """
        Currently unsupported.
        """
        # TODO: UP/DOWN actions
        raise AttributeError('Currently not supported.')


class IpNetworkBackend(backend.MixinBackend):
    """
    A mixin backend for the IPnetworking.
    """

    def create(self, entity, extras):
        """
        Add l3 support to the network.
        """
        ctx = extras['nova_ctx']
        iden = entity.attributes['occi.core.id']

        if 'occi.network.address' in entity.attributes:
            cidr = entity.attributes['occi.network.address']
        else:
            cidr = '10.0.0.1/24'

        if 'occi.network.gateway' in entity.attributes:
            gw = entity.attributes['occi.network.gateway']
        else:
            gw = cidr.split('/')[0]

        dyn = True
        if 'occi.network.allocation' in entity.attributes:
            if entity.attributes['occi.network.allocation'] == 'static':
                dyn = False

        neutron.create_subnet(ctx, iden, cidr, gw, dynamic=dyn)

    def retrieve(self, entity, extras):
        """
        Retrieve a network.
        """
        ctx = extras['nova_ctx']
        iden = entity.attributes['occi.core.id']

        tmp = neutron.retrieve_network(ctx, iden)
        subnet_id = tmp['subnets'][0]
        tmp = neutron.retrieve_subnet(ctx, subnet_id)['subnet']

        entity.attributes['occi.network.address'] = tmp['cidr']
        entity.attributes['occi.network.gateway'] = tmp['gateway_ip']
        if tmp['enable_dhcp'] is True:
            entity.attributes['occi.network.allocation'] = 'dynamic'
        else:
            entity.attributes['occi.network.allocation'] = 'static'

    def update(self, old, new, extras):
        """
        Not supported for now.
        """
        raise AttributeError('Currently not supported.')

    def delete(self, entity, extras):
        """
        Remove L3.
        """
        ctx = extras['nova_ctx']
        iden = entity.attributes['occi.core.id']

        tmp = neutron.retrieve_network(ctx, iden)
        subnet_id = tmp['subnets'][0]
        neutron.delete_subnet(ctx, subnet_id)


class NetworkInterfaceBackend(backend.KindBackend):
    """
    A backend for network links.

    Note: Takes care of the kind networkinginterface and the
    mixin ipnetworkinginterface simultaneously.
    """

    def create(self, link, extras):
        """
        create links between:
        a) between VM and network:
           1) port assignment - currently only done on creation (see vm.py).
           2) floating ips.
        b) between networks -> router
        """
        # TODO: attributes
        if link.source.kind == infrastructure.COMPUTE \
                and link.target.kind == infrastructure.NETWORK:
            src = link.source.attributes['occi.core.id']
            trg = link.target.attributes['occi.core.id']
            tmp = neutron.add_floating_ip(extras['nova_ctx'], src, trg)
            if tmp is not None:
                # float ip
                link.attributes['occi.core.id'] = tmp['floatingip']['id']
            else:
                # vnic
                pass
        elif link.source.kind == infrastructure.NETWORK \
                and link.target.kind == infrastructure.NETWORK:
            # router
            # router between two networks
            src = link.source.attributes['occi.core.id']
            trg = link.target.attributes['occi.core.id']
            router = neutron.create_router(extras['nova_ctx'], src, trg)
            link.attributes['occi.core.id'] = router['router']['id']
        else:
            raise AttributeError('Not supported.')

    def retrieve(self, entity, extras):
        """
        Update the attributes of the links.
        """
        # TODO!
        pass

    def update(self, old, new, extras):
        """
        Allows for the update of network links.
        """
        raise AttributeError('Currently not supported.')

    def delete(self, link, extras):
        """
        Remove a floating ip!
        """
        if link.source.kind == infrastructure.COMPUTE and \
                        link.target.kind == infrastructure.NETWORK:
            # remove floating ip.
            neutron.remove_floating_ip(extras['nova_ctx'],
                                       link.attributes['occi.core.id'])
        elif link.source.kind == infrastructure.NETWORK \
                and link.target.kind == infrastructure.NETWORK:
            # router between two networks
            neutron.delete_router(extras['nova_ctx'],
                                  link.attributes['occi.core.id'],
                                  link.source.attributes['occi.core.id'])
        else:
            raise AttributeError('Not supported.')