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
VM related 'glue' :-)
"""

#pylint: disable=R0914,W0142,R0912,R0915

from nova import compute
from nova import utils
from nova.compute import task_states
from nova.compute import vm_states
from nova.compute import flavors
from nova.openstack.common import log

from occi import exceptions
from occi.extensions import infrastructure

from occi_os_api.extensions import os_mixins
from occi_os_api.extensions import os_addon

COMPUTE_API = compute.API()

LOG = log.getLogger(__name__)


def create_vm(entity, context):
    """
    Create a VM for an given OCCI entity.

    entity -- the OCCI resource entity.
    context -- the os context.
    """
    # TODO: needs major overhaul!

    if 'occi.compute.hostname' in entity.attributes:
        name = entity.attributes['occi.compute.hostname']
    else:
        name = None
    key_name = key_data = None
    password = utils.generate_password()
    access_ip_v4 = None
    access_ip_v6 = None
    user_data = None
    metadata = {}
    injected_files = []
    min_count = max_count = 1
    requested_networks = None
    sg_names = []
    availability_zone = None
    config_drive = None
    block_device_mapping = None
    kernel_id = ramdisk_id = None
    auto_disk_config = None
    scheduler_hints = None

    resource_template = None
    os_template = None
    for mixin in entity.mixins:
        if isinstance(mixin, os_mixins.ResourceTemplate):
            resource_template = mixin
        elif isinstance(mixin, os_mixins.OsTemplate):
            os_template = mixin
        elif mixin == os_addon.OS_KEY_PAIR_EXT:
            attr = 'org.openstack.credentials.publickey.name'
            key_name = entity.attributes[attr]
            attr = 'org.openstack.credentials.publickey.data'
            key_data = entity.attributes[attr]
        elif mixin == os_addon.OS_USER_DATA_EXT:
            attr = 'org.openstack.compute.user_data'
            user_data = entity.attributes[attr]
        # Look for security group. If the group is non-existant, the
        # call to create will fail.
        if os_addon.SEC_GROUP in mixin.related:
            secgroup = COMPUTE_API.security_group_api.get(context,
                                                          name=mixin.term)
            sg_names.append(secgroup["name"])

    if not os_template:
        raise AttributeError('Please provide a valid OS Template.')

    if resource_template:
        inst_type = flavors.get_flavor_by_flavor_id(resource_template.res_id)
    else:
        inst_type = None
    # make the call
    try:
        (instances, _reservation_id) = COMPUTE_API.create(
            context=context,
            instance_type=inst_type,
            image_href=os_template.os_id,
            kernel_id=kernel_id,
            ramdisk_id=ramdisk_id,
            min_count=min_count,
            max_count=max_count,
            display_name=name,
            display_description=name,
            key_name=key_name,
            key_data=key_data,
            security_group=sg_names,
            availability_zone=availability_zone,
            user_data=user_data,
            metadata=metadata,
            injected_files=injected_files,
            admin_password=password,
            block_device_mapping=block_device_mapping,
            access_ip_v4=access_ip_v4,
            access_ip_v6=access_ip_v6,
            requested_networks=requested_networks,
            config_drive=config_drive,
            auto_disk_config=auto_disk_config,
            scheduler_hints=scheduler_hints)
    except Exception as e:
        raise AttributeError(e.message)

    # return first instance
    return instances[0]


def rebuild_vm(uid, image_href, context):
    """
    Rebuilds the specified VM with the supplied OsTemplate mixin.

    uid -- id of the instance
    image_href -- image reference.
    context -- the os context
    """
    instance = get_vm(uid, context)

    admin_password = utils.generate_password()
    kwargs = {}
    try:
        COMPUTE_API.rebuild(context, instance, image_href, admin_password,
                            **kwargs)
    except Exception as e:
        raise AttributeError(e.message)


def resize_vm(uid, flavor_id, context):
    """
    Resizes a VM up or down

    Update: libvirt now supports resize see:
    http://wiki.openstack.org/HypervisorSupportMatrix

    uid -- id of the instance
    flavor_id -- image reference.
    context -- the os context
    """
    instance = get_vm(uid, context)
    kwargs = {}
    try:
        flavor = flavors.get_flavor_by_flavor_id(flavor_id)
        COMPUTE_API.resize(context, instance, flavor_id=flavor['flavorid'],
                           **kwargs)
        ready = False
        i = 0
        # XXX are 15 secs enough to resize?
        while not ready and i < 15:
            i += 1
            state = get_vm(uid, context)['vm_state']
            if state == 'resized':
                ready = True
            import time
            time.sleep(1)
        instance = get_vm(uid, context)
        COMPUTE_API.confirm_resize(context, instance)
    except Exception as e:
        raise AttributeError(str(e))


def delete_vm(uid, context):
    """
    Destroy a VM.

    uid -- id of the instance
    context -- the os context
    """
    try:
        instance = get_vm(uid, context)
        COMPUTE_API.delete(context, instance)
    except Exception as error:
        raise exceptions.HTTPError(500, str(error))


def suspend_vm(uid, context):
    """
    Suspends a VM. Use the start action to unsuspend a VM.

    uid -- id of the instance
    context -- the os context
    """
    instance = get_vm(uid, context)

    try:
        COMPUTE_API.pause(context, instance)
    except Exception as error:
        raise exceptions.HTTPError(500, str(error))


def snapshot_vm(uid, image_name, context):
    """
    Snapshots a VM. Use the start action to unsuspend a VM.

    uid -- id of the instance
    image_name -- name of the new image
    context -- the os context
    """
    instance = get_vm(uid, context)
    try:
        COMPUTE_API.snapshot(context,
                             instance,
                             image_name)

    except Exception as e:
        raise AttributeError(e.message)


def start_vm(uid, context):
    """
    Starts a vm that is in the stopped state. Note, currently we do not
    use the nova start and stop, rather the resume/suspend methods. The
    start action also unpauses a paused VM.

    uid -- id of the instance
    state -- the state the VM is in (str)
    context -- the os context
    """
    instance = get_vm(uid, context)
    try:
        if instance['vm_state'] in [vm_states.PAUSED]:
            COMPUTE_API.unpause(context, instance)
        elif instance['vm_state'] in [vm_states.SUSPENDED]:
            COMPUTE_API.resume(context, instance)
        # the following will probably not happen, as COMPUTE_API.stop()
        # is never called.
        elif instance['vm_state'] in [vm_states.STOPPED]:
            COMPUTE_API.start(context, instance)
        else:
            raise exceptions.HTTPError(500, "Unable to map start to appropriate OS action.")
    except exceptions.HTTPError as e:
        raise e
    except Exception as e:
        raise AttributeError(e.message)


def stop_vm(uid, context):
    """
    Stops a VM. Rather than use stop, suspend is used.
    OCCI -> graceful, acpioff, poweroff
    OS -> unclear

    uid -- id of the instance
    context -- the os context
    """
    instance = get_vm(uid, context)

    try:
        COMPUTE_API.suspend(context, instance)
    except Exception as e:
        raise AttributeError(e.message)


def restart_vm(uid, method, context):
    """
    Restarts a VM.
      OS types == SOFT, HARD
      OCCI -> graceful, warm and cold
      mapping:
      - SOFT -> graceful, warm
      - HARD -> cold

    uid -- id of the instance
    method -- how the machine should be restarted.
    context -- the os context
    """
    instance = get_vm(uid, context)

    if method in ('graceful', 'warm'):
        reboot_type = 'SOFT'
    elif method == 'cold':
        reboot_type = 'HARD'
    else:
        raise AttributeError('Unknown method.')
    try:
        COMPUTE_API.reboot(context, instance, reboot_type)
    except Exception as e:
        raise AttributeError(e.message)


def attach_volume(instance_id, volume_id, mount_point, context):
    """
    Attaches a storage volume.

    instance_id -- Id of the VM.
    volume_id -- Id of the storage volume.
    mount_point -- Where to mount.
    context -- The os security context.
    """
    instance = get_vm(instance_id, context)
    try:
        COMPUTE_API.attach_volume(
            context,
            instance,
            volume_id,
            mount_point)
    except Exception as e:
        raise AttributeError(e.message)


def detach_volume(instance_id, volume, context):
    """
    Detach a storage volume.

    volume -- Volume description.
    instance_id -- Id of the VM.
    context -- the os context.
    """
    try:
        instance = get_vm(instance_id, context)
        COMPUTE_API.detach_volume(context, instance, volume)
    except Exception as e:
        raise AttributeError(e)


def set_password_for_vm(uid, password, context):
    """
    Set new password for an VM.

    uid -- Id of the instance.
    password -- The new password.
    context -- The os context.
    """
    instance = get_vm(uid, context)
    try:
        COMPUTE_API.set_admin_password(context, instance, password)
    except Exception as e:
        raise AttributeError(e.message)


def get_vnc(uid, context):
    """
    Retrieve VNC console or None if unavailable.

    uid -- id of the instance
    context -- the os context
    """
    console = None
    instance = get_vm(uid, context)
    try:
        console = COMPUTE_API.get_vnc_console(context, instance, 'novnc')
    except Exception:
        LOG.warn('Console info is not available atm!')
    finally:
        return console


def get_vm(uid, context):
    """
    Retrieve an VM instance from nova.

    uid -- id of the instance
    context -- the os context
    """
    try:
        instance = COMPUTE_API.get(context, uid, want_objects=True)
    except Exception:
        raise exceptions.HTTPError(404, 'VM not found!')
    return instance


def get_vms(context):
    """
    Retrieve all VMs in a given context.
    """
    opts = {'deleted': False}
    tmp = COMPUTE_API.get_all(context, search_opts=opts)
    return tmp


def get_vm_state(uid, context):
    """
    See nova/compute/vm_states.py nova/compute/task_states.py

    Mapping assumptions:
    - active == VM can service requests from network. These requests
            can be from users or VMs
    - inactive == the oppose! :-)
    - suspended == machine in a frozen state e.g. via suspend or pause

    uid -- Id of the VM.
    context -- the os context.
    """
    instance = get_vm(uid, context)
    state = 'inactive'
    actions = []

    if instance['vm_state'] in [vm_states.ACTIVE]:
        state = 'active'
        actions.append(infrastructure.STOP)
        actions.append(infrastructure.SUSPEND)
        actions.append(infrastructure.RESTART)
    elif instance['vm_state'] in [vm_states.BUILDING]:
        state = 'inactive'
    elif instance['vm_state'] in [vm_states.PAUSED, vm_states.SUSPENDED,
                                  vm_states.STOPPED]:
        state = 'inactive'
        actions.append(infrastructure.START)
    elif instance['vm_state'] in [vm_states.RESCUED,
                                  vm_states.ERROR,
                                  vm_states.DELETED]:
        state = 'inactive'

    # Some task states require a state
    if instance['vm_state'] in [task_states.IMAGE_SNAPSHOT]:
        state = 'inactive'
        actions = []

    return state, actions

# Image management


def retrieve_image(uid, context):
    """
    Return details on an image.
    """
    try:
        return COMPUTE_API.image_service.show(context, uid)
    except Exception as e:
        raise AttributeError(e.message)


def retrieve_images(context):
    """
    Retrieve list of images.
    """
    return COMPUTE_API.image_service.detail(context)


def retrieve_flavors():
    """
    Retrieve list of flavors.
    """
    return flavors.get_all_flavors()
