#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import re
import glob
import json
import lxml.etree
from datetime import timedelta
from mc_util import McUtil
from mc_param import McConst


class McPluginManager:

    def __init__(self, param):
        self.param = param

    def getEnabledPluginNameList(self):
        ret = []
        for fn in glob.glob(McConst.pluginCfgFileGlobPattern):
            pluginName = McUtil.rreplace(os.path.basename(fn).replace("plugin-", "", 1), ".conf", "", 1)
            pluginPath = os.path.join(McConst.pluginsDir, pluginName)
            if not os.path.isdir(pluginPath):
                continue
            ret.append(pluginName)
        return ret

    def loadEnabledPlugins(self):
        for pluginName in self.getEnabledPluginNameList():
            with open(os.path.join(McConst.etcDir, "plugin-%s.conf" % (pluginName)), "r") as f:
                buf = f.read()
                if buf != "":
                    pluginCfg = json.loads(buf)
                else:
                    pluginCfg = dict()
            self._loadOnePlugin(pluginName, os.path.join(McConst.pluginsDir, pluginName), pluginCfg)

    def getStorageNameList(self):
        ret = os.listdir(McConst.storageDir)
        ret = [x for x in ret if os.path.isdir(os.path.join(McConst.storageDir, x))]
        return ret

    def loadStorageObjects(self):
        tDict = dict()                                          # {storage-name: [mirror-site-id]}
        for msId, msObj in self.param.mirrorSiteDict.items():
            for st in msObj.storageDict:
                if st not in tDict:
                    tDict[st] = []
                tDict[st].append(msId)

        storageNameList = sorted(list(tDict.keys()))            # [storage-name]
        if "file" in storageNameList:
            # always load the simplest file storage object first
            storageNameList.remove("file")
            storageNameList.insert(0, "file")

        for st in storageNameList:
            self.param.storageDict[st] = self._loadOneStorageObject(st, tDict[st])

    def getAdvertiserNameList(self):
        return os.listdir(McConst.advertiserDir)

    def loadAdvertiserObjects(self):
        tDict = dict()                                          # {advertiser-name: [mirror-site-id]}
        for msId, msObj in self.param.mirrorSiteDict.items():
            for name in msObj.advertiserDict:
                if name not in tDict:
                    tDict[name] = []
                tDict[name].append(msId)

        for name in sorted(list(tDict.keys())):
            self.param.advertiserDict[name] = self._loadOneAdvertiserObject(name, tDict[name])

    def _loadOnePlugin(self, name, path, cfgDict):
        # get metadata.xml file
        metadata_file = os.path.join(path, "metadata.xml")
        if not os.path.exists(metadata_file):
            raise Exception("plugin %s has no metadata.xml" % (name))
        if not os.path.isfile(metadata_file):
            raise Exception("metadata.xml for plugin %s is not a file" % (name))
        if not os.access(metadata_file, os.R_OK):
            raise Exception("metadata.xml for plugin %s is invalid" % (name))

        # check metadata.xml file content
        # FIXME
        rootElem = lxml.etree.parse(metadata_file).getroot()
        # if True:
        #     dtd = libxml2.parseDTD(None, constants.PATH_PLUGIN_DTD_FILE)
        #     ctxt = libxml2.newValidCtxt()
        #     messages = []
        #     ctxt.setValidityErrorHandler(lambda item, msgs: msgs.append(item), None, messages)
        #     if tree.validateDtd(ctxt, dtd) != 1:
        #         msg = ""
        #         for i in messages:
        #             msg += i
        #         raise exceptions.IncorrectPluginMetaFile(metadata_file, msg)

        # create McMirrorSite objects
        if rootElem.tag == "mirror-site":
            msId = rootElem.get("id")
            if msId in self.param.mirrorSiteDict:
                raise Exception("metadata.xml for plugin %s contains duplicate mirror-site %s" % (name, msId))
            self.param.mirrorSiteDict[msId] = McMirrorSite(self.param, path, rootElem, cfgDict)
        elif rootElem.tag in ["mirror-sites", "plugin"]:                    # FIXME: "plugin" is deprecated
            for child in rootElem.xpath("./mirror-site"):
                msId = child.get("id")
                if msId in self.param.mirrorSiteDict:
                    raise Exception("metadata.xml for plugin %s contains duplicate mirror-site %s" % (name, msId))
                self.param.mirrorSiteDict[msId] = McMirrorSite(self.param, path, child, cfgDict)
        else:
            raise Exception("metadata.xml content for plugin %s is invalid" % (name))

    def _loadOneStorageObject(self, name, mirrorSiteIdList):
        mod = __import__("storage.%s" % (name))
        mod = getattr(mod, name)

        # prepare storage initialization parameter
        param = {
            "temp-directory": os.path.join(McConst.tmpDir, "storage-%s" % (name)),
            "log-directory": os.path.join(McConst.logDir, "storage-%s" % (name)),
            "mirror-sites": dict(),
        }
        if mod.Storage.get_properties().get("with-integrated-advertiser", False):
            param.update({
                "listen-ip": self.param.listenIp,
            })
        for msId in mirrorSiteIdList:
            param["mirror-sites"][msId] = {
                "config-xml": self.param.mirrorSiteDict[msId].storageDict[name][0],
                "state-directory": self.param.mirrorSiteDict[msId].pluginStateDir,
                "data-directory": self.param.mirrorSiteDict[msId].getDataDirForStorage(name),
            }

        # prepare directories
        McUtil.ensureDir(param["temp-directory"])
        McUtil.ensureDir(param["log-directory"])

        # create object
        return mod.Storage(param)

    def _loadOneAdvertiserObject(self, name, mirrorSiteIdList):
        mod = __import__("advertiser.%s" % (name))
        mod = getattr(mod, name)

        # prepare advertiser initialization parameter
        param = {
            "listen-ip": self.param.listenIp,
            "temp-directory": os.path.join(McConst.tmpDir, "advertiser-%s" % (name)),
            "log-directory": os.path.join(McConst.logDir, "advertiser-%s" % (name)),
            "mirror-sites": dict(),
        }
        for msId in mirrorSiteIdList:
            param["mirror-sites"][msId] = {
                "config-xml": self.param.mirrorSiteDict[msId].advertiserDict[name][0],
                "state-directory": self.param.mirrorSiteDict[msId].pluginStateDir,
                "storage-param": dict()
            }
            for st in self.param.mirrorSiteDict[msId].storageDict:
                if st in mod.Advertiser.get_properties().get("storage-dependencies", []):
                    param["mirror-sites"][msId]["storage-param"][st] = self.param.storageDict[st].get_param(msId)

        # prepare directories
        McUtil.ensureDir(param["temp-directory"])
        McUtil.ensureDir(param["log-directory"])

        # create object
        return mod.Advertiser(param)


class McMirrorSite:

    def __init__(self, param, pluginDir, rootElem, cfgDict):
        self.param = param
        self.id = rootElem.get("id")
        self.cfgDict = cfgDict

        # persist mode
        self.bPersist = cfgDict.get("persist", False)

        # master directory
        if self.bPersist:
            self.masterDir = os.path.join(McConst.varDir, self.id)
        else:
            self.masterDir = os.path.join(McConst.cacheDir, self.id)
        McUtil.ensureDir(self.masterDir)

        # state directory (plugin can use it)
        self.pluginStateDir = os.path.join(self.masterDir, "state")
        McUtil.ensureDir(self.pluginStateDir)

        # log directory (plugin can use it)
        self.logDir = os.path.join(McConst.logDir, "mirror-site-%s" % (self.id))
        self.mainUpdaterLogFile = os.path.join(self.logDir, "updater.log")              # log file for initializer/updater/maintainer stdout/stderr
        McUtil.ensureDir(self.logDir)

        # storage
        self.storageDict = dict()                       # {name:(config-xml,data-directory)}
        for child in rootElem.xpath("./storage"):
            st = child.get("type")
            if st not in self.param.pluginManager.getStorageNameList():
                raise Exception("mirror site %s: invalid storage type %s" % (self.id, st))
            # record outer xml
            self.storageDict[st] = (lxml.etree.tostring(child, encoding="unicode"), self.getDataDirForStorage(st))
            # create data directory
            McUtil.ensureDir(self.getDataDirForStorage(st))

        # advertiser
        self.advertiserDict = dict()                 # {name:(config-xml)}
        for child in rootElem.xpath("./advertiser"):
            st = child.get("type")
            if st not in self.param.pluginManager.getAdvertiserNameList():
                raise Exception("mirror site %s: invalid advertiser type %s" % (self.id, st))
            # record outer xml
            self.advertiserDict[st] = (lxml.etree.tostring(child, encoding="unicode"))

        # initializer
        self.initializerExe = None
        if True:
            slist = rootElem.xpath("./initializer")
            if len(slist) > 0:
                self.initializerExe = slist[0].xpath("./executable")[0].text
                self.initializerExe = os.path.join(pluginDir, self.initializerExe)

        # updater
        self.updaterExe = None
        self.schedType = None              # "interval" or "cronexpr"
        self.schedInterval = None          # timedelta
        self.schedCronExpr = None          # string
        self.updateRetryType = None        # "interval" or "cronexpr"
        self.updateRetryInterval = None    # timedelta
        self.updateRetryCronExpr = None    # string
        if True:
            slist = rootElem.xpath("./updater")
            if len(slist) > 0:
                self.updaterExe = slist[0].xpath("./executable")[0].text
                self.updaterExe = os.path.join(pluginDir, self.updaterExe)

                tag = slist[0].xpath("./schedule")[0]
                self.schedType = tag.get("type")
                if self.schedType == "interval":
                    self.schedInterval = self._parseInterval(tag.text)
                elif self.schedType == "cronexpr":
                    self.schedCronExpr = self._parseCronExpr(tag.text)
                else:
                    raise Exception("mirror site %s: invalid schedule type %s" % (self.id, self.schedType))

                if len(slist[0].xpath("./retry-after-failure")) > 0:
                    tag = slist[0].xpath("./retry-after-failure")[0]
                    self.updateRetryType = tag.get("type")
                    if self.updateRetryType == "interval":
                        self.updateRetryInterval = self._parseInterval(tag.text)
                    elif self.updateRetryType == "cronexpr":
                        if self.schedType == "interval":
                            raise Exception("mirror site %s: invalid retry-after-update type %s" % (self.id, self.updateRetryType))
                        self.updateRetryCronExpr = self._parseCronExpr(tag.text)
                    else:
                        raise Exception("mirror site %s: invalid retry-after-update type %s" % (self.id, self.updateRetryType))

        # maintainer
        self.maintainerExe = None
        if True:
            slist = rootElem.xpath("./maintainer")
            if len(slist) > 0:
                self.maintainerExe = slist[0].xpath(".//executable")[0].text
                self.maintainerExe = os.path.join(pluginDir, self.maintainerExe)

    def getDataDirForStorage(self, storageName):
        return os.path.join(self.masterDir, "storage-%s" % (storageName))

    def _parseInterval(self, intervalStr):
        m = re.match("([0-9]+)(h|d|w|m)", intervalStr)
        if m is None:
            raise Exception("invalid interval %s" % (intervalStr))

        if m.group(2) == "h":
            return timedelta(hours=int(m.group(1)))
        elif m.group(2) == "d":
            return timedelta(days=int(m.group(1)))
        elif m.group(2) == "w":
            return timedelta(weeks=int(m.group(1)))
        elif m.group(2) == "m":
            return timedelta(months=int(m.group(1)))
        else:
            assert False

    def _parseCronExpr(self, cronExprStr):
        # FIXME: should add checking
        return cronExprStr
