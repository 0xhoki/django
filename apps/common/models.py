# -*- coding: utf-8 -*-
from django.contrib.sites.models import Site
from django.db import models
from django.template import Context
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.core.mail import send_mail
from django.dispatch import receiver
from django.template.loader import render_to_string
from django.conf import settings

from common.shortcuts import get_template_from_string

class Feedback(models.Model):
    email = models.EmailField(_('email address'))
    message = models.TextField(_('message'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Feedback')
        verbose_name_plural = _('Feedbacks')

    def send_feedback(self):
        ctx_dict = {'email': self.email}
        subject = render_to_string('registration/feedback_email_subject.txt',
                                   ctx_dict)
        # Email subject *must not* contain newlines
        subject = ''.join(subject.splitlines())
        self.message = self.message + '\n' + Site.objects.get_current().domain
        send_mail(subject, self.message, self.email, [i[1] for i in settings.ADMINS])

    def __unicode__(self):
        return 'Feedback from {}'.format(self.email)


@receiver(models.signals.post_save, sender=Feedback)
def send_feedback_via_email(sender, created, instance, **kwargs):
    if created:
        instance.send_feedback()


class TemplateModel(models.Model):
    (ACTIVATE, RESET, MEETING, INVITE, CANCEL, TRIAL, TRIAL_IS_OVER_CANCEL,
     PAID, TRIAL_REMINDER, DOC, DOCUMENT_UPDATED, MEETING_REMINDER, VOTING_INVITATION) = range(1, 14)

    CHOICES = (
        (ACTIVATE, _('account activation template')),
        (RESET, _('password reset template')),
        (MEETING, _('meeting invitation template')),
        (INVITE, _('member invitation template')),
        (CANCEL, _('account canceled template')),
        (TRIAL, _('trial is over template')),
        (TRIAL_IS_OVER_CANCEL, _('trial is over and account cancel template')),
        (PAID, _('paid is over template')),
        (TRIAL_REMINDER, _('trial reminder template')),
        (DOC, _('add document template')),
        (DOCUMENT_UPDATED, _('document updated template')),
        (MEETING_REMINDER, _('meeting reminder updated template')),
        (VOTING_INVITATION, _('voting invitation template')),
    )

    name = models.IntegerField(_('name'), choices=CHOICES, unique=True, editable=False)
    title = models.CharField(_('subject'), max_length=100)
    html = models.TextField(_('content'), help_text=_('Do not change text in braces'))

    def __unicode__(self):
        return self.get_name_display().title()

    def generate(self, content):
        content['title'] = self.title
        t = get_template_from_string(self.html)
        return t.render(content)

    def generate_title(self, content):
        content['title'] = self.title
        t = get_template_from_string(self.title)
        return t.render(content)

    class Meta:
        verbose_name = _('Template editor')
        verbose_name_plural = _('Template editors')


class UpdateNotification(models.Model):
    notification_text = models.TextField()
    is_active = models.BooleanField(default=True)
    publish_date = models.DateTimeField(default=timezone.now)
    details_link = models.URLField()

    def __unicode__(self):
        return self.notification_text