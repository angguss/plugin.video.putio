# coding: utf-8
#
# put.io xbmc addon
# Copyright (C) 2014 Angus Rigby <angus@angusrigby.co.uk>
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
import time
import re

import xbmc
import xbmcaddon as xa
import xbmcgui as xg
import xbmcplugin as xp
from resources import PLUGIN_ID
from resources.lib.common import PutioApiHandler
from resources.lib.exceptions import PutioAuthFailureException
__addon__ = xa.Addon(PLUGIN_ID)

# Service to handle polling of Put.io API and download new files
class PutioService(object):

    def __init__(self):
        self.putioHandler = None

        self.types = {
            "movies": 0,
            "tv": 1,
            "music": 2
        }

        self.refreshSettings()
        self.run()

    def refreshSettings(self):
        # get time to wait between polls from settings
        # and do some cool parsing
        self.time_to_wait = self.parseTime(__addon__.getSetting("poll_time"))
        self.resume_downloads = __addon__.getSetting("resume_downloads") == "true"
        self.recursive_scan = __addon__.getSetting("subfolder_search") == "true"
        self.speed_limit_kbs = int(__addon__.getSetting("limit_download_speed"))

    # takes minutes, convert to millisec
    def parseTime(self, time):
        return int(time) * 60 * 1000

    def updateProgressDialog(self, downloaded, speed, name, total):
        if self.show_download_bar:
            if self.progressdialog and total != -1:
                percentage = (float(downloaded) / total) * 100
                self.progressdialog.update(int(percentage), __addon__.getLocalizedString(30036) % speed, name)

    def formatSpeed(self, speed):
        speed_formatted = __addon__.getLocalizedString(30040)
        if speed > 1000:
            speed_formatted = '{0:.2f}'.format(speed / 1024) + "mb/s"
        else:
            speed_formatted = '{0:.2f}'.format(speed) + "kb/s"
        return speed_formatted

    def progressCallback(self, start_time, downloaded, downloaded_session, total, name):
        cur_time = time.time()

        elapsed = cur_time - start_time

        # default speed, can't get much slower eh?
        speed = 1

        if elapsed > 0 and downloaded_session > 0:
            # default to kb, no-one's interested in b/s
            speed = (float(downloaded_session) / elapsed) / 1024

        self.speed_limit_kbs = int(__addon__.getSetting("limit_download_speed"))
        # calculate time to sleep in order to reduce the speed
        sleep_time = 0

        if self.speed_limit_kbs > 0:
            slowed_speed = speed

            while slowed_speed >= self.speed_limit_kbs:
                elapsed = time.time() - start_time
                slowed_speed = (float(downloaded_session) / elapsed) / 1024
                xbmc.sleep(100)
                speed_formatted = self.formatSpeed(speed)
                self.updateProgressDialog(downloaded, speed_formatted, name, total)

        speed_formatted = self.formatSpeed(speed)
        self.updateProgressDialog(downloaded, speed_formatted, name, total)

    # Callback to determine whether to kill this service
    def cancelCallback(self):
        return xbmc.abortRequested

    # Traverse a put.io directory and get all non-directory items
    def traverseDirectory(self, id, recursive = True):
        folder_listing = self.putioHandler.getFolderListing(id)
        item_listing = []

        non_directory_listing = [i for i in folder_listing if i.content_type != "application/x-directory"]
        directory_listing = [i for i in folder_listing if i.content_type == "application/x-directory"]

        for directory in directory_listing:
            item_listing.extend(self.traverseDirectory(directory.id, recursive))

        item_listing.extend(non_directory_listing)

        return item_listing

    def download(self, check_directory, dest_directory, move_to_subdirectory=False):

        # now we can make a call to put.io
        # NOTE: root may take ages
        item_listing = self.traverseDirectory(check_directory, self.recursive_scan)

        progress_total = len(item_listing)

        if progress_total <= 0:
            return

        self.show_download_bar = __addon__.getSetting("show_download_bar") == "true"

        # if the download bar is enabled, create one
        if self.show_download_bar:
            self.progressdialog = xg.DialogProgressBG()
            self.progressdialog.create(__addon__.getLocalizedString(30036) % '', '')

        delete_after_download = __addon__.getSetting("delete_after_download") == "true"
        clean_filenames = __addon__.getSetting("clean_filenames") == "true"

        # Need to keep track of whether the file has been downloaded
        downloaded_file = False

        for item in item_listing:
            if self.show_download_bar:
                self.progressdialog.update(0, __addon__.getLocalizedString(30036) % item.name, item.name)

            # Currently synchronous call
            # TODO: Implement concurrent downloads if setting is > 1
            self.putioHandler.downloadItem(item, dest_directory, self.progressCallback, self.cancelCallback, self.resume_downloads)

            # At this point the file is downloaded, we can now do some post-processing
            if delete_after_download:
                item.delete()

            if move_to_subdirectory:
                subdirectory = xbmc.getCleanMovieTitle(item.name)[0]
                subdirectory = re.sub(r'(S[0-9][0-9]E[0-9][0-9])', '', subdirectory)
                subdirectory = xbmc.makeLegalFilename(subdirectory).strip()

                # check if directory already exists
                new_dest_directory = os.path.join(dest_directory, subdirectory).strip()

                if not os.path.exists(new_dest_directory):
                    os.mkdir(new_dest_directory)
                if os.path.exists(new_dest_directory):
                    os.rename(os.path.join(dest_directory, item.name), os.path.join(new_dest_directory, item.name))

                    # Make sure to skip clean_filenames if we're doing TV or music,
                    # otherwise we use the SXXEXX etc from the title and break
                    # library updates
                    dest_directory = new_dest_directory

            # Some people like to have files renamed to keep it tidy
            # TODO: Make this user configurable, based on string maybe?
            if clean_filenames:
                resolution = ''
                res = ['720p', '1080p', '1080i', '480p']
                for r in res:
                    if r in item.name.lower():
                        resolution = r
                        break

                clean_title = xbmc.getCleanMovieTitle(item.name)
                extension = os.path.splitext(filename)[1]
                os.rename(
                    os.path.join(dest_directory, filename),
                    os.path.join(dest_directory, "{} {} {}".format(clean_title[0], resolution, extension))
                    )
            downloaded_file = True


        if self.show_download_bar:
            self.progressdialog.close()

        return downloaded_file


    def singleDownload(self):
        check_directory = __addon__.getSetting('single_dir')
        dest_directory = __addon__.getSetting('single_monitor_dir')
        if check_directory == "-1" or dest_directory == "":
            xbmc.log("Single download is enabled but directories haven't been set up", level=xbmc.LOGDEBUG)
            return

        downloaded_file = self.download(check_directory, dest_directory)
        if downloaded_file:
            xbmc.executebuiltin('XBMC.UpdateLibrary(video)')

    def multiDownload(self, download_type):
        check_directory = 0
        dest_directory = ''
        move_to_subdirectory = False

        if download_type == self.types["movies"]:
            check_directory = __addon__.getSetting("multi_movie_monitor_dir")
            dest_directory = __addon__.getSetting("multi_movie_dir")
        elif download_type == self.types["tv"]:
            check_directory = __addon__.getSetting("multi_tv_monitor_dir")
            dest_directory = __addon__.getSetting("multi_tv_dir")
            move_to_subdirectory = True
        elif download_type == self.types["music"]:
            check_directory = __addon__.getSetting("multi_music_monitor_dir")
            dest_directory = __addon__.getSetting("multi_music_dir")

        if download_type != self.types["tv"] and download_type != self.types["movies"]:
            return

        # at this point we can assume that we have an ID to check with put.io API
        # and a matching destination download directory
        if check_directory == "-1" or dest_directory == "":
            xbmc.log("multiple downloads are enabled but some settings were not set", level=xbmc.LOGDEBUG)
            return

        downloaded_file = self.download(check_directory, dest_directory, move_to_subdirectory)

        # Only update library for the type and if the download actually finished
        if downloaded_file:
            if download_type == self.types["movies"] or download_type == self.types["tv"]:
                xbmc.executebuiltin('XBMC.UpdateLibrary(video)')
            elif download_type == self.types["music"]:
                xbmc.executebuiltin('XBMC.UpdateLibrary(music)')

    def run(self):
        # need a putio api object
        auth_failure = False
        try:
            self.putioHandler = PutioApiHandler(__addon__.getAddonInfo("id"))
        except PutioAuthFailureException:
            dialog = xg.Dialog()
            dialog.ok(
                __addon__.getLocalizedString(30001),
                __addon__.getLocalizedString(30041) +
                __addon__.getLocalizedString(30042)
            )
            auth_failure = True

        xbmc.sleep(2000)

        i = 0

        while not xbmc.abortRequested and not auth_failure:
            self.refreshSettings()
            single_download_mode = __addon__.getSetting("single_download_enabled")

            if single_download_mode == "true":
                self.singleDownload()
            else:
                # multi download mode, separate directories for music, movies and TV. Need to check
                self.multiDownload(self.types["movies"])
                self.multiDownload(self.types["tv"])
                self.multiDownload(self.types["music"])

            time_left = self.time_to_wait
            while xbmc.abortRequested and time_left > 0:
                time_left -= 1000
                xbmc.sleep(1000)


putio = PutioService()