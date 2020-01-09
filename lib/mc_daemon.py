#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import sys
import signal
import shutil
import socket
import logging
import asyncio
import asyncio_glib
from mc_util import McUtil
from mc_util import StdoutRedirector
from mc_util import AvahiServiceRegister
from mc_param import McConst
from mc_plugin import McPluginManager
from mc_updater import McMirrorSiteUpdater
from mc_advertiser import McAdvertiser


class McDaemon:

    def __init__(self, param):
        self.param = param

    def run(self):
        McUtil.ensureDir(McConst.logDir)
        McUtil.mkDirAndClear(McConst.runDir)
        McUtil.mkDirAndClear(McConst.tmpDir)
        try:
            sys.stdout = StdoutRedirector(os.path.join(McConst.tmpDir, "mirrors.out"))
            sys.stderr = sys.stdout

            logging.getLogger().addHandler(logging.StreamHandler(sys.stderr))
            logging.getLogger().setLevel(logging.INFO)
            logging.info("Program begins.")

            # create mainloop
            asyncio.set_event_loop_policy(asyncio_glib.GLibEventLoopPolicy())
            self.param.mainloop = asyncio.get_event_loop()

            # write pid file
            with open(os.path.join(McConst.runDir, "mirrors.pid"), "w") as f:
                f.write(str(os.getpid()))

            # load plugins
            self.pluginManager = McPluginManager(self.param)
            self.pluginManager.loadPlugins()
            logging.info("Plugins loaded: %s" % (",".join(self.param.pluginList)))

            # updater
            self.param.updater = McMirrorSiteUpdater(self.param)
            logging.info("Mirror site updater initialized.")

            # advertiser
            self.param.advertiser = McAdvertiser(self.param)
            logging.info("Advertiser initialized.")

            # register serivce
            if self.param.avahiSupport:
                self.param.avahiObj = AvahiServiceRegister()
                self.param.avahiObj.add_service(socket.gethostname(), "_mirrors._tcp", self.param.apiPort)
                self.param.avahiObj.start()

            # start main loop
            logging.info("Mainloop begins.")
            self.param.mainloop.add_signal_handler(signal.SIGINT, self._sigHandlerINT)
            self.param.mainloop.add_signal_handler(signal.SIGTERM, self._sigHandlerTERM)
            self.param.mainloop.run_forever()
            logging.info("Mainloop exits.")
        finally:
            if self.param.avahiObj is not None:
                self.param.avahiObj.stop()
            if self.param.updater is not None:
                self.param.updater.dispose()
            if self.param.advertiser is not None:
                self.param.advertiser.dispose()
            logging.shutdown()
            shutil.rmtree(McConst.tmpDir)
            shutil.rmtree(McConst.runDir)

    def _sigHandlerINT(self):
        logging.info("SIGINT received.")
        self.param.mainloop.stop()
        return True

    def _sigHandlerTERM(self):
        logging.info("SIGTERM received.")
        self.param.mainloop.stop()
        return True
