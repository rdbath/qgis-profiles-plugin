# -*- coding: utf-8 -*-
#
# (c) 2016 Boundless, http://boundlessgeo.com
# This code is licensed under the GPL 2.0 license.

import json

from PyQt4.QtGui import (QToolBar,
                         QDockWidget,
                         QMessageBox,
                         QAction, QPushButton)
from PyQt4.QtCore import (QSettings, QCoreApplication)

from qgis.utils import (iface,
                        active_plugins,
                        available_plugins,
                        unloadPlugin,
                        loadPlugin,
                        startPlugin,
                        updateAvailablePlugins)

from qgis.gui import QgsMessageBar
from qgis.core import QgsMessageOutput

import pyplugin_installer
from pyplugin_installer.installer_data import repositories, plugins
from pyplugin_installer.qgsplugininstallerinstallingdialog import QgsPluginInstallerInstallingDialog
from collections import defaultdict


PLUGINS, MENUS, BUTTONS, PANELS = range(4)

def _objectName(ob):
    if isinstance(ob.objectName, str):
        return ob.objectName
    else:
        return ob.objectName()

def saveCurrentStatus(filepath, name, toAdd=None):
    toAdd = toAdd or range(4)
    status = {'name': name}
    if MENUS in toAdd:
        addMenus(status)
    if BUTTONS in toAdd:
        addButtons(status)
    if PANELS in toAdd:
        addPanels(status)
    if PLUGINS in toAdd:
        addPlugins(status)

    with open(filepath, 'w') as f:
        json.dump(status, f, indent=4, sort_keys=True)


def getMenus(path, action):
    menus = {}
    submenu = action.menu()
    if submenu is None:
        if not action.isSeparator():
            menus[path + '/' + action.objectName()] = action
    else:
        path = submenu.objectName() if path is None else path + '/' + submenu.objectName()
        actions = submenu.actions()
        for subaction in actions:
            menus.update(getMenus(path, subaction))
    return menus


def addMenus(status):
    menus = {}
    actions = iface.mainWindow().menuBar().actions()
    for action in actions:
        menus.update(getMenus(None, action))
    status['menus'] = {k:v.text() for k,v in menus.iteritems()}


def addPanels(status):
    status['panels'] =  [_objectName(el) for el in iface.mainWindow().children()
                if isinstance(el, QDockWidget) and el.isVisible()]


def addPlugins(status):
    status['plugins'] = active_plugins


def addButtons(status):
    buttons = {}
    toolbars = [el for el in iface.mainWindow().children()
                if isinstance(el, QToolBar) and el.isVisible()]
    for bar in toolbars:
        barbuttons = {action.objectName(): None for action in bar.actions() if action.isVisible()}
        if barbuttons:
            buttons[bar.objectName()] = barbuttons

    status['buttons'] = buttons


customToolbarsWidgets = []

def applyButtons(profile):
    if profile.buttons is None:
        return

    for toolbar in customToolbarsWidgets[::-1]:
        toolbar.setVisible(False)
        iface.mainWindow().removeToolBar(toolbar)
        del toolbar

    del customToolbarsWidgets[:]

    currentToolbars = [el for el in iface.mainWindow().children()
                if isinstance(el, QToolBar)]

    customToolbars = defaultdict(list)
    toolbars = profile.buttons
    for toolbar in currentToolbars:
        if toolbar.objectName() in toolbars:
            hasVisibleActions = False
            actions = toolbar.actions()
            for action in actions:
                if action.objectName() in toolbars[toolbar.objectName()]:
                    action.setVisible(True)
                    location = toolbars[toolbar.objectName()][action.objectName()]
                    if location is not None:
                        newAction = QAction(action.icon(), action.text(), iface.mainWindow())
                        newAction.triggered.connect(action.trigger)
                        objectName = "%s_%i" % (location, len(customToolbars[location]))
                        newAction.setObjectName(objectName)
                        customToolbars[location].append(newAction)
                        action.setVisible(False)
                    else:
                        hasVisibleActions = True
                        action.setVisible(True)
                else:
                    action.setVisible(False)
            toolbar.setVisible(hasVisibleActions)
        else:
            toolbar.setVisible(False)

    for name, actions in customToolbars.iteritems():
        toolbar = iface.mainWindow().addToolBar(name)
        toolbar.setObjectName("toolbar_%s" % name)
        customToolbarsWidgets.append(toolbar)
        for action in actions:
            toolbar.addAction(action)


def isMenuWhiteListed(path, text):
    text = text.lower()
    return 'mProfilesPlugin' in path or "testing" in text or "tester" in text


def applyMenus(profile):
    if profile.menus is None:
        return
    menus = {}
    actions = iface.mainWindow().menuBar().actions()
    for action in actions:
        menus.update(getMenus(None, action))

    for path, action in menus.iteritems():
        if action.isSeparator():
            action.setVisible(True)
        elif path in profile.menus or isMenuWhiteListed(path, action.text()):
            action.setVisible(True)
            action.setText(profile.menus.get(path, action.text()))
        else:
            action.setVisible(False)

    cleanEmptyMenus()


def cleanEmptyMenus():
    actions = iface.mainWindow().menuBar().actions()
    for action in actions:
        action.setVisible(cleanEmptySubmenus(action))


def cleanEmptySubmenus(action):
    menu = action.menu()
    actions = menu.actions()
    for act in actions:
        submenu = act.menu()
        if submenu is not None:
            act.setVisible(cleanEmptySubmenus(act))

    for act in actions:
        if not act.isSeparator() and act.isVisible():
            return True

    return False


def addActionAt(action, menuPath):
    pathLevels = menuPath.split('/')
    actions = iface.mainWindow().menuBar().actions()
    for name in pathLevels:
        menu = None
        for act in actions:
            _menu = act.menu()
            if _menu is not None and _menu.objectName() == name:
                menu = _menu
                break
        if menu is None:
            return
        actions = menu.actions()

    menu.addAction(action)


def applyPanels(profile):
    if profile.panels is None:
        return
    currentPanels = [el for el in iface.mainWindow().children()
                if isinstance(el, QDockWidget)]
    panels = profile.panels
    panels.append("TesterPluginPanel")
    for panel in currentPanels:
        panel.setVisible(_objectName(panel) in panels)


pluginsToIgnore = ['profiles', 'qgistester', 'processing']
def applyPlugins(profile):
    if profile.plugins is None:
        return
    toInstall = [p  for p in profile.plugins if p not in available_plugins]
    pluginErrors = []
    for p in toInstall:
        error = installPlugin(p)
        if error:
            pluginErrors.append(error)

    updateAvailablePlugins()

    settings = QSettings()

    tounload = [p for p in active_plugins if p not in pluginsToIgnore]
    for p in tounload:
        try:
            unloadPlugin(p)
        except:
            pass
        settings.setValue('/PythonPlugins/' + p, False)
        updateAvailablePlugins()

    updateAvailablePlugins()

    for p in profile.plugins:
        if p not in active_plugins and p in available_plugins:
            loadPlugin(p)
            startPlugin(p)
            settings.setValue('/PythonPlugins/' + p, True)
    updateAvailablePlugins()
    updatePluginManager()

    return pluginErrors


def updatePluginManager():
    installer = pyplugin_installer.instance()
    plugins.getAllInstalled(testLoad=True)
    plugins.rebuild()
    installer.exportPluginsToManager()


def installPlugin(pluginName):
    installer = pyplugin_installer.instance()
    installer.fetchAvailablePlugins(False)

    if pluginName in plugins.all():
        plugin = plugins.all()[pluginName]
        if pluginName not in available_plugins or plugin['status'] == 'upgradeable':
            dlg = QgsPluginInstallerInstallingDialog(iface.mainWindow(), plugin)
            dlg.exec_()
            if dlg.result():
                return tr('The {} plugin could not be installed.<br>'
                            'The following problems were found during installation:<br>{}'.format(pluginName, dlg.result()))
    else:
        return tr('The {} plugin could not be installed.<br>'
                    'It was not found in any of the available repositories.'.format(pluginName))


def applyProfile(profile, defaultProfile):
    plugins = profile.plugins or defaultProfile.plugins
    if plugins is not None:
        toInstall = [p  for p in plugins if p not in available_plugins]
        if toInstall:
            ok = QMessageBox.question(iface.mainWindow(),
                tr('Profile installation'),
                tr('This profile requires plugins that are not currently\n'
                'available in your QGIS installation. The will have to\n'
                'be downloaded and installed.\n\n Do you want to proceed?'),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if ok != QMessageBox.Yes:
                return
    if profile.menus is None:
        applyMenus(defaultProfile)
    if profile.buttons is None:
        applyButtons(defaultProfile)
    if profile.panels is None:
        applyPanels(defaultProfile)
    if profile.plugins is None:
        applyPlugins(defaultProfile)
    pluginErrors = applyPlugins(profile)
    applyMenus(profile)
    applyButtons(profile)
    applyPanels(profile)
    if pluginErrors:
        widget = iface.messageBar().createMessage("Error", tr('Profile {} has been applied with errors'.format(profile.name)))
        showButton = QPushButton(widget)
        showButton.setText("View more")
        def showMore():
            dlg = QgsMessageOutput.createMessageOutput()
            dlg.setTitle('Profile errors')
            dlg.setMessage("<br><br>".join(pluginErrors), QgsMessageOutput.MessageHtml)
            dlg.showMessage()
        showButton.pressed.connect(showMore)
        widget.layout().addWidget(showButton)
        iface.messageBar().pushWidget(widget, QgsMessageBar.WARNING,
                                             duration = 5)
    else:
        iface.messageBar().pushMessage(tr('Profiles'),
                                   tr('Profile {} has been correctly applied'.format(profile.name)),
                                   level=QgsMessageBar.INFO,
                                   duration=5)


def tr(string, context=''):
    if context == '':
        context = 'Profiles'
    return QCoreApplication.translate(context, string)
