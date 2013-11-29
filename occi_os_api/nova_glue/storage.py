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
Storage related glue :-)
"""

import random

from nova import compute

from occi import exceptions

VOLUME_API = compute.API().volume_api


def create_storage(size, context, name=None, description=None):
    """
    Create a storage instance.

    size -- Size of the storage. ('occi.storage.size')
    context -- The os context.
    name -- defaults to a random number if needed.
    description -- defaults to the name
    """
    # L8R: A blueprint?
    # OpenStack deals with size in terms of integer.
    # Need to convert float to integer for now and only if the float
    # can be losslessly converted to integer
    # e.g. See nova/quota.py:allowed_volumes(...)
    if not float(size).is_integer:
        raise AttributeError('Volume sizes cannot be specified as fractional'
                             ' floats.')
    size = int(float(size))

    disp_name = ''
    if name is not None:
        disp_name = name
    else:
        disp_name = str(random.randrange(0, 99999999)) + '-storage.occi-wg.org'
    if description is not None:
        disp_descr = description
    else:
        disp_descr = disp_name

    try:
        return VOLUME_API.create(context,
                                 size,
                                 disp_name,
                                 disp_descr)
    except Exception as e:
        raise AttributeError(e.message)


def delete_storage_instance(uid, context):
    """
    Delete a storage instance.

    uid -- Id of the volume.
    context -- The os context.
    """
    try:
        VOLUME_API.delete(context, uid)
    except Exception as e:
        raise AttributeError(e.message)


def snapshot_storage_instance(uid, name, description, context):
    """
    Snapshots an storage instance.

    uid -- Id of the volume.
    context -- The os context.
    """
    try:
        instance = get_storage(uid, context)
        VOLUME_API.create_snapshot(context, instance, name, description)
    except Exception as e:
        raise AttributeError(e.message)


def get_storage(uid, context):
    """
    Retrieve an Volume instance from nova.

    uid -- id of the instance
    context -- the os context
    """
    try:
        instance = VOLUME_API.get(context, uid)
    except Exception:
        raise exceptions.HTTPError(404, 'Volume not found!')
    return instance


def get_storage_volumes(context):
    """
    Retrieve all storage entities from user.
    """
    return VOLUME_API.get_all(context)
