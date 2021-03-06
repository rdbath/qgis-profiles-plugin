from builtins import object
# -*- coding: utf-8 -*-
#
# (c) 2016 Boundless, http://boundlessgeo.com
# This code is licensed under the GPL 2.0 license.

import os
from collections import defaultdict

from qgis.PyQt.QtWidgets import QAction, QActionGroup, QMenu, QMessageBox
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtCore import QCoreApplication, QSettings, QUrl

from qgis.core import QgsApplication
from qgis.gui import QgsMessageBar

from qgis.utils import iface

from profiles.userprofiles import profiles, applyProfile, saveCurrentPluginState
from profiles.gui.profilemanager import ProfileManager

pluginPath = os.path.dirname(__file__)


class ProfilesPlugin(object):

    def __init__(self, iface):
        self.iface = iface
        QSettings().setValue('/UI/Customization/enabled', False)

        try:
            from profiles.tests import testerplugin
            from qgistester.tests import addTestModule
            addTestModule(testerplugin, 'Profiles plugin')
        except:
            pass

        self.userProfileAction = None
        self.profilesMenu = None

        iface.initializationCompleted.connect(self.initProfile)

    def unload(self):
        if self.profilesMenu is not None:
            self.profilesMenu.deleteLater()
        self.iface.removePluginMenu(self.tr('Profiles'), self.autoloadAction)
        self.iface.removePluginMenu(self.tr('Profiles'), self.saveProfileAction)
        try:
            from profiles.tests import testerplugin
            from qgistester.tests import removeTestModule
            removeTestModule(testerplugin, 'Profiles plugin')
        except:
            pass
        saveCurrentPluginState()

    def initGui(self):
        self.addMenus()

    def addMenus(self):
        if self.profilesMenu is not None:
            self.profilesMenu.clear()
        self.actions = defaultdict(list)
        settings = QSettings()
        defaultProfile = settings.value('profilesplugin/LastProfile', 'Default', str)
        autoLoad = settings.value('profilesplugin/AutoLoad', False, bool)
        for k, v in profiles.items():
            action = QAction(k, self.iface.mainWindow())
            action.setCheckable(True)
            if k == defaultProfile and autoLoad:
                action.setChecked(True)
            action.triggered.connect(lambda _, menuName=k: self.applyProfile(menuName))
            action.setObjectName('mProfilesPlugin_' + k)
            self.actions[v.group].append(action)

        actions = self.iface.mainWindow().menuBar().actions()
        settingsMenu = None
        self.profilesGroup = QActionGroup(self.iface.mainWindow())
        if self.profilesMenu is None:
            for action in actions:
                if action.menu().objectName() == 'mSettingsMenu':
                    settingsMenu = action.menu()
                    self.profilesMenu = QMenu(settingsMenu)
                    self.profilesMenu.setObjectName('mProfilesPlugin')
                    self.profilesMenu.setTitle(self.tr('Profiles'))
                    settingsMenu.addMenu(self.profilesMenu)
                    break

        if self.profilesMenu is not None:
            for k,v in self.actions.items():
                submenu = QMenu(self.profilesMenu)
                submenu.setObjectName('mProfilesPlugin_submenu_' + k)
                submenu.setTitle(k)
                for action in v:
                    self.profilesGroup.addAction(action)
                    submenu.addAction(action)
                self.profilesMenu.addMenu(submenu)

        self.profilesMenu.addSeparator()

        settings = QSettings()
        def _setAutoLoad():
            settings.setValue('profilesplugin/AutoLoad', self.autoloadAction.isChecked())

        self.autoloadAction = QAction(self.tr('Auto-load last profile on QGIS start'), iface.mainWindow())
        self.autoloadAction.setCheckable(True)
        autoLoad = settings.value('profilesplugin/AutoLoad', False, bool)
        self.autoloadAction.setChecked(autoLoad)
        self.autoloadAction.setObjectName('mProfilesPluginAutoLoad')
        self.autoloadAction.triggered.connect(_setAutoLoad)
        self.profilesMenu.addAction(self.autoloadAction)

        self.saveProfileAction = QAction(self.tr('Profiles manager...'),
                                         self.iface.mainWindow())
        self.saveProfileAction.setObjectName('mProfilesPluginProfilesManager')
        self.saveProfileAction.triggered.connect(self.saveProfile)
        self.profilesMenu.addAction(self.saveProfileAction)

        self.showHelpAction = QAction(self.tr('Help'), self.iface.mainWindow())
        self.showHelpAction.setIcon(QgsApplication.getThemeIcon('/mActionHelpContents.svg'))
        self.showHelpAction.setObjectName('mProfilesPluginShowHelp')
        self.showHelpAction.triggered.connect(self.showHelp)
        self.profilesMenu.addAction(self.showHelpAction)


    def applyProfile(self, name):
        profile = profiles.get(name)
        applyProfile(profile)

    def initProfile(self):
        settings = QSettings()
        autoLoad = settings.value('profilesplugin/AutoLoad', False, bool)
        if autoLoad:
            profileName = settings.value('profilesplugin/LastProfile', '', str)
            if profileName in profiles:
                profile = profiles[profileName]
                if not profile.hasToInstallPlugins():
                    applyProfile(profile, False)

    def saveProfile(self):
        dlg = ProfileManager(iface.mainWindow())
        dlg.exec_()

    def showHelp(self):
        if not QDesktopServices.openUrl(
                QUrl('file://{}'.format(os.path.join(pluginPath, 'docs', 'html', 'index.html')))):
            QMessageBox.warning(None,
                                self.tr('Error'),
                                self.tr('Can not open help URL in browser'))

    def tr(self, text):
        return QCoreApplication.translate('Profiles', text)
