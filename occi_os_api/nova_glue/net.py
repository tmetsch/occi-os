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
Nova Network related 'glue' :-)
"""

import logging

from nova import compute

from occi_os_api.nova_glue import vm

# Connect to nova :-)

NETWORK_API = compute.API().network_api


LOG = logging.getLogger(__name__)


def get_network_details(uid, context):
    """
    Extracts the VMs network adapter information.

    uid -- Id of the VM.
    context -- The os context.
    """
    vm_instance = vm.get_vm(uid, context)
    result = []

    for item in NETWORK_API.get_instance_nw_info(context, vm_instance):
        result.append({'vif': item['id'], 'net_id': item['network']['id']})

    return result
