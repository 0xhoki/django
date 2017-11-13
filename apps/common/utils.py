# -*- coding: utf-8 -*-
import binascii
import hashlib
import random

import os
from PIL import Image
from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.test import TestCase
from django.urls.base import reverse
from django.utils.six import StringIO
from json import dumps
from rest_framework.pagination import PageNumberPagination

import ipaddress
import socket
import re

from accounts.account_helper import set_current_account


def get_temporary_image(ext='jpg'):
    io = StringIO()
    size = (200, 200)
    color = (255, 0, 0, 0)
    image = Image.new("RGBA", size, color)
    image.save(io, format='JPEG')
    name = 'test.{}'.format(ext)
    image_file = InMemoryUploadedFile(io, None, name, 'jpeg', io.len, None)
    image_file.seek(0)
    return image_file


def avatar_upload_to(instance, filename):
    """Generates likely unique image path using md5 hashes"""
    filename, ext = os.path.splitext(filename.lower())
    instance_id_hash = hashlib.md5(str(instance.id)).hexdigest()
    filename_hash = ''.join(random.sample(hashlib.md5(filename.encode('utf-8')).hexdigest(), 8))
    return settings.AVATAR_UPLOAD_ROOT_TEMPLATE.format(instance_id_hash=instance_id_hash,
                                                       filename_hash=filename_hash, ext=ext)


def random_with_n_digits(n):
    range_start = 10 ** (n - 1)
    range_end = (10 ** n) - 1
    return random.randint(range_start, range_end)


def random_hex(length):
    """Generate random hex number returned as unicode. Good for slugs and filenames."""
    return binascii.hexlify(os.urandom(length)).decode()[:length]


def crops_upload_to(instance, filename, crop_name):
    """
    Default function to specify a location to save crops to.

    :param instance: The model instance this crop field belongs to.
    :param filename: The image's filename this crop field operates on.
    :param crop_name: The crop name used when :attr:`CropFieldDescriptor.crop` was
        called.
    """
    filename, ext = os.path.splitext(os.path.split(filename)[-1])
    return settings.AVATAR_CROPS_UPLOAD_ROOT_TEMPLATE.format(filename=filename, crop_name=crop_name, ext=ext)


def is_valid_ip(ip_address):
    """ Check Validity of an IP address """

    try:
        ip = ipaddress.ip_address(u'' + ip_address)
        return True
    except ValueError as e:
        return False


def is_local_ip(ip_address):
    """ Check if IP is local """

    try:
        ip = ipaddress.ip_address(u'' + ip_address)
        return ip.is_loopback
    except ValueError as e:
        return None


def get_ip_address_from_request(request):
    """ Makes the best attempt to get the client's real IP or return the loopback """
    PRIVATE_IPS_PREFIX = ('10.', '172.', '192.', '127.')
    ip_address = ''
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if x_forwarded_for and ',' not in x_forwarded_for:
        if not x_forwarded_for.startswith(PRIVATE_IPS_PREFIX) and is_valid_ip(x_forwarded_for):
            ip_address = x_forwarded_for.strip()
    else:
        ips = [ip.strip() for ip in x_forwarded_for.split(',')]
        for ip in ips:
            if ip.startswith(PRIVATE_IPS_PREFIX):
                continue
            elif not is_valid_ip(ip):
                continue
            else:
                ip_address = ip
                break
    if not ip_address:
        x_real_ip = request.META.get('HTTP_X_REAL_IP', '')
        if x_real_ip:
            if not x_real_ip.startswith(PRIVATE_IPS_PREFIX) and is_valid_ip(x_real_ip):
                ip_address = x_real_ip.strip()
    if not ip_address:
        remote_addr = request.META.get('REMOTE_ADDR', '')
        if remote_addr:
            if not remote_addr.startswith(PRIVATE_IPS_PREFIX) and is_valid_ip(remote_addr):
                ip_address = remote_addr.strip()
    if not ip_address:
        ip_address = '127.0.0.1'
    return ip_address


class BaseTestCase(TestCase):
    fixtures = ['initial_data.json']

    def ajax(self, *args, **kwargs):
        kwargs['HTTP_X_REQUESTED_WITH'] = 'XMLHttpRequest'
        return self.client.post(*args, **kwargs)

    def ajax_get(self, *args, **kwargs):
        kwargs['HTTP_X_REQUESTED_WITH'] = 'XMLHttpRequest'
        return self.client.get(*args, **kwargs)

    def create_init_data(self):
        from committees.models import Committee
        from profiles.models import User, Membership
        from accounts.factories import AccountFactory
        from profiles.factories import AdminFactory, UserFactory
        from meetings.factories import MeetingFactory
        from committees.factories import CommitteeFactory

        self.account = AccountFactory()
        self.admin = AdminFactory(accounts=[self.account])

        UserFactory.create_batch(5, accounts=[self.account])
        CommitteeFactory.create_batch(5)

        for membership in Membership.objects.filter(user__in=User.objects.select_related().exclude(is_superuser=True)):
            membership.committees.add(*random.sample(set(Committee.objects.filter(account_id=membership.account_id)), 2))

        # Set last membership as comittee chairman (comittee_set)
        membership.committee_set.add(*random.sample(set(Committee.objects.filter(account_id=membership.account_id)), 1))
        self.meetings = MeetingFactory.create_batch(2)

        # Document creation is broken and needs fixing
        # for meeting in self.meetings:
        #     DocumentFactory.create_batch(2, meeting=meeting)
        self.membership = Membership.objects.filter(is_admin=False, account=self.account).order_by('pk')[0]
        self.membership_admin = Membership.objects.filter(is_admin=True, account=self.account)[0]

        self.user = self.membership.user

    def init_second_account(self):
        """Smaller account to have one. Just Board and users, no data."""
        from profiles.models import Membership
        from accounts.factories import AccountFactory
        from profiles.factories import AdminFactory, UserFactory

        self.account2 = AccountFactory()
        self.admin2 = AdminFactory(accounts=[self.account2])

        UserFactory.create_batch(5, accounts=[self.account2])

        self.membership2 = Membership.objects.filter(role=Membership.ROLES.member, account=self.account2)[0]
        self.membership_admin2 = Membership.objects.filter(is_admin=True, account=self.account2)[0]
        self.user2 = self.membership.user

    def create_membership(self, account=None, role=None, **kwargs):
        from profiles.factories import UserFactory

        account = account or self.account
        user = UserFactory(accounts=[account], accounts__role=role, **kwargs)
        return user, user.get_membership(account)

    def login_admin(self):
        self.client.login(username=self.admin.email, password='admin')
        self.session = self.client.session
        set_current_account(self, self.account)
        self.session.save()

    def login_member(self, email=None):
        email = email or self.user.email
        self.assertTrue(self.client.login(username=email, password='member'), msg="Can't login username={0}, password=member".format(email))
        self.session = self.client.session
        set_current_account(self, self.account)
        self.session.save()

    def login_admin2(self):
        self.assertTrue(self.client.login(username=self.admin2.email, password='admin'),
                        msg="Can't login admin2 username={0}, password=admin".format(self.admin2.email))
        self.session = self.client.session
        set_current_account(self, self.account2)
        self.session.save()


class AccJsonRequestsTestCase(BaseTestCase):
    def acc_get(self, viewname, account_url=None, assert_status_code=200, request_kwargs=None, **kwargs):
        kwargs['url'] = account_url or self.account.url
        resp = self.client.get(self._resolve_url(viewname, kwargs), **(request_kwargs or {}))
        self._assert_status_code(resp, assert_status_code)
        return resp

    def acc_post_json(self, viewname, json_data, account_url=None, assert_status_code=201, request_kwargs=None, **kwargs):
        kwargs['url'] = account_url or self.account.url
        resp = self.client.post(self._resolve_url(viewname, kwargs), dumps(json_data), content_type='application/json', **(request_kwargs or {}))
        self._assert_status_code(resp, assert_status_code)
        return resp

    def acc_put_json(self, viewname, json_data, account_url=None, assert_status_code=200, request_kwargs=None, **kwargs):
        kwargs['url'] = account_url or self.account.url
        resp = self.client.put(self._resolve_url(viewname, kwargs), dumps(json_data), content_type='application/json', **(request_kwargs or {}))
        self._assert_status_code(resp, assert_status_code)
        return resp

    def acc_delete(self, viewname, account_url=None, assert_status_code=204, request_kwargs=None, **kwargs):
        kwargs['url'] = account_url or self.account.url
        resp = self.client.delete(self._resolve_url(viewname, kwargs), content_type='application/json', **(request_kwargs or {}))
        self._assert_status_code(resp, assert_status_code)
        return resp

    def _resolve_url(self, viewname, kwargs):
        return reverse(viewname, kwargs=kwargs)

    def _assert_status_code(self, resp, assert_status_code):
        if assert_status_code is not None:
            self.assertEqual(assert_status_code, resp.status_code,
                             'Status code %d != %d, response:\n%s' % (assert_status_code, resp.status_code, resp.content))


class AlmostNoPagination(PageNumberPagination):
    """
    Class used to effectively disable pagination for things like membership, etc, where whole list is expected.
    """
    page_size = 1000


# Straightforward alternative for itertools.groupby as later requires sorting and not a dict by itself.
def dict_by_key(items, key_callable):
    result = {}
    for item in items:
        key = key_callable(item)
        if key in result:
            result[key].append(item)
        else:
            result[key] = [item]
    return result


us_timezones = ['US/Alaska',
                'US/Arizona',
                'US/Central',
                'US/Eastern',
                'US/Hawaii',
                'US/Mountain',
                'US/Pacific',
                'UTC']
us_timezones = [tz for tz in us_timezones]
us_timezones_set = set(us_timezones)
