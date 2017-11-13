# -*- coding: utf-8 -*-
import os

from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.sites.models import Site
from django.contrib.staticfiles.templatetags.staticfiles import static
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.core.mail.message import EmailMessage
from django.core.urlresolvers import reverse
from django.db import models
from django.db.models import Q
from django.template.defaultfilters import date as datefilter
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from mptt.models import MPTTModel, TreeForeignKey

from .managers import FolderManager
from common.storage_backends import StableS3BotoStorage
from common.models import TemplateModel
from common.utils import random_hex

if settings.USE_S3:
    file_storage = StableS3BotoStorage(acl='private', file_overwrite=False)
else:
    file_storage = FileSystemStorage()


class Folder(MPTTModel):
    TRASH_NAME = u'Trash'
    MEETINGS_NAME = u'Meeting Documents'
    COMMITTEES_NAME = u'Committee Documents'
    MEMBERSHIPS_NAME = u'Member Documents'
    RESERVED_NAMES = (TRASH_NAME, MEETINGS_NAME, COMMITTEES_NAME, MEMBERSHIPS_NAME)

    name = models.CharField(_('name'), max_length=255)
    parent = TreeForeignKey('self', verbose_name=_('parent'), related_name='children', null=True, blank=True,
                            on_delete=models.CASCADE)
    account = models.ForeignKey('accounts.Account', verbose_name=_('account'), related_name='folders', null=True,
                                on_delete=models.SET_NULL)
    user = models.ForeignKey('profiles.User', verbose_name=_('user'), related_name='folders', null=True, blank=True,
                             on_delete=models.SET_NULL)
    meeting = models.OneToOneField('meetings.Meeting', verbose_name=_('meeting'), blank=True, null=True,
                                   related_name='folder')
    committee = models.OneToOneField('committees.Committee', verbose_name=_('committee'), blank=True, null=True,
                                     related_name='folder')
    membership = models.OneToOneField('profiles.Membership', verbose_name=_('membership'), blank=True, null=True,
                                      related_name='private_folder')
    slug = models.SlugField(_('slug'), unique=True)
    created = models.DateTimeField(_('created'), auto_now_add=True)
    modified = models.DateTimeField(_('modified'), auto_now=True)
    protected = models.BooleanField(_('protected'), default=False,
                                    help_text=_('For special folders like "Trash"'))
    permissions = GenericRelation('permissions.ObjectPermission')

    objects = FolderManager()

    class MPTTMeta:
        order_insertion_by = ('name',)

    class Meta:
        unique_together = (('parent', 'name'),)
        ordering = ('name',)
        verbose_name = _('folder')
        verbose_name_plural = _('folders')

    def __unicode__(self):
        if self.meeting is not None:
            # Replace meeting id with date in name
            date_str = datefilter(self.meeting.start, 'N j, Y')
            return u'{0} ({1})'.format(self.meeting.name, date_str)
        if self.committee is not None:
            return self.committee.name
        if self.membership is not None:
            return unicode(self.membership)
        return self.name

    def clean(self, *args, **kwargs):
        if self.name and self.name.lower() in [n.lower() for n in Folder.RESERVED_NAMES]:
            raise ValidationError(_('That folder name is system reserved. Please choose another name.'))
        super(Folder, self).clean(*args, **kwargs)

    @classmethod
    def generate_slug(cls):
        exists = True
        while exists:
            slug = random_hex(length=20)
            exists = cls.objects.filter(slug=slug).exists()
        return slug

    @classmethod
    def generate_name_from_meeting(cls, meeting):
        id_str = unicode(meeting.id)
        return u'{0} ({1})'.format(meeting.name[:250 - len(id_str)], id_str)

    @classmethod
    def generate_name_from_committee(cls, committee):
        id_str = unicode(committee.id)
        return u'{0} ({1})'.format(committee.name[:250 - len(id_str)], id_str)

    @classmethod
    def generate_name_from_membership(cls, membership):
        id_str = unicode(membership.id)
        return u'{0} ({1})'.format(unicode(membership)[:250 - len(id_str)], id_str)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = Folder.generate_slug()
        super(Folder, self).save(*args, **kwargs)

    @property
    def is_account_root(self):
        return self.account is not None and self.account.url == self.name and self.level == 0

    @property
    def can_add_folders(self):
        # account root can add (while protected)
        return self.is_account_root or self.committee is not None or self.membership is not None or not self.protected

    @property
    def can_add_files(self):
        # meeting folder can add files (but no folders)
        return self.can_add_folders or self.meeting is not None

    @property
    def sort_date(self):
        # return date used for sorting
        return self.created if self.protected else self.modified

    def get_absolute_url(self):
        return reverse('folders:folder_detail', kwargs={'slug': self.slug, 'url': self.account.url}) if self.account else None

    def get_parents_without_root(self):
        return self.get_ancestors().filter(parent__isnull=False)


class AbstractDocument(models.Model):
    AGENDA, MINUTES, OTHER, BOARD_BOOK = range(1, 5)

    DOCS_TYPES = (
        (AGENDA, _('agenda')),
        (MINUTES, _('minutes')),
        (BOARD_BOOK, _('board_book')),
        (OTHER, _('other')),
    )

    name = models.CharField(_('name'), max_length=250, blank=True)
    file = models.FileField(_('file'), upload_to='uploads/docs/%Y%m%d', storage=file_storage)
    pdf_preview = models.FileField(_('pdf_preview'), upload_to='uploads/docs/%Y%m%d', storage=file_storage, blank=True, null=True)
    type = models.PositiveIntegerField(verbose_name=_('document type'), choices=DOCS_TYPES, default=OTHER)
    created_at = models.DateTimeField(_('upload date'), default=timezone.now)

    def __unicode__(self):
        return self.name if self.name else self.file.name

    class Meta:
        abstract = True

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None, clone=False):
        if not self.pk and not clone:
            name, extension = os.path.splitext(self.file.name)
            self.name = name + extension.lower()
            self.file.name = '{}.{}'.format(random_hex(8), extension[1:])
        super(AbstractDocument, self).save(force_insert, force_update, using, update_fields)

    def extension(self):
        name, extension = os.path.splitext(self.file.name)
        ext = extension[1:].lower()
        if ext in {'xlsx', 'xls'}:
            return 'xlsx'
        elif ext == 'pdf':
            return ext
        elif ext in ['docx', 'doc']:
            return 'docx'
        elif ext == 'png':
            return ext
        elif ext in ['jpg', 'jpeg']:
            return 'jpeg'
        elif ext in ['tif', 'tiff']:
            return 'tiff'
        elif ext in ['ppt', 'pptx']:
            return 'pptx'
        elif ext == 'mp4':
            return 'mp4'
        elif ext == 'avi':
            return 'avi'
        else:
            return 'gif'

    # Roughly mapping to Font-Awesome file-*-o
    EXTENSION_TO_TYPE_MAPPING = {
        'xlsx': 'excel',
        'docx': 'word',
        'png': 'image',
        'jpeg': 'image',
        'tiff': 'image',
        'pdf': 'pdf',
        'pptx': 'powerpoint',
    }

    def file_type(self):
        return self.EXTENSION_TO_TYPE_MAPPING.get(self.extension(), 'text')

    @property
    def filename(self):
        if self.type == self.AGENDA:
            return _('Meeting Agenda')
        if self.type == self.MINUTES:
            return _('Meeting Minutes')
        return os.path.basename(self.name or self.file.name)

    @property
    def sort_date(self):
        return self.created_at

    def get_download_url(self):
        return reverse('documents:download', kwargs={'document_id': self.pk})

    OFFICE_EXTENSIONS = ['docx', 'xlsx', 'pptx', 'doc', 'xls', 'ppt']
    VIEWABLE_EXTENSIONS = ['jpeg', 'png', 'gif', 'mp4', 'avi']

    def get_viewer_url(self):
        extension = self.extension()
        if extension == 'pdf':
            return static('pdfviewer/web/viewer.html') + '?file=' + self.get_download_url()
        elif extension.lower() in self.OFFICE_EXTENSIONS:
            return static('pdfviewer/web/viewer.html') + '?file=' + reverse('documents:pdf_preview', kwargs={'pk': self.pk})
        elif extension.lower() in self.VIEWABLE_EXTENSIONS:
            return self.get_download_url() + '?view=1'
        else:
            return None

    def get_viewer_or_download_url(self):
        return self.get_viewer_url() or self.get_download_url()


class Document(AbstractDocument):
    user = models.ForeignKey('profiles.User', verbose_name=_('user'), related_name='documents')
    account = models.ForeignKey('accounts.Account', verbose_name=_('account'), null=True, related_name='documents')
    previous_version = models.PositiveIntegerField(blank=True, null=True)
    folder = TreeForeignKey(Folder, verbose_name=_('folder'), related_name='documents', blank=True, null=True, on_delete=models.SET_NULL)
    permissions = GenericRelation('permissions.ObjectPermission')

    def get_committee_name(self):
        if self.committee:
            return self.committee.name
        else:
            return _('All Board Members')

    @property
    def revisions(self):
        return AuditTrail.objects.filter(latest_version=self.id).order_by('-created_at')

    def send_notification_email(self, members):

        ctx_dict = {
            'document': self,
            'site': Site.objects.get_current(),
            'protocol': settings.SSL_ON and 'https' or 'http',
            'previous_versions': self.revisions
        }

        for member in members:
            tmpl = TemplateModel.objects.get(name=TemplateModel.DOCUMENT_UPDATED)
            subject = tmpl.title or self.account.name  # fixme: which one?
            message = tmpl.generate(ctx_dict)

            mail = EmailMessage(subject, message, settings.DEFAULT_FROM_EMAIL, [member.user.email])
            mail.content_subtype = "html"

            mail.send()


class AuditTrail(AbstractDocument):
    UPDATED, DELETED = range(2)

    CHANGES_TYPES = (
        (UPDATED, _('update')),
        (DELETED, _('deleted'))
    )

    user = models.ForeignKey('profiles.User', verbose_name=_('user'), related_name='audits')
    change_type = models.PositiveIntegerField(verbose_name=_('type of changes'), choices=CHANGES_TYPES, default=UPDATED)
    latest_version = models.PositiveIntegerField(blank=True, null=True)
    revision = models.PositiveIntegerField(blank=True, null=True)

    class Meta:
        unique_together = (('latest_version', 'revision'),)

    def get_download_url(self):
        return reverse('documents:download-revision', kwargs={
            'document_id': self.latest_version, 'revision': self.revision})

    def save(self, *args, **kwargs):
        # set revision
        ids = list(Document.objects.filter(Q(previous_version=self.latest_version) | Q(
            previous_version=Document.objects.filter(id=self.latest_version).values_list(
                'previous_version', flat=True))).order_by('id').values_list('id', flat=True))
        if ids:
            latest_id = ids.pop()
            for doc_id in ids:  # rarely used, in best case never
                at = AuditTrail.objects.filter(latest_version=doc_id)
                at.update(latest_version=latest_id)
            revision = AuditTrail.objects.filter(latest_version=latest_id).count() + 1
        else:
            revision = 1
        self.revision = revision
        super(AuditTrail, self).save(*args, clone=True, **kwargs)


# import after models
from . import signals  # noqa
