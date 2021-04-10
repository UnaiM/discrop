import asyncio
import math
import os.path
import sys
import time
import threading

import obspython as obs

script_path_ = os.path.dirname(__file__) # script_path is part of the OBS script interface.
sys.path.append(os.path.join(script_path_, 'lib', 'site-packages'))
from PySide2 import QtCore, QtWidgets
import discord


class Discrop(QtWidgets.QDialog):

    def __init__(self):
        super().__init__(QtWidgets.QApplication.instance().desktop())
        self.setWindowTitle('Discrop')
        self.setWindowFlag(QtCore.Qt.Tool)

        self.source = QtWidgets.QComboBox()
        self.channel = QtWidgets.QComboBox()
        self.mapping = QtWidgets.QListWidget()
        self.ignored = QtWidgets.QListWidget()

        layout = QtWidgets.QFormLayout()
        layout.addRow('Capture source', self.source)
        layout.addRow('Discord channel', self.channel)
        layout.addRow('Participant mapping', self.mapping)
        layout.addRow('Ignored participants', self.ignored)
        self.setLayout(layout)


discrop = Discrop()


def script_load(settings):
    pass


def script_properties():
    props = obs.obs_properties_create()
    obs.obs_properties_add_button(props, 'options', 'Options…', lambda *x: discrop.show())
    return props
