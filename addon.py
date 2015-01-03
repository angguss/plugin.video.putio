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
import time

import requests

import sys
import xbmc
import xbmcaddon as xa
import xbmcgui
from resources.lib.common import PutioApiHandler
from resources.lib.exceptions import PutioAuthFailureException
from resources.lib.gui import play, populateDir
from resources import PLUGIN_ID

pluginUrl = sys.argv[0]
pluginId = 0
try:
    pluginId = int(sys.argv[1])
except ValueError:
    pluginId = 0

itemId = sys.argv[2].lstrip("?")
__addon__ = xa.Addon(PLUGIN_ID)

__addonname__       = __addon__.getAddonInfo( "name" )


def runOutOfContext():
    to_call = sys.argv[2]
    param1 = sys.argv[3]
    param2 = sys.argv[4]

    if to_call == "set_dir":
        set_dir(param1, param2)
    if to_call == "download":
        download(param1)

def download(id):
    xbmc.log("Downloading...")

def set_dir(type, id):
    was_set = False
    typeString = ""

    if type == "single_dir":
        __addon__.setSetting("single_monitor_dir", str(id))
        was_set = True
        typeString = __addon__.getLocalizedString(30024)
    elif type == "tv_dir":
        __addon__.setSetting("multi_tv_monitor_dir", str(id))
        was_set = True
        typeString = __addon__.getLocalizedString(30022)
    elif type == "movie_dir":
        __addon__.setSetting("multi_movie_monitor_dir", str(id))
        was_set = True
        typeString = __addon__.getLocalizedString(30021)
    elif type == "music_dir":
        __addon__.setSetting("multi_music_monitor_dir", str(id))
        was_set = True
        typeString = __addon__.getLocalizedString(30023)

    if was_set:
        dialog = xbmcgui.Dialog()
        dialog.ok(
                __addon__.getLocalizedString(30019),
                __addon__.getLocalizedString(30020) % typeString
            )

# Main program
def main():
    try:# Get the handler, pass in this plugin ID so we can get settings from the correct place
        putio = PutioApiHandler(PLUGIN_ID)

        # if a particular folder
        if itemId:
            item = putio.getItem(itemId)

            if item.content_type:
                if item.content_type == "application/x-directory":
                    populateDir(pluginUrl, pluginId, putio.getFolderListing(itemId), putio)
                else:
                    play(item, putio.getSubtitle(item))
        else:
            populateDir(pluginUrl, pluginId, putio.getRootListing(), putio)
    except PutioAuthFailureException as e:
        addonid = __addon__.getAddonInfo("id")
        __addon__ = xa.Addon(addonid)
        r = requests.get("https://put.io/xbmc/getuniqueid")
        o = json.loads(r.content)

        uniqueid = o['id']
        oauthtoken = __addon__.getSetting('oauthkey')

        if not oauthtoken:
            dialog = xbmcgui.Dialog()
            dialog.ok(
                "Oauth2 Key Required",
                "Visit http://put.io/xbmc and enter this code: %s\nthen press OK." % uniqueid
            )

        while not oauthtoken:
            try:
                # now we'll try getting oauth key by giving our uniqueid
                r = requests.get("http://put.io/xbmc/k/%s" % uniqueid)
                o = json.loads(r.content)
                oauthtoken = o['oauthtoken']

                if oauthtoken:
                    __addon__.setSetting("oauthkey", str(oauthtoken))
                    main()
            except Exception as e:
                dialog = xbmcgui.Dialog()
                dialog.ok("Oauth Key Error", str(e))

                raise e

            time.sleep(1)


if sys.argv[1] == "OOC":
    runOutOfContext()
else:
    main()




