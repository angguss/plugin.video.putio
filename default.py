# coding: utf-8
#
# put.io xbmc addon
# Copyright (C) 2009  Alper Kanat <tunix@raptiye.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import json
import os
import time

import requests

import sys
import xbmc
import xbmcaddon as xa
import xbmcgui
import xbmcplugin
from resources.lib import putio

PLUGIN_ID = "plugin.video.putio"

pluginUrl = sys.argv[0]
pluginId = int(sys.argv[1])
itemId = sys.argv[2].lstrip("?")
addon = xa.Addon(PLUGIN_ID)


class PutioAuthFailureException(Exception):
    def __init__(self, header, message, duration=10000, icon="error.png"):
        self.header = header
        self.message = message
        self.duration = duration
        self.icon = icon


def populateDir(pluginUrl, pluginId, listing):
    for item in listing:
        if item.screenshot:
            screenshot = item.screenshot
        else:
            screenshot = os.path.join(
                addon.getAddonInfo("path"),
                "resources",
                "images",
                "mid-folder.png"
            )

        url = "%s?%s" % (pluginUrl, item.id)
        listItem = xbmcgui.ListItem(
            item.name,
            item.name,
            screenshot,
            screenshot
        )

        listItem.setInfo(item.content_type, {
            'originaltitle': item.name,
            'title': item.name,
            'sorttitle': item.name
        })

        xbmcplugin.addDirectoryItem(
            pluginId,
            url,
            listItem,
            "application/x-directory" == item.content_type
        )

    xbmcplugin.endOfDirectory(pluginId)


def play(item):
    player = xbmc.Player()

    if item.screenshot:
        screenshot = item.screenshot
    else:
        screenshot = item.icon

    listItem = xbmcgui.ListItem(
        item.name,
        item.name,
        screenshot,
        screenshot
    )

    listItem.setInfo('video', {'Title': item.name})
    player.play(item.stream_url, listItem)


class PutioApiHandler(object):
    """
    Class to handle putio api calls for XBMC actions
    """

    wantedItemTypes = ("folder", "movie", "audio", "unknown", "file")
    subtitleTypes = ("srt", "sub")

    def __init__(self, pluginId):
        self.addon = xa.Addon(pluginId)
        self.oauthkey = self.addon.getSetting("oauthkey").replace('-', '')

        if not self.oauthkey:
            raise PutioAuthFailureException(
                self.addon.getLocalizedString(30001),
                self.addon.getLocalizedString(30002)
            )

        self.apiclient = putio.Client(self.oauthkey)

    def getItem(self, itemId):
        return self.apiclient.File.GET(itemId)

    def getRootListing(self):
        items = []

        for item in self.apiclient.File.list(parent_id=0):
            items.append(item)

        return items

    def getFolderListing(self, folderId, isItemFilterActive=True):
        items = []

        for item in self.apiclient.File.list(parent_id=folderId):
            if isItemFilterActive:
                continue

            items.append(item)

        return items


# Main program
def main():
    putio = PutioApiHandler(addon.getAddonInfo("id"))

    if itemId:
        item = putio.getItem(itemId)

        if item.content_type:
            if item.content_type == "application/x-directory":
                populateDir(pluginUrl, pluginId, putio.getFolderListing(itemId))
            else:
                play(item)
    else:
        populateDir(pluginUrl, pluginId, putio.getRootListing())

try:
    main()
except PutioAuthFailureException as e:
    addonid = addon.getAddonInfo("id")
    addon = xa.Addon(addonid)
    r = requests.get("https://put.io/xbmc/getuniqueid")
    o = json.loads(r.content)
    uniqueid = o['id']
    oauthtoken = addon.getSetting('oauthkey')

    if not oauthtoken:
        dialog = xbmcgui.Dialog()
        dialog.ok(
            "Oauth2 Key Required",
            "Visit put.io/xbmc and enter this code: %s\nthen press OK." % uniqueid
        )

    while not oauthtoken:
        try:
            # now we'll try getting oauth key by giving our uniqueid
            r = requests.get("http://put.io/xbmc/k/%s" % uniqueid)
            o = json.loads(r.content)
            oauthtoken = o['oauthtoken']

            if oauthtoken:
                addon.setSetting("oauthkey", str(oauthtoken))
                main()
        except Exception as e:
            dialog = xbmcgui.Dialog()
            dialog.ok("Oauth Key Error", str(e))

            raise e

        time.sleep(1)
