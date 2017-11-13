# -*- coding: utf-8 -*-
from collections import defaultdict
from copy import copy
from datetime import datetime, date, timedelta
from itertools import groupby

import pytz
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.core.mail import EmailMessage
from django.core.urlresolvers import reverse
from django.db import models
from django.db.models.query_utils import Q
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _, ugettext as __
from icalendar import Calendar, Event, vCalAddress, vText
from six import StringIO
from fields import JSONField

from common.choices import Choices
from common.models import TemplateModel
from dashboard.models import RecentActivity
from documents.models import Document, Folder
from meetings.repetitions import sync_meeting_repetitions
from profiles.models import Membership

import time
from common.authhelper import get_google_token_from_refresh_token, get_office_token_from_refresh_token


class MeetingManager(models.Manager):
    # TODO - convert to QuerySet as_manager after Django upgrade
    def for_membership(self, membership, only_own_meetings=False):
        queryset = self.filter(account=membership.account)
        # Only Admin should see all meetings
        if membership.is_admin:
            return queryset
        # limit guest to see only his committee meetings
        if membership.role == membership.ROLES.guest or only_own_meetings:
            # A longer form of: committee_ids = membership.committees.all().values_list('id', flat=True)
            # It results in one less join in resulting query, and so better plan
            committee_ids = membership.committees.through.objects.filter(membership=membership).values_list('committee_id', flat=True)
            direct_meetings = membership.meeting_set.through.objects.filter(membership=membership).values_list('meeting_id', flat=True)
            if membership.role in (membership.ROLES.guest, membership.ROLES.vendor, membership.ROLES.consultant):
                queryset = queryset.filter(Q(committee__id__in=committee_ids) | Q(id__in=direct_meetings))
            else:
                queryset = queryset.filter(Q(committee_id=None) | Q(committee__id__in=committee_ids) | Q(id__in=direct_meetings))

        return queryset

    @staticmethod
    def future_meetings_predicate():
        return {
            'where': ['exists (select 1 from {repetitions} where meeting_id = {meeting}.id and date >= current_date)'
                          .format(repetitions=MeetingRepetition._meta.db_table, meeting=Meeting._meta.db_table)]
        }

    @staticmethod
    def past_meetings_predicate():
        return {
            'where': ['not exists (select 1 from {repetitions} where meeting_id = {meeting}.id and date >= current_date)'
                          .format(repetitions=MeetingRepetition._meta.db_table, meeting=Meeting._meta.db_table)]
        }


class CalendarConnection(models.Model):
    CONNECT_TYPE = (
        ('office', 'Office 365'),
        ('google', 'Google'),
        ('ical', 'iCloud')
    )
    account = models.ForeignKey('accounts.Account', verbose_name=_('account'), related_name='calendar_connection')
    provider = models.CharField(max_length=20, choices=CONNECT_TYPE)
    email = models.CharField(verbose_name=_('email'), max_length=255)
    access_token = models.TextField(
                            verbose_name=_('access token'),
                            help_text=_('"oauth_token" (OAuth1) or access token (OAuth2)'),
                            blank=True
    )
    refresh_token = models.TextField(
                            verbose_name=_('refresh token'),
                            help_text=_('"oauth_token_secret" (OAuth1) or refresh token (OAuth2)'),
                            blank=True
    )
    expires_in = models.IntegerField(null=True, blank=True)

    calendar_id = models.CharField(verbose_name=_('Calendar'), max_length=255, null=True, blank=True)
    checked_add = models.BooleanField(default=True)
    checked_conflict = models.BooleanField(default=True)
    calendar_check_list = models.TextField(
                            verbose_name=_('Calendar Check list'),
                            help_text=_('Calendar ID list for checking conflicts'),
                            null=True, blank=True
    )

    class Meta:
        unique_together = ('account', 'provider')

    def get_access_token(self, redirect_uri):

        current_token = self.access_token
        expiration = self.expires_in

        now = int(time.time())
        if current_token and now < expiration:
            # Token still valid
            return current_token
        else:
            # Token expired
            refresh_token = self.refresh_token
            if self.provider == 'office':
                new_tokens = get_office_token_from_refresh_token(refresh_token, redirect_uri)
            if self.provider == 'google':
                new_tokens = get_google_token_from_refresh_token(refresh_token, redirect_uri)

            try:
                # Update session
                # expires_in is in seconds
                # Get current timestamp (seconds since Unix Epoch) and
                # add expires_in to get expiration time
                # Subtract 5 minutes to allow for clock differences
                expiration = int(time.time()) + new_tokens['expires_in'] - 300

                # save new token
                self.access_token = new_tokens['access_token']
                self.expires_in = expiration

                if self.provider == 'office':
                    self.refresh_token = new_tokens['refresh_token']
            except KeyError:    # key_error in new_tokens
                return False

            return new_tokens['access_token']


class Meeting(models.Model):
    STATUSES = Choices(
        (0, 'draft', _('Draft')),
        (1, 'published', _('Published')))

    REPEAT_TYPES = Choices(
        (0, 'once', _('No repeat')),
        (1, 'every_day', _('Every day')),
        (2, 'every_work_day', _('Every work day')),
        (3, 'every_week', _('Every week')),
        (4, 'every_month', _('Every month')),
        (5, 'every_year', _('Every year')),
    )

    # Not stored in database
    REPEAT_END_TYPES = Choices(
        ('never', _('Never')),
        ('max_count', _('Max count')),
        ('end_date', _('End date'))
    )

    name = models.CharField(_('name'), max_length=250)
    start = models.DateTimeField(_('from'))
    end = models.DateTimeField(_('to'))
    location = models.CharField(_('location'), max_length=250)
    # committee can be Null if Meeting attendees - All Board Members
    committee = models.ForeignKey('committees.Committee', verbose_name=_('committee'), null=True, blank=True,
                                  related_name='meetings')
    account = models.ForeignKey('accounts.Account', verbose_name=_('account'), related_name='meetings')

    description = models.TextField(verbose_name=_('description'), null=False, blank=False)

    is_event = models.BooleanField(default=False, verbose_name=_('event'), null=False)

    status = models.SmallIntegerField(verbose_name=_('status'), null=False, default=STATUSES.draft)
    last_published = models.DateTimeField(verbose_name=_('last published'), null=True, blank=True)
    last_email_sent = models.DateTimeField(verbose_name=_('last email sent'), null=True, blank=True)

    extra_members = models.ManyToManyField('profiles.Membership', db_table='meetings_meeting_member')

    repeat_type = models.SmallIntegerField(verbose_name=_('repeat type'), choices=REPEAT_TYPES, blank=True, default=REPEAT_TYPES.once)
    repeat_interval = models.SmallIntegerField(verbose_name=_('repeat interval'), blank=True, default=1)
    repeat_max_count = models.SmallIntegerField(verbose_name=_('repeat max count'), blank=True, null=True)
    repeat_end_date = models.DateField(verbose_name=_('repeat end date'), blank=True, null=True)
    # works for every_week repeat type: week days in form of bit mask i.e. repeat_week_days & 1 == True means Sun is on, days are 1-based
    repeat_week_days = models.SmallIntegerField(verbose_name=_('repeat week days'), blank=True, default=0)

    objects = MeetingManager()

    class Meta:
        ordering = ['-start']

    def __unicode__(self):
        return self.name

    def get_absolute_url(self):
        url_name = 'events:detail' if self.is_event else 'meetings:detail'
        return reverse(url_name, kwargs={'pk': self.pk, 'url': self.account.url})

    def publish(self):
        self.status = Meeting.STATUSES.published
        self.last_published = datetime.now()

    def unpublish(self):
        self.status = Meeting.STATUSES.draft
        self.last_published = None

    def clean(self):
        super(Meeting, self).clean()

        # Only one must be set
        if self.repeat_max_count:
            self.repeat_end_date = None

        if not self.repeat_week_days:
            self.repeat_week_days = 0  # cleanup type

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        super(Meeting, self).save(force_insert, force_update, using, update_fields)

        sync_meeting_repetitions(self)

    @property
    def repeat_end_type(self):
        if self.repeat_max_count:
            return self.REPEAT_END_TYPES.max_count
        elif self.repeat_end_date:
            return self.REPEAT_END_TYPES.end_date
        else:
            return self.REPEAT_END_TYPES.never

    @property
    def repeat_description(self):
        if self.repeat_type == self.REPEAT_TYPES.once:
            return ''

        result = self.get_repeat_type_display()
        if self.repeat_interval > 1:
            result += ' (%s %d)' % (__('every'), self.repeat_interval)

        if self.repeat_max_count:
            result += '%s %d' % (__(', max repetitions'), self.repeat_max_count)
        elif self.repeat_end_date:
            result += '%s %s' % (__(', until'), date_format(self.repeat_end_date))

        return result

    @cached_property
    def closest_repetition(self):
        future = self.repetitions.filter(date__gte=date.today()).order_by('date')[0:1]
        if future:
            return future[0]
        else:
            return self.repetitions.order_by('-date')[0]

    def reset_closest_repetition(self):
        if 'closest_repetition' in self.__dict__:
            del self.__dict__['closest_repetition']

    def future_repetitions(self):
        return self.repetitions.filter(date__gte=date.today()).order_by('date')[:10]

    @property
    def is_repeated(self):
        return bool(self.repeat_type)

    @property
    def cached_docs(self):
        if not hasattr(self, '_cached_docs'):
            cached_docs = defaultdict(list)
            try:
                for key, docs in groupby(self.folder.documents.all(), lambda x: x.type):
                    cached_docs[key] = list(docs)
            except Folder.DoesNotExist:
                # No docs then
                pass

            self._cached_docs = cached_docs
        return self._cached_docs

    @property
    def is_published(self):
        return self.status == Meeting.STATUSES.published

    @cached_property
    def creator(self):
        try:
            meeting_type = ContentType.objects.get(app_label="meetings", model="meeting")
            user = RecentActivity.objects.get(
                content_type=meeting_type,
                account=self.account,
                object_id=self.id,
                action_flag=RecentActivity.ADDITION
            ).init_user
            member = user.membership_set.get(account=self.account)
            return member
        except RecentActivity.DoesNotExist:
            pass
        return None

    @cached_property
    def extra_members_list(self):
        """ NOTE: Use only for view - is not reset on extra_members manipulations. """
        return list(self.extra_members.filter(user__is_active=True, is_active=True).select_related('user'))

    def _core_members(self):
        if self.committee is None:
            members = self.account.memberships.exclude(role=Membership.ROLES.guest)
        else:
            members = self.committee.memberships.all()
        # if self.creator is not None:
        #     members = members.exclude(user=self.creator.user)
        return members.filter(user__is_active=True, is_active=True).select_related('user')

    @property
    def members(self):
        result = list(self._core_members())
        for m in result:
            m.is_meeting_member_invited = False

        ids = {m.id for m in result}
        for m in self.extra_members.filter(user__is_active=True, is_active=True):
            if m.id not in ids:
                m.is_meeting_member_invited = True
                result.append(m)

        return result

    def check_user_is_member(self, user):
        if self.extra_members.filter(user=user).exists():
            return True

        return self._core_members().filter(user=user).exists()

    def get_minutes(self):
        if Document.MINUTES in self.cached_docs:
            return self.cached_docs[Document.MINUTES][0]
        return None

    def get_board_book(self):
        if Document.BOARD_BOOK in self.cached_docs:
            return self.cached_docs[Document.BOARD_BOOK][0]
        return None

    def get_agenda(self):
        if Document.AGENDA in self.cached_docs:
            return self.cached_docs[Document.AGENDA][0]
        return None

    def get_other_docs(self):
        if Document.OTHER in self.cached_docs:
            return self.cached_docs[Document.OTHER]
        return None

    def get_committee_name(self):
        if self.committee:
            return self.committee.name
        else:
            return _('All Board Members')

    def generate_ics(self, user, current_member):
        tz_info = current_member.timezone or timezone.get_default_timezone()

        meeting = self.closest_repetition.to_meeting_with_repetition_date()

        cal = Calendar()
        event = Event()
        event.add('summary', self.name)
        event.add('dtstart', meeting.start.astimezone(tz_info))
        event.add('dtend', meeting.end.astimezone(tz_info))
        # event.add('dtstamp', datetime(2005,4,4,0,10,0,tzinfo=pytz.utc))

        organizer = vCalAddress('MAILTO:' + user.email)
        organizer.params['cn'] = vText(user.get_full_name())

        event['organizer'] = organizer
        event['location'] = vText(self.location)
        event['uid'] = user.email
        event.add('priority', 1)

        for member in Membership.objects.filter(committees=self.committee, account=self.account):
            attendee = vCalAddress('MAILTO:' + member.user.email)
            attendee.params['cn'] = vText(member.user.get_full_name())
            event.add('attendee', attendee, encode=0)
        cal.add_component(event)
        return cal.to_ical()

    def send_details_email(self, save=True, template_name=TemplateModel.MEETING, exclude_user=None):
        ctx_dict = {
            'meeting': self.closest_repetition.to_meeting_with_repetition_date(),
            'site': Site.objects.get_current(),
            'protocol': settings.SSL_ON and 'https' or 'http',
            'link': self.get_absolute_url(),
        }

        for member in self.members:
            if exclude_user and member.user.id == exclude_user.id:
                continue

            ctx_dict['recipient'] = member

            tmpl = TemplateModel.objects.get(name=template_name)
            subject = tmpl.generate_title(ctx_dict) or self.account.name  # fixme: which one?
            message = tmpl.generate(ctx_dict)

            mail = EmailMessage(subject, message, settings.DEFAULT_FROM_EMAIL, [member.user.email])
            admin_emails = [m.user.email for m in self.account.get_admin_memberships() if m.id != member.id]
            if admin_emails:
                mail.extra_headers['Reply-To'] = ', '.join(admin_emails)

            mail.content_subtype = "html"
            # try:
            #     for doc in self.folder.documents.all():
            #         mail.attach(doc.name, doc.file.read())
            # except Folder.DoesNotExist:
            #     pass

            ics = self.generate_ics(self.creator.user, member)
            f = StringIO()
            f.name = 'invite.ics'
            f.write(ics)
            mail.attach(f.name, f.getvalue(), 'text/calendar')

            mail.send()
            f.close()

        self.last_email_sent = datetime.now()
        if save:
            self.save()


class MeetingAttendance(models.Model):
    PRESENT_TYPES = Choices(
        (0, 'absent', _('Absent')),
        (1, 'attended_in_person', _('Attended (in person)')),
        (2, 'attended_via_conference', _('Attended (via conference)'))
    )

    meeting = models.ForeignKey('meetings.Meeting', verbose_name=_('meeting'), null=False, related_name='attendance')
    user = models.ForeignKey('profiles.User', verbose_name=_('user'), null=False, related_name='attendance')
    present = models.SmallIntegerField(verbose_name=_('present'), choices=PRESENT_TYPES,
                                       null=True, blank=True)


class MeetingRepetitionManager(models.Manager):
    def for_membership(self, membership, only_own_meetings=False):
        return self.filter(meeting__in=Meeting.objects.for_membership(membership, only_own_meetings))


class MeetingRepetition(models.Model):
    """
    Repetition of Meeting.
    NOTE: every Meeting has at least 1 repetition created in Meeting.save() even if it's not repeated. For uniformity.
    """
    meeting = models.ForeignKey('meetings.Meeting', verbose_name=_('meeting'), null=False, related_name='repetitions', on_delete=models.CASCADE)

    # Date is UTC date, this way it's used all over code below.
    date = models.DateField(verbose_name=_('date'))

    objects = MeetingRepetitionManager()

    def __unicode__(self):
        return u'MeetingRepetition(meeting=%s, date=%s)' % (str(self.meeting_id), self.date.isoformat())

    @property
    def start(self):
        start = self.meeting.start.astimezone(pytz.utc)
        return timezone.make_aware(datetime.combine(self.date, start.time()), start.tzinfo)

    def to_meeting_with_repetition_date(self):
        meeting = copy(self.meeting)  # Shallow copy, just in case
        meeting.current_repetition = self
        delta = meeting.end - meeting.start
        meeting.start = self.start
        meeting.end = meeting.start + delta
        return meeting

    class Meta:
        unique_together = [('meeting', 'date')]


class MeetingNextRepetition(models.Model):
    """
    Handy class for fetching/filtering on next repetition, currently implemented via view.
    """
    meeting = models.OneToOneField(Meeting, verbose_name=_('meeting'), null=False, related_name='next_repetition', on_delete=models.DO_NOTHING)
    repetition = models.OneToOneField(MeetingRepetition, verbose_name=_('repetition'), on_delete=models.DO_NOTHING)
    date = models.DateField()

    class Meta:
        managed = False
