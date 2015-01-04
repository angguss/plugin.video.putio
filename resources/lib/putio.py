# coding: utf-8

"""
A python wrapper for put.io APIv2

https://github.com/putdotio/putio-apiv2-python

Documentation: See https://api.put.io/v2/docs

Usage:

import putio2
client = putio2.Client('..oauth token here...')
# list files
files = client.File.list()
...
# add a new transfer
client.Transfer.add('http://example.com/good.torrent')

"""

import traceback
import json
import logging
import os
import re
import time
from urllib import urlencode

import requests

import iso8601

logger = logging.getLogger(__name__)

API_URL = 'https://api.put.io/v2'
ACCESS_TOKEN_URL = 'https://api.put.io/v2/oauth2/access_token'
AUTHENTICATION_URL = 'https://api.put.io/v2/oauth2/authenticate'


class AuthHelper(object):
    def __init__(self, client_id, client_secret, redirect_uri):
        self.client_id = client_id
        self.client_secret = client_secret
        self.callback_url = redirect_uri

    def get_authentication_url(self):
        params = {
            'client_id': self.client_id,
            'response_type': 'code',
            'redirect_uri': self.callback_url
        }
        query_str = urlencode(params)

        return AUTHENTICATION_URL + "?" + query_str

    def get_access_token(self, code):
        params = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'authorization_code',
            'redirect_uri': self.callback_url,
            'code': code
        }
        r = requests.get(ACCESS_TOKEN_URL, params=params, verify=False)
        d = json.loads(r.content)
        return d['access_token']


class Client(object):
    def __init__(self, access_token):
        self.access_token = access_token

        # Keep resource classes as attributes of client.
        # Pass client to resource classes so resource object
        # can use the client.
        attributes = {'client': self}
        self.File = type('File', (_File,), attributes)
        self.Transfer = type('Transfer', (_Transfer,), attributes)

    def request(self, path, method='GET', params=None, data=None, files=None, headers=None, raw=False, stream=True):
        '''
        Wrapper around requests.request()

        Prepends API_URL to path.
        Inserts oauth_token to query params.
        Parses response as JSON and returns it.
        '''

        if not params:
            params = {}

        params['oauth_token'] = self.access_token
        url = API_URL + path

        logger.debug('url: %s', url)

        r = requests.request(
            method,
            url,
            params=params,
            data=data,
            files=files,
            headers=headers,
            allow_redirects=True,
            verify=False,
            stream=stream
        )

        logger.debug('response: %s', r)

        if raw:
            return r

        logger.debug('content: %s', r.content)

        try:
            r = json.loads(r.content)
        except ValueError:
            raise Exception('Server didn\'t send valid JSON:\n%s\n%s' % (r, r.content))

        if r['status'] == 'ERROR':
            raise Exception(r['error_type'])

        return r


class _BaseResource(object):
    def __init__(self, resource_dict):
        '''Construct the object from a dict'''

        self.__dict__.update(resource_dict)

        try:
            self.created_at = iso8601.parse_date(self.created_at)
        except:
            pass

    def __str__(self):
        return self.name.encode('utf-8')

    def __repr__(self):
        try:
            # shorten name for display
            return '%s(id=%s, name="%s")' % (self.__class__.__name__, self.id, str(self))
        except:
            return object.__repr__()


class _File(_BaseResource):
    @classmethod
    def list(cls, parent_id=0, as_dict=False):
        d = cls.client.request('/files/list', params={'parent_id': parent_id})
        files = d['files']
        files = [cls(f) for f in files]

        if as_dict:
            ids = [f.id for f in files]

            return dict(zip(ids, files))

        return files

    @classmethod
    def get_path(cls, id=0):
        cur_id = id
        path = ''
        while cur_id != 0:
            d = cls.GET(cur_id)

            if cur_id != id:
                path = d.name + "/" + path
            else:
                path = d.name

            cur_id = d.parent_id
        path = "/" + path
        return path

    @classmethod
    def GET(cls, id=0, as_dict=False):
        d = cls.client.request('/files/%s' % id, params={})
        f = cls(dict(d['file']))

        return f


    @classmethod
    def upload(cls, path, name):
        with open(path) as f:
            files = {'file': (name, f)}
            d = cls.client.request('/files/upload', method='POST', files=files)
            f = d['file']

            return cls(f)

    @property
    def files(self):
        '''Helper function for listing inside of directory'''

        return self.list(parent_id=self.id)

    @property
    def stream_url(self):
        return API_URL + '/files/%s/stream?oauth_token=%s' % (self.id, self.client.access_token)

    def download(self, dest='.', range=None, progress_callback=None, cancel_callback=None, resume=True):

        # means that download was originally started but failed (kodi crash maybe?)
        if os.path.exists(os.path.join(dest, self.name + ".part")):
            if resume:
                range = os.path.getsize(os.path.join(dest, self.name + ".part"))
            else:
                os.remove(os.path.join(dest, self.name + ".part"))

        total_length = -1

        if range:
            # If no content-length was sent then it's resuming a previously stopped
            # download and won't send content-length so will send a new request to try to
            # get the length
            content_length_r = self.client.request('/files/%s/download' % self.id, raw=True, headers=None)
            try:
                total_length = int(content_length_r.headers['Content-Length'])
            except KeyError:
                total_length = -1

            headers = {'Range': 'bytes={}-{}'.format(str(range),total_length)}
        else:
            headers = None

        r = self.client.request('/files/%s/download' % self.id, raw=True, headers=headers)


        if not range:
            total_length = int(r.headers['Content-Length'])

        filename = ''

        # this regex is provided by put.io but seems to fail everytime
        try:
            filename = re.match('attachment; filename\="(.*)"', r.headers['Content-Disposition']).groups()[0]
        except AttributeError:
            filename = self.name

        downloaded = 0

        if range:
            downloaded = range

        chunk_ct = 0


        if os.path.exists(os.path.join(dest, filename)):
            return

        # download to .part file
        download_finished = False
        was_canceled = False
        started_time = time.time()
        downloaded_this_session = 0
        with open(os.path.join(dest, filename + ".part"), 'ab') as f:
            for data in r.iter_content(chunk_size=1024):
                downloaded += len(data)
                downloaded_this_session += len(data)
                chunk_ct += 1

                if chunk_ct > 32:
                    if progress_callback:
                        progress_callback(started_time, downloaded, downloaded_this_session, total_length, self.name)
                    chunk_ct = 0
                f.write(data)

                if cancel_callback:
                    if cancel_callback():
                        was_canceled = True

                if was_canceled:
                    break

            download_finished = True

        if not download_finished and was_canceled:
            os.delete(os.path.join(dest, filename + ".part"))
        else:
            os.rename(os.path.join(dest, filename + ".part"), os.path.join(dest, filename))

    # delete method changed, now posts with files_id
    def delete(self):
        # return self.client.request('/files/%s/delete' % self.id)
        return self.client.request('/files/delete',
            method='POST',
            data=dict(
                file_ids=self.id
            )
        )

    @property
    def subtitle(self):
        return self.client.request('/files/%s/subtitles' % self.id)


class _Transfer(_BaseResource):
    @classmethod
    def list(cls, parent_id=0, as_dict=False):
        d = cls.client.request('/transfers/list')
        transfers = d['transfers']
        transfers = [cls(t) for t in transfers]

        if as_dict:
            ids = [t.id for t in transfers]
            return dict(zip(ids, transfers))

        return transfers

    @classmethod
    def add(cls, url, parent_id=0, extract=False):
        d = cls.client.request(
            '/transfers/add',
            method='POST',
            data=dict(
                url=url,
                parent_id=parent_id,
                extract=extract
            )
        )
        t = d['transfer']

        return cls(t)
