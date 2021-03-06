from builtins import object
# -*- coding: utf-8 -*-
#
# (c) 2016 Boundless, http://boundlessgeo.com
# This code is licensed under the GPL 2.0 license.


import os
import json
import importlib

from qgis.utils import plugins

from profiles.utils import applyProfile


class Profile(object):

    def __init__(self):
        self.name = ''
        self.group = ''
        self.description = ''
        self.panels = None
        self.buttons = None
        self.menus = None
        self.plugins = None
        self._filename = None
        self._apply = None

    def apply(self):
        applyProfile(self, defaultProfile)
        if self._apply is not None:
            self._apply()

    def hasToInstallPlugins(self):
        if self.plugins is None:
            return False
        return any([(p not in plugins) for p in self.plugins])

    @staticmethod
    def fromFile(defFile):
        with open(defFile) as f:
            d = json.load(f)
        profile = Profile()
        profile.__dict__.update(d)
        try:
            module = importlib.import_module('profiles.userprofiles.' + os.path.splitext(os.path.basename(defFile))[0])
            if hasattr(module, 'apply'):
                func = getattr(module, 'apply')
                profile._apply = func
        except ImportError:
            pass
        profile._filename = defFile
        return profile

folder = os.path.join(os.path.dirname(__file__), 'userprofiles', 'base')
filepath = os.path.join(folder, 'base.json')
defaultProfile = Profile.fromFile(filepath)
