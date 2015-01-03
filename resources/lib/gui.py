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
#

import os

import xbmc
import xbmcaddon as xa
import xbmcgui as xg
import xbmcplugin as xp
from resources import PLUGIN_ID

__all__ = ("populateDir", "play")

__addon__ = xa.Addon(PLUGIN_ID)

def populateDir(pluginUrl, pluginId, listing, putio):
    single_download_enabled = __addon__.getSetting('single_download_enabled')

    context_text = __addon__.getLocalizedString(30037)

    for item in listing:

        if item.screenshot:
            screenshot = item.screenshot
        else:
            screenshot = os.path.join(
                __addon__.getAddonInfo("path"),
                "resources",
                "images",
                "mid-folder.png"
            )

        url = "%s?%s" % (pluginUrl, item.id)
        listItem = xg.ListItem(
            item.name,
            item.name,
            screenshot,
            screenshot
        )

        commands = []

        # commands.append((__addon__.getLocalizedString(30039), 'RunScript(' + PLUGIN_ID + ', OOC, download, "' + str(item.id) + '")', ))

        if single_download_enabled == True or single_download_enabled == "true":
            commands.append((context_text % __addon__.getLocalizedString(30016), 'RunScript(' + PLUGIN_ID + ', OOC, set_dir, single_dir, "' + str(item.id) + '")', ))
        else:
            commands.append((context_text % __addon__.getLocalizedString(30014), 'RunScript(' + PLUGIN_ID + ', OOC, set_dir, tv_dir, "' + str(item.id) + '")', ))
            commands.append((context_text % __addon__.getLocalizedString(30013), 'RunScript(' + PLUGIN_ID + ', OOC, set_dir, movie_dir, "' + str(item.id) + '")', ))
            commands.append((context_text % __addon__.getLocalizedString(30015), 'RunScript(' + PLUGIN_ID + ', OOC, set_dir, music_dir, "' + str(item.id) + '")', ))

        listItem.setInfo(item.content_type, {
            'originaltitle': item.name,
            'title': item.name,
            'sorttitle': item.name
        })

        listItem.addContextMenuItems(commands)

        xp.addDirectoryItem(
            pluginId,
            url,
            listItem,
            "application/x-directory" == item.content_type
        )

    xp.endOfDirectory(pluginId)


def play(item, subtitle=None):
    player = xbmc.Player()

    if item.screenshot:
        screenshot = item.screenshot
    else:
        screenshot = item.icon

    listItem = xg.ListItem(
        item.name,
        item.name,
        screenshot,
        screenshot
    )

    listItem.setInfo('video', {'Title': item.name})
    player.play(item.stream_url, listItem)

    if subtitle:
        print "Adding subtitle to player!"
        player.setSubtitles(subtitle)
