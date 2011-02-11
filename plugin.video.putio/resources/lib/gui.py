# coding: utf-8
# 
# put.io xbmc addon
# Copyright (C) 2009  Alper Kanat <alper@put.io>
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

import xbmcgui as xg
import xbmcplugin as xp

iconMapping = {
    "folder": "DefaultFolder.png",
    "movie": "DefaultVideo.png",
    "audio": "DefaultAudio.png"
}

def getIcon(fileType):
    return iconMapping.get(fileType, "DefaultFile.png")

def populateDir(pluginUrl, pluginId, listing):
    for item in listing:
        if item.is_dir:
            url = "%s?%s" % (pluginUrl, item.id)
        else:
            url = item.get_stream_url()
        
        listItem = xg.ListItem(
            item.name,
            item.name,
            getIcon(item.type),
            getIcon(item.type)
        )
        
        xp.addDirectoryItem(
            pluginId,
            url,
            listItem,
            item.is_dir
        )
    
    xp.endOfDirectory(pluginId)