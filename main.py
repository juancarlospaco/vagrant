1# -*- coding: utf-8 -*-
# PEP8:OK, LINT:OK, PY3:OK


#############################################################################
## This file may be used under the terms of the GNU General Public
## License version 2.0 or 3.0 as published by the Free Software Foundation
## and appearing in the file LICENSE.GPL included in the packaging of
## this file.  Please review the following information to ensure GNU
## General Public Licensing requirements will be met:
## http:#www.fsf.org/licensing/licenses/info/GPLv2.html and
## http:#www.gnu.org/copyleft/gpl.html.
##
## This file is provided AS IS with NO WARRANTY OF ANY KIND, INCLUDING THE
## WARRANTY OF DESIGN, MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.
#############################################################################


# metadata
' Vagrant Ninja '
__version__ = ' 0.2 '
__license__ = ' GPL '
__author__ = ' juancarlospaco '
__email__ = ' juancarlospaco@ubuntu.com '
__url__ = 'github.com/juancarlospaco'
__date__ = '01/05/2013'
__prj__ = 'vagrant'
__docformat__ = 'html'
__source__ = ''
__full_licence__ = ''


# imports
from os import environ, linesep, chmod, remove, path, chdir, makedirs
from sip import setapi
from datetime import datetime
from subprocess import check_output as getoutput
from random import choice
from getpass import getuser

try:
    from os import startfile
except ImportError:
    from subprocess import Popen

from PyQt4.QtGui import (QLabel, QCompleter, QDirModel, QPushButton, QSpinBox,
    QDockWidget, QVBoxLayout, QLineEdit, QIcon, QCheckBox, QColor, QMessageBox,
    QGraphicsDropShadowEffect, QGroupBox, QComboBox, QTabWidget, QButtonGroup,
    QAbstractButton)

from PyQt4.QtCore import Qt, QDir, QProcess, QUrl

from PyQt4.QtNetwork import QNetworkProxy

try:
    from PyKDE4.kdeui import KTextEdit as QTextEdit
except ImportError:
    from PyQt4.QtGui import QTextEdit  # lint:ok

from ninja_ide.core import plugin


# API 2
(setapi(a, 2) for a in ("QDate", "QDateTime", "QString", "QTime", "QUrl",
                        "QTextStream", "QVariant"))


# constans
HELPMSG = '''<h3>Vagrant</h3>
Vagrant provides easy to configure, reproducible, and portable work environments
built on top of industry-standard technology and controlled by a single
consistent workflow.
<br>
Machines are provisioned on top of VirtualBox.
Provisioning tools automatically install and configure software on the machine.
<br><br>
<b>If you are Developer</b>, Vagrant will isolate dependencies and configuration
within a single disposable, consistent environment, without sacrificing any of
the tools you are used to working with (editors, browsers, debuggers, etc.).
Once you or someone else creates a single Vagrantfile, you just need to vagrant
 up and everything is installed and configured for you to work.
 Other members of your team create their development environments from the same
 configuration, so whether you are working on Linux, OSX, or Windows, all your
 team members are running code in the same environment, against the same
 dependencies, all configured the same way.
 Say goodbye to "works on my machine" bugs.
<br><br>
Visit <a href="http://vagrantup.com">Vagrantup.com</a>
and <a href="http://virtualbox.org">Virtualbox.org</a>
<br><br>
''' + ''.join((__doc__, __version__, __license__, 'by', __author__, __email__))

VBOXGUI = '''
    config.vm.provider :virtualbox do |vb|
        vb.gui = true
    end
'''

CONFIG = '''
Vagrant.configure("2") do |config|
    config.vm.box = "{}"
    config.vm.box_url = "{}://cloud-images.ubuntu.com/vagrant/{}/current/{}-server-cloudimg-{}-vagrant-disk1.box"
    config.vm.provision :shell, :path => "bootstrap.sh"
    {}
end
'''

BASE = path.abspath(path.join(path.expanduser("~"), 'vagrant'))


###############################################################################


class Main(plugin.Plugin):
    " Main Class "
    def initialize(self, *args, **kwargs):
        " Init Main Class "
        super(Main, self).initialize(*args, **kwargs)

        # directory auto completer
        self.completer, self.dirs = QCompleter(self), QDirModel(self)
        self.dirs.setFilter(QDir.AllEntries | QDir.NoDotAndDotDot)
        self.completer.setModel(self.dirs)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)

        self.desktop = ''

        self.process = QProcess()
        self.process.finished.connect(self._process_finished)
        self.process.error.connect(self._process_finished)

        # Proxy support, by reading http_proxy os env variable
        proxy_url = QUrl(environ.get('http_proxy', ''))
        QNetworkProxy.setApplicationProxy(QNetworkProxy(QNetworkProxy.HttpProxy
            if str(proxy_url.scheme()).startswith('http')
            else QNetworkProxy.Socks5Proxy, proxy_url.host(), proxy_url.port(),
                 proxy_url.userName(), proxy_url.password())) \
            if 'http_proxy' in environ else None

        self.mainwidget = QTabWidget()
        self.mainwidget.tabCloseRequested.connect(lambda:
            self.mainwidget.setTabPosition(1)
            if self.mainwidget.tabPosition() == 0
            else self.mainwidget.setTabPosition(0))
        self.mainwidget.setStyleSheet('QTabBar{font-weight:bold;}')
        self.mainwidget.setMovable(True)
        self.mainwidget.setTabsClosable(True)

        self.dock = QDockWidget()
        self.dock.setWindowTitle(__doc__)
        self.dock.setStyleSheet('QDockWidget::title{text-align: center;}')
        self.dock.setWidget(self.mainwidget)

        self.misc = self.locator.get_service('misc')
        self.misc.add_widget(self.dock, QIcon.fromTheme("virtualbox"), __doc__)

        self.tab1, self.tab2, self.tab3 = QGroupBox(), QGroupBox(), QGroupBox()
        self.tab4, self.tab5, self.tab6 = QGroupBox(), QGroupBox(), QGroupBox()
        for a, b in ((self.tab1, 'Basic Startup'),
            (self.tab2, 'General Options'), (self.tab3, 'VM Package Manager'),
            (self.tab4, 'VM Provisioning'), (self.tab5, 'VM Desktop GUI'),
                     (self.tab6, 'Run')):
            a.setTitle(b)
            a.setToolTip(b)
            self.mainwidget.addTab(a, QIcon.fromTheme("virtualbox"), b)

        QPushButton(QIcon.fromTheme("help-about"), 'About', self.dock
        ).clicked.connect(lambda: QMessageBox.information(self.dock, __doc__,
        HELPMSG))

        self.vmname = QLineEdit(self.get_random_name())
        self.vmname.setPlaceholderText('type_your_VM_name_here_without_spaces')
        self.vmname.setToolTip('Type VM name, no spaces or special characters')
        self.target = QLabel('<b>Vagrant Target Folder: ' +
                             path.join(BASE, self.vmname.text()))
        self.vmname.textChanged.connect(lambda: self.target.setText(
            '<b>Vagrant Target Folder: ' + path.join(BASE, self.vmname.text())))
        self.btn1 = QPushButton(QIcon.fromTheme("face-smile-big"), 'Suggestion')
        self.btn1.setToolTip('Suggest me a Random VM name !')
        self.btn1.clicked.connect(lambda:
                                  self.vmname.setText(self.get_random_name()))
        self.vmcode = QComboBox()
        self.vmcode.addItems(['saucy', 'raring', 'quantal', 'precise'])
        self.vmarch = QComboBox()
        self.vmarch.addItems(['x86_64 (amd64) 64-Bits', 'x86 (i386) 32-Bits'])
        vboxg1 = QVBoxLayout(self.tab1)
        for each_widget in (
            QLabel('<b>Name for your new VM:</b>'), self.vmname, self.btn1,
            QLabel('<b>Choose Ubuntu Codename for the VM:</b>'), self.vmcode,
            QLabel('<b>Choose an Architecture for the VM:</b>'), self.vmarch,
            self.target):
            vboxg1.addWidget(each_widget)

        self.combo1 = QSpinBox()
        self.combo1.setValue(20)
        self.combo1.setMaximum(20)
        self.combo1.setMinimum(0)
        self.combo1.setToolTip('Backend Nice priority (0 = High, 20 = Low)')
        self.chttps = QComboBox()
        self.chttps.addItems(['https', 'http'])
        try:
            self.vinfo1 = QLabel('<b> Vagrant Backend Version: </b>' +
                            getoutput('vagrant --version', shell=1).strip())
        except:
            self.vinfo1 = QLabel('<b>Warning: Failed to query Vagrant Backend!')
        try:
            self.vinfo2 = QLabel('<b> VirtualBox Backend Version: </b>' +
                            getoutput('vboxmanage --version', shell=1).strip())
        except:
            self.vinfo2 = QLabel('<b>Warning: Failed query VirtualBox Backend')
        self.qckb1 = QCheckBox(' Open target directory later')
        self.qckb1.setToolTip('Open the target directory when finished')
        self.qckb2 = QCheckBox(' Save a LOG file to target later')
        self.qckb2.setToolTip('Save a read-only .LOG file to target')
        self.qckb3 = QCheckBox(' NO run Headless Mode, use a Window')
        self.qckb3.setToolTip('Show the VM on a Window GUI instead of Headless')
        vboxg2 = QVBoxLayout(self.tab2)
        for each_widget in (self.qckb1, self.qckb2, self.qckb3,
            QLabel('<b>Backend CPU priority:</b>'), self.combo1,
            QLabel('<b>Download Protocol Type:</b>'), self.chttps,
            self.vinfo1, self.vinfo2):
            vboxg2.addWidget(each_widget)

        self.qckb10 = QCheckBox('Run apt-get update on the created VM')
        self.qckb11 = QCheckBox('Run apt-get dist-upgrade on the created VM')
        self.qckb12 = QCheckBox('Run apt-get check on the created VM')
        self.qckb12 = QCheckBox('Run apt-get clean on the created VM')
        self.qckb13 = QCheckBox('Run apt-get autoremove on the created VM')
        self.qckb14 = QCheckBox('Try to Fix Broken packages if any on the VM')
        vboxg3 = QVBoxLayout(self.tab3)
        for each_widget in (self.qckb10, self.qckb11, self.qckb12, self.qckb13,
            self.qckb14):
            vboxg3.addWidget(each_widget)

        self.aptpkg = QTextEdit('build-essential vim mc wget git')
        self.aptppa = QLineEdit()
        self.aptppa.setPlaceholderText(' ppa:ninja-ide-developers/daily ')
        self.pippkg = QTextEdit('virtualenv')
        vboxg4 = QVBoxLayout(self.tab4)
        for each_widget in (
            QLabel('<b>Custom APT Ubuntu packages:</b> '), self.aptpkg,
            QLabel('<b>Custom APT Ubuntu PPA:</b>      '), self.aptppa,
            QLabel('<b>Custom PIP Python packages:</b> '), self.pippkg, ):
            vboxg4.addWidget(each_widget)

        self.buttonGroup = QButtonGroup()
        self.buttonGroup.buttonClicked[QAbstractButton].connect(self.get_de_pkg)
        vboxg5 = QVBoxLayout(self.tab5)
        for i, d in enumerate(('Ubuntu Unity', 'KDE Plasma', 'LXDE', 'XFCE')):
            button = QPushButton(d)
            button.setCheckable(True)
            button.setMinimumSize(75, 50)
            button.setToolTip(d)
            vboxg5.addWidget(button)
            self.buttonGroup.addButton(button)

        self.output = QTextEdit('''
        We have persistent objects, they are called files.  -Ken Thompson. ''')
        self.runbtn = QPushButton(QIcon.fromTheme("media-playback-start"),
            'Start Vagrant Instrumentation Now !')
        self.runbtn.setMinimumSize(75, 50)
        self.runbtn.clicked.connect(self.build)
        self.stopbt = QPushButton(QIcon.fromTheme("media-playback-stop"),
            'Stop Vagrant')
        self.stopbt.clicked.connect(lambda: self.process.stop())
        self.killbt = QPushButton(QIcon.fromTheme("application-exit"),
            'Force Kill Vagrant')
        self.killbt.clicked.connect(lambda: self.process.kill())
        vboxg6 = QVBoxLayout(self.tab6)
        for each_widget in (
            QLabel('<b>Multiprocessing Output Logs:</b> '), self.output,
            self.runbtn, self.stopbt, self.killbt):
            vboxg6.addWidget(each_widget)

        def must_glow(widget_list):
            ' apply an glow effect to the widget '
            for glow, each_widget in enumerate(widget_list):
                try:
                    if each_widget.graphicsEffect() is None:
                        glow = QGraphicsDropShadowEffect(self)
                        glow.setOffset(0)
                        glow.setBlurRadius(99)
                        glow.setColor(QColor(99, 255, 255))
                        each_widget.setGraphicsEffect(glow)
                        glow.setEnabled(True)
                except:
                    pass

        must_glow((self.runbtn, ))
        [a.setChecked(True) for a in (self.qckb1, self.qckb2, self.qckb3,
            self.qckb10, self.qckb11, self.qckb12, self.qckb13, self.qckb14)]
        self.mainwidget.setCurrentIndex(5)

    def get_de_pkg(self, button):
        ' get package from desktop name '
        if button.text() in 'Ubuntu Unity':
            self.desktop = 'ubuntu-desktop'
        elif button.text() in 'KDE Plasma':
            self.desktop = 'kubuntu-desktop'
        elif button.text() in 'LXDE':
            self.desktop = 'lubuntu-desktop'
        else:
            self.desktop = 'xubuntu-desktop'
        return self.desktop

    def get_random_name(self):
        ' return a random name of stars, planets and moons of solar system '
        return choice((getuser(), 'sun', 'mercury', 'venus', 'earth', 'mars',
            'neptun', 'ceres', 'pluto', 'haumea', 'makemake', 'eris', 'moon',
            'saturn', 'europa', 'ganymede', 'callisto', 'mimas', 'enceladus',
            'tethys', 'dione', 'rhea', 'titan', 'iapetus', 'miranda', 'ariel',
            'umbriel', 'titania', 'oberon', 'triton', 'charon', 'orcus', 'io',
            'ixion', 'varuna', 'quaoar', 'sedna', 'methone', 'jupiter', ))

    def readOutput(self):
        """Read and append output to the logBrowser"""
        self.output.append(str(self.process.readAllStandardOutput()))

    def readErrors(self):
        """Read and append errors to the logBrowser"""
        self.output.append(self.formatErrorMsg(str(
                                        self.process.readAllStandardError())))

    def formatErrorMsg(self, msg):
        """Format error messages in red color"""
        return self.formatMsg(msg, 'red')

    def formatInfoMsg(self, msg):
        """Format informative messages in blue color"""
        return self.formatMsg(msg, 'green')

    def formatMsg(self, msg, color):
        """Format message with the given color"""
        return '<font color="{}">{}</font>'.format(color, msg)

    def build(self):
        """Main function calling vagrant to generate the vm"""
        self.output.setText('')
        self.output.append(self.formatInfoMsg(
                            'INFO: OK: Starting at {}'.format(datetime.now())))
        self.runbtn.setDisabled(True)
        # Do I need to run the init ?, what the init does that im missing ?
        base = path.join(BASE, self.vmname.text())
        try:
            self.output.append(self.formatInfoMsg(
                ' INFO: OK: Created the Target Folder {}'.format(base)))
            makedirs(base)
            self.output.append(self.formatInfoMsg(
                ' INFO: OK: Changed to Target Folder {}'.format(base)))
            chdir(base)
            self.output.append(self.formatInfoMsg('INFO:Removing Vagrant file'))
            remove(path.join(base, 'Vagrantfile'))
        except:
            self.output.append(self.formatErrorMsg('ERROR:Remove Vagrant file'))
        cmd1 = getoutput('nice -n {} vagrant init'.format(self.combo1.value()),
                         shell=True)
        self.output.append(self.formatInfoMsg('INFO:OK:Init: {}'.format(cmd1)))
        cfg = CONFIG.format(self.vmname.text(), self.chttps.currentText(),
            self.vmcode.currentText(), self.vmcode.currentText(),
            'amd64' if self.vmarch.currentIndex() is 0 else 'i386',
            VBOXGUI if self.qckb3.isChecked() is True else '')
        self.output.append(self.formatInfoMsg('INFO:OK:Config: {}'.format(cfg)))
        with open(path.join(base, 'Vagrantfile'), 'w') as f:
            f.write(cfg)
            self.output.append(self.formatInfoMsg('INFO: Writing Vagrantfile'))
            f.close()
        prv = ''.join(('#!/usr/bin/env bash', linesep * 4,
        "PS1='\[\e[1;32m\][\u@\h \W]\$\[\e[0m\] ' ; HISTSIZE=5000",
        linesep * 2,
        '# Vagrant Bootstrap Provisioning autogenerated by Vagrant Ninja-IDE !',
        linesep * 2,
        'add-apt-repository -s -y {}'.format(str(self.aptppa.text()).strip()),
        linesep * 2,
        'apt-get -y update' if self.qckb10.isChecked() is True else '',
        linesep * 2,
        'apt-get -y -m dist-upgrade' if self.qckb11.isChecked() is True else '',
        linesep * 2,
        'apt-get -y -m autoremove' if self.qckb11.isChecked() is True else '',
        linesep * 2,
        'apt-get -y clean' if self.qckb11.isChecked() is True else '',
        linesep * 2,
        'dpkg --configure -a' if self.qckb11.isChecked() is True else '',
        linesep * 2,
        'apt-get -y -f install' if self.qckb11.isChecked() is True else '',
        linesep * 2,
        'apt-get -y check' if self.qckb11.isChecked() is True else '',
        linesep * 2,
        'apt-get -y --force-yes install {}'.format(self.aptpkg.toPlainText()),
        linesep * 2,
        'pip install --upgrade --verbose {}'.format(self.pippkg.toPlainText()),
        linesep * 2,
        'apt-get -y --force-yes -m install {}'.format(self.desktop),
        linesep * 2,
        ))
        self.output.append(self.formatInfoMsg('INFO:OK:Script: {}'.format(prv)))
        with open(path.join(base, 'bootstrap.sh'), 'w') as f:
            f.write(prv)
            self.output.append(self.formatInfoMsg('INFO: Writing bootstrap.sh'))
            f.close()
        try:
            chmod('bootstrap.sh', 0775)  # Py2
            self.output.append(self.formatInfoMsg('INFO: bootstrap.sh is 775'))
        except:
            chmod('bootstrap.sh', 0o775)  # Py3
            self.output.append(self.formatInfoMsg('INFO: bootstrap.sh is o775'))
        self.output.append(self.formatInfoMsg('INFO: OK: Running Vagrant Up !'))
        self.process.start('nice -n {} vagrant up'.format(self.combo1.value()))
        if not self.process.waitForStarted():
            self.output.append(self.formatErrorMsg('ERROR: FAIL: Vagrant Fail'))
            self.runbtn.setEnabled(True)
            return
        self.runbtn.setEnabled(True)
        chdir(path.expanduser("~"))

    def _process_finished(self):
        """finished sucessfully"""
        self.output.append(self.formatInfoMsg(
                            'INFO: OK: Finished at {}'.format(datetime.now())))
        if self.qckb2.isChecked() is True:
            with open('vagrant_ninja.log', 'w') as f:
                self.output.append(self.formatInfoMsg('INFO: OK: Writing .LOG'))
                f.write(self.output.toPlainText())
                f.close()
        if self.qckb1.isChecked() is True:
            try:
                startfile(str(path.join((BASE, 'vagrant'))))
            except:
                Popen(["xdg-open", str(path.join((BASE, 'vagrant')))])
        chdir(path.expanduser("~"))


###############################################################################


if __name__ == "__main__":
    print(__doc__)
