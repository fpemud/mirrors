#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import signal
import logging
import subprocess
import atomicwrites
from mc_util import McUtil


class Advertiser:

    @staticmethod
    def get_properties():
        return {
            "storage-dependencies": ["file"],
        }

    def __init__(self, param):
        self._tmpDir = param["temp-directory"]
        self._logDir = param["log-directory"]
        self._virtRootDir = os.path.join(self._tmpDir, "vroot")
        self._cfgFn = os.path.join(self._tmpDir, "httpd.conf")
        self._pidFile = os.path.join(self._tmpDir, "httpd.pid")
        self._errorLogFile = os.path.join(self._logDir, "error.log")
        self._accessLogFile = os.path.join(self._logDir, "access.log")
        self._listenIp = param["listen-ip"]
        self._mirrorSiteDict = param["mirror-sites"]

        self._port = None
        self._proc = None
        self._advertisedMirrorSiteIdList = []
        try:
            self._port = McUtil.getFreeSocketPort("tcp")
            self._generateVirtualRootDir()
            self._generateCfgFn()
            self._proc = subprocess.Popen(["/usr/sbin/apache2", "-f", self._cfgFn, "-DFOREGROUND"], cwd=self._virtRootDir)
            McUtil.waitSocketPortForProc("tcp", self._listenIp, self._port, self._proc)
            logging.info("Advertiser (httpdir) started, listening on port %d." % (self._port))
        except Exception:
            self.dispose()
            raise

    def dispose(self):
        if self._proc is not None:
            self._proc.terminate()
            self._proc.wait()
            self._proc = None
        if self._port is not None:
            self._port = None
        McUtil.forceDelete(self._virtRootDir)

    def get_access_info(self, mirror_site_id):
        assert mirror_site_id in self._mirrorSiteDict
        return {
            "url": "http://{IP}:%d/%s" % (self._port, mirror_site_id),
            "description": "",
        }

    def advertise_mirror_site(self, mirror_site_id):
        assert mirror_site_id in self._mirrorSiteDict
        self._advertisedMirrorSiteIdList.append(mirror_site_id)
        self._generateVirtualRootDir()
        self._generateCfgFn()
        os.kill(self._proc.pid, signal.SIGUSR1)

    def _generateVirtualRootDir(self):
        McUtil.ensureDir(self._virtRootDir)

        # create new directories
        for msId in self._advertisedMirrorSiteIdList:
            realPath = self._mirrorSiteDict[msId]["storage-param"]["file"]["data-directory"]
            dn = os.path.join(self._virtRootDir, msId)
            if not os.path.exists(dn):
                os.symlink(realPath, dn)

    def _generateCfgFn(self):
        modulesDir = "/usr/lib64/apache2/modules"
        buf = ""

        # modules
        buf += "LoadModule log_config_module      %s/mod_log_config.so\n" % (modulesDir)
        buf += "LoadModule unixd_module           %s/mod_unixd.so\n" % (modulesDir)
        buf += "LoadModule alias_module           %s/mod_alias.so\n" % (modulesDir)
        buf += "LoadModule authz_core_module      %s/mod_authz_core.so\n" % (modulesDir)            # it's strange why we need this module and Require directive when we have no auth at all
        buf += "LoadModule autoindex_module       %s/mod_autoindex.so\n" % (modulesDir)
        # add mod_log_rotate
        buf += "\n"

        # global settings
        buf += 'PidFile "%s"\n' % (self._pidFile)
        buf += 'ErrorLog "%s"\n' % (self._errorLogFile)
        buf += r'LogFormat "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"" common' + "\n"
        buf += 'CustomLog "%s" common\n' % (self._accessLogFile)
        buf += "\n"
        buf += "Listen %d http\n" % (self._port)
        buf += "ServerName none\n"                              # dummy value
        buf += "\n"
        buf += 'DocumentRoot "%s"\n' % (self._virtRootDir)
        buf += '<Directory "%s">\n' % (self._virtRootDir)
        buf += '  Require all granted\n'
        buf += '</Directory>\n'

        # write file atomically
        with atomicwrites.atomic_write(self._cfgFn, overwrite=True) as f:
            f.write(buf)
