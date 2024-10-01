# -*- coding: utf-8 -*-
from http.client import HTTPConnection
from io import BytesIO
from urllib.error import HTTPError
from urllib.parse import quote, urlparse

from django.conf import settings
from django.core.files.storage import Storage, storages
from django.utils.deconstruct import deconstructible
from django.utils.encoding import force_bytes
from django.utils.functional import LazyObject


@deconstructible
class WebDAVStorage(Storage):
    """
    WebDAV Storage class for Django pluggable storage system.
    >>> s = WebDAVStorage()
    """

    def __init__(self, location=settings.WEBDAV_STORAGE_LOCATION, base_url=settings.MEDIA_URL,
                 public_url=settings.WEBDAV_PUBLIC_URL):
        self._location = location
        self._host = urlparse(location)[1]
        self._base_url = base_url
        self.public_url = public_url

    def _get_connection(self):
        conn = HTTPConnection(self._host)
        conn.set_debuglevel(0)
        return conn

    @staticmethod
    def _get_name(name):
        return quote(force_bytes(name))

    def exists(self, name):
        conn = self._get_connection()
        conn.request('HEAD', self._location + self._get_name(name))
        is_exists = conn.getresponse().status == 200
        conn.close()
        return is_exists

    def _save(self, name, content):
        conn = self._get_connection()
        conn.putrequest('PUT', self._location + self._get_name(name))
        conn.putheader('Content-Length', len(content))
        conn.endheaders()
        content.seek(0)
        conn.send(content.read())
        res = conn.getresponse()
        conn.close()
        if res.status != 201:
            raise HTTPError(self._location + name, res.status, res.reason, res.msg, res.fp)
        return name

    def _open(self, name, mode):
        from webdav_storage.fields import WebDAVFile
        assert (mode == 'rb'), 'DAV storage accepts only rb mode'
        return WebDAVFile(name, self, mode)

    def _read(self, name):
        conn = self._get_connection()
        conn.request('GET', self._location + self._get_name(name))
        res = conn.getresponse()
        if res.status != 200:
            raise ValueError(res.reason)
        temp_file = BytesIO()
        while True:
            chunk = res.read(32768)
            if chunk:
                temp_file.write(chunk)
            else:
                break
        temp_file.seek(0)
        conn.close()
        return temp_file

    def delete(self, name):
        conn = self._get_connection()
        conn.request('DELETE', self._location + self._get_name(name))
        res = conn.getresponse()
        if res.status != 204:
            raise HTTPError(self._location + name, res.status, res.reason, res.msg, res.fp)
        conn.close()
        return res

    def url(self, name):
        return self.get_public_url(quote(name))

    def get_public_url(self, name):
        return self.public_url.rstrip('/') + '/' + name.lstrip('/')

    def size(self, name):
        conn = self._get_connection()
        conn.request('HEAD', self._location + self._get_name(name))
        res = conn.getresponse()
        conn.close()
        if res.status != 200:
            raise HTTPError(self._location + name, res.status, res.reason, res.msg, res.fp)
        return res.getheader('Content-Length')


class DefaultWebDAVStorage(LazyObject):
    def _setup(self):
        try:
            self._wrapped = storages['webdav']
        except KeyError:
            self._wrapped = WebDAVStorage()


default_webdav_storage = DefaultWebDAVStorage()
