# -*- coding: utf-8 -*-
from django.conf import settings
from django.core.files.storage import default_storage
from django.forms import forms
from django.template.defaultfilters import filesizeformat

from webdav_storage.fields import WebDAVImageField, WebDAVFieldFile, WebDAVImageFieldFile, WebDAVFileField


def domain4url(url, shift=4, length=2):
    """
    Host determined by the last character: shift (from the end) and length
    """
    if not settings.STATIC_DOMAINS:
        return ''

    return settings.STATIC_DOMAINS[
        int(str(url)[(0 - shift - length):(0 - shift)].encode('hex') or '1', 16) % len(settings.STATIC_DOMAINS)
    ]


class NginxFileBase():
    def public_url(self):
        return '{}/storage/public/{}'.format(getattr(settings, 'NGINX_PREFIX', ''), self.name)


class NginxImageFileBase(NginxFileBase):
    hosts = settings.STATIC_DOMAINS or []

    def host(self):
        if not self.hosts or not self.name:
            return settings.NGINX_IMAGES_PREFIX
        return domain4url(self.name, shift=4)

    def resize_url(self, size):
        """
        Get url for resized image
        """
        return self._url('p', size)

    def resize_relative_url(self, size):
        """
        Get url for resized image (relative - without domain)
        """
        return self._url('p', size, relative=True)

    def crop_url(self, size):
        """
        Get url for croped image
        """
        return self._url('c', size)

    def crop_relative_url(self, size):
        """
        Get url for croped image (relative - without domain)
        """
        return self._url('c', size, relative=True)

    def _url(self, type, size, relative=False):
        if relative:
            return '/{}/{}/{}'.format(type, size, self.name)
        else:
            return '{}/{}/{}/{}'.format(self.host(), type, size, self.name)

    def _get_url(self):
        return self._url('r', '100x100')


class NginxImageFile(NginxImageFileBase, WebDAVImageFieldFile):
    pass


class NginxImageFileNull(NginxImageFileBase):
    """
    This field is used for default images. For example, default avatar or default cover.
    """
    def __init__(self, name=None):
        self.name = name


class NginxImageField(WebDAVImageField):
    """
    Field for images which support resize with custom image class
    """
    attr_class = NginxImageFile


class NginxFile(NginxFileBase, WebDAVFieldFile):
    pass


class CustomNginxImageField(NginxImageField):
    """
    5MB - 5242880
    10MB - 10485760
    20MB - 20971520
    50MB - 52428800
    """

    def __init__(self, *args, **kwargs):
        self.content_types = kwargs.pop('content_types', [])
        self.max_upload_size = kwargs.pop('max_upload_size', 5242880)  # 5MB
        super(CustomNginxImageField, self).__init__(*args, **kwargs)

    def clean(self, *args, **kwargs):
        data = super(CustomNginxImageField, self).clean(*args, **kwargs)

        file = data.file
        try:
            content_type = file.content_type
            if content_type in self.content_types:
                if file._size > self.max_upload_size:
                    raise forms.ValidationError(
                        'Превышен максимальный размер файла {}. Ваш файл {}'.format(
                            filesizeformat(self.max_upload_size),
                            filesizeformat(file._size)))
            else:
                raise forms.ValidationError('Формат файла не поддерживается')
        except AttributeError:
            pass

        return data

    def deconstruct(self):
        name, path, args, kwargs = super(CustomNginxImageField, self).deconstruct()
        kwargs.pop('content_types', None)
        kwargs.pop('max_upload_size', None)
        return name, path, args, kwargs


class CustomFileField(WebDAVFileField):
    """
    5MB - 5242880
    10MB - 10485760
    20MB - 20971520
    30MB - 31457820
    50MB - 52428800
    """
    attr_class = NginxFile

    def __init__(self, verbose_name=None, name=None, upload_to='', **kwargs):
        if 'storage' not in kwargs:
            kwargs['storage'] = default_storage
        if 'validators' not in kwargs:
            kwargs['validators'] = []

        self.max_upload_size = kwargs.pop('max_upload_size', None)
        super(CustomFileField, self).__init__(verbose_name, name, upload_to, **kwargs)

    def clean(self, *args, **kwargs):
        data = super(CustomFileField, self).clean(*args, **kwargs)
        max_upload_size = self.max_upload_size or 52428800

        file = data.file
        try:
            if file._size > max_upload_size:
                raise forms.ValidationError(
                    'Превышен максимальный размер файла {}. Ваш файл - {}'.format(
                        filesizeformat(max_upload_size),
                        filesizeformat(file._size)))
        except AttributeError:
            pass
        return data
