# Copyright (c) 2019 Aldo Hoeben / fieldOfView
# SerialConnection is released under the terms of the GPLv3 or higher.

import os, json

from . import SerialOutputDevicePlugin
from . import ConnectSerialAction

def getMetaData():
    return {}

def register(app):
    return {
        "output_device": SerialOutputDevicePlugin.SerialOutputDevicePlugin(app),
        "machine_action": ConnectSerialAction.ConnectSerialAction()
    }