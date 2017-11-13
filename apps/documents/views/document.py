# -*- coding: utf-8 -*-
import mimetypes
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta
from os.path import splitext, basename
from subprocess import PIPE
from wsgiref.util import FileWrapper

import os
from django.conf import settings
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import File
from django.core.urlresolvers import reverse
from django.db.models import F
from django.http import HttpResponseBadRequest, HttpResponse
from django.http.response import BadHeaderError
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.template import RequestContext
from django.template.loader import render_to_string
from django.utils.translation import ugettext
from django.utils.translation import ugettext_lazy as _
from django.views.generic import FormView
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView, BaseFormView, View

from accounts.account_helper import get_current_account
from accounts.models import Account
from common import signals
from common.mixins import AjaxableResponseMixin, RecentActivityMixin, SelectBoardRequiredMixin, MemberNotificationMixin
from dashboard.models import RecentActivity
from documents.forms import DocumentForm, DocumentDeleteForm, MessageForm, FolderMoveForm
from documents.models import Document, AuditTrail, Folder
from permissions import PERMISSIONS
from permissions.mixins import PermissionMixin
from permissions.shortcuts import has_object_permission

ALL_COMMITTEES = -1


class DocumentQuerysetMixin(object):
    def get_queryset(self):
        account = get_current_account(self.request)
        queryset = Document.objects.filter(account=account)
        return queryset


class DocumentAjaxCreateView(AjaxableResponseMixin, RecentActivityMixin,
                             SelectBoardRequiredMixin, CreateView):
    """Has no PermissionMixin because permissions checking is done on folder view."""
    form_class = DocumentForm

    def post(self, request, *args, **kwargs):
        self.object = None
        if 'type' in request.POST:
            file = request.FILES.get(request.POST.get('type'))
            request.FILES['file'] = file
        size = request.FILES['file'].size
        account = get_current_account(request)
        if account.plan.max_storage and account.total_storage + size > account.plan.max_storage:
            return self.render_to_json_response({
                'status': 'error',
                'message': ugettext('Limit of data storage for your billing plan is exceeded,'
                                    ' you can upgrade it in your profile!')},
                status=403)
        Account.objects.filter(id=account.id).update(total_storage=F('total_storage') + size)
        return super(DocumentAjaxCreateView, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        old_doc_id = form.data.get('old_document')
        if old_doc_id:
            old_doc_id = int(old_doc_id)

        self.object = form.save(commit=False)
        self.object.account = get_current_account(self.request)
        if 'type' in self.request.POST:
            for i, t in Document.DOCS_TYPES:
                if t == self.request.POST.get('type'):
                    self.object.type = i
                    break
        self.object.user = self.request.user
        if old_doc_id:
            self.object.previous_version = old_doc_id
        self.object.save()

        if old_doc_id:
            revisions = AuditTrail.objects.filter(latest_version=old_doc_id)
            revisions.update(latest_version=self.object.id)

        action_flag = RecentActivity.ADDITION
        data = {'status': 'success', 'pk': self.object.pk}
        if 'action' in self.request.POST:
            if self.request.POST.get('action') == 'update':
                action_flag = RecentActivity.CHANGE
                if 'meeting' in self.request.POST:
                    self.object.folder = self.object.account.meetings.get(id=self.request.POST['meeting']).folder
                    self.object.save()
                # copy folder & permissions from old document
                if old_doc_id:
                    old_doc = self.object.account.documents.get(id=old_doc_id)
                    # folder
                    self.object.folder = old_doc.folder
                    self.object.save(update_fields=['folder'])
                    # permissions
                    for perm in old_doc.permissions.all():
                        perm.id = None
                        perm.object_id = self.object.id
                        perm.save()
                data['html'] = render_to_string('documents/document_item.html',
                                                {'doc': self.object, 'user': self.request.user})
                data['type'] = self.object.get_type_display()
        self.save_recent_activity(action_flag=action_flag)
        signals.view_create.send(sender=self.__class__, instance=self.object, request=self.request)
        return self.render_to_json_response(data)


class DocumentAjaxDeleteView(AjaxableResponseMixin, SelectBoardRequiredMixin,
                             DocumentQuerysetMixin, PermissionMixin, BaseFormView):
    permission = (Document, PERMISSIONS.delete)
    form_class = DocumentDeleteForm

    def get_permission_object(self):
        document_id = self.request.POST.get('document_id')
        return get_object_or_404(self.get_queryset(), id=document_id)

    def form_invalid(self, form):
        return HttpResponseBadRequest()

    def form_valid(self, form):
        document_id = form.cleaned_data['document_id']
        change_type = form.cleaned_data['change_type']
        document = get_object_or_404(self.get_queryset(), id=document_id)

        # create AuditTrail from deleted/updated document
        AuditTrail.objects.create(
            name=document.name,
            file=document.file,
            type=document.type,
            user_id=self.request.user.id,
            change_type=change_type,
            latest_version=document.id,
            created_at=document.created_at,
        )

        data = {'doc_id': document.id, 'doc_type': document.type}

        RecentActivity.objects.filter(
            object_id=document.id,
            content_type_id=ContentType.objects.get_for_model(document),
        ).delete()
        document.delete()

        new_version = Document.objects.filter(previous_version=document_id)
        if new_version:
            ats = AuditTrail.objects.filter(latest_version=document_id)
            ats.update(latest_version=new_version[0].id)

        return self.render_to_json_response(data)


class DocumentDownloadView(SelectBoardRequiredMixin, DocumentQuerysetMixin, PermissionMixin, View):
    permission = (Document, PERMISSIONS.view)

    def and_permission(self, account, membership):
        document = get_object_or_404(self.get_queryset(), id=self.kwargs['document_id'])
        self.document = document
        return has_object_permission(membership, document, PERMISSIONS.view)

    def get(self, request, document_id):
        return self.do_download(self.document, view=bool(request.GET.get('view', False)))

    # Static so that it can be reused in DocumentDirectDownloadView below
    @staticmethod
    def do_download(document, view=False):
        return DocumentDownloadView.do_download_file(document.file, document.name, view)

    # Static so that it can be reused in DocumentPdfPreviewView below
    @staticmethod
    def do_download_file(f, document_name, view=False):
        if settings.USE_S3:
            content_type = mimetypes.guess_type(f.name)[0]
            filename = f.file.key.name.split('/')[-1]
            wrapper = FileWrapper(f.file)
            size = f.size
        else:
            content_type = mimetypes.guess_type(f.path)[0]
            filename = os.path.basename(f.name)
            wrapper = FileWrapper(open(f.path, 'rb'))
            size = os.path.getsize(f.path)

        # Create the HttpResponse object with the appropriate headers.
        response = HttpResponse(wrapper, content_type=content_type)
        response['Content-Length'] = size
        if not view:
            try:
                response['Content-Disposition'] = u'attachment; filename="{}"'.format(document_name or filename)
            except BadHeaderError:
                _, file_extension = os.path.splitext(document_name or filename)
                response['Content-Disposition'] = u'attachment; filename="{}"'.format("file" + file_extension)
                pass

        return response


class DocumentRevisionDownloadView(SelectBoardRequiredMixin, DocumentQuerysetMixin, PermissionMixin, View):
    permission = (Document, PERMISSIONS.view)

    def and_permission(self, account, membership):
        document = get_object_or_404(self.get_queryset(), id=self.kwargs['document_id'])
        return has_object_permission(membership, document, PERMISSIONS.view)

    def get(self, request, document_id, revision):
        audit = get_object_or_404(AuditTrail, latest_version=document_id, revision=revision)

        if settings.USE_S3:
            content_type = mimetypes.guess_type(audit.file.name)[0]
            filename = audit.file.file.key.name.split('/')[-1]
            wrapper = FileWrapper(audit.file.file)
            size = audit.file.size
        else:
            content_type = mimetypes.guess_type(audit.file.path)[0]
            filename = os.path.basename(audit.file.name)
            wrapper = FileWrapper(file(audit.file.path, 'rb'))
            size = os.path.getsize(audit.file.path)

        # Create the HttpResponse object with the appropriate headers.
        response = HttpResponse(wrapper, content_type=content_type)
        response['Content-Length'] = size
        response['Content-Disposition'] = u'attachment; filename="{}"'.format(audit.name or filename)
        return response


class DocumentSendView(AjaxableResponseMixin, SelectBoardRequiredMixin, MemberNotificationMixin,
                       DocumentQuerysetMixin, PermissionMixin, FormView):
    permission = (Document, PERMISSIONS.view)
    form_class = MessageForm
    template_name = 'documents/message.html'

    def and_permission(self, account, membership):
        document = get_object_or_404(self.get_queryset(), id=self.kwargs['document_id'])
        self.object = document
        return has_object_permission(membership, document, PERMISSIONS.view)

    def get(self, request, *args, **kwargs):
        super(DocumentSendView, self).get(request, *args, **kwargs)
        data = {
            'html': render_to_string(self.template_name,
                                     self.get_context_data(form=self.get_form(self.form_class), document_id=self.kwargs['document_id']),
                                     context_instance=RequestContext(self.request))
        }
        return self.render_to_json_response(data)

    def form_valid(self, form):
        ctx_dict = {
            'title': form.cleaned_data['subject'],
            'msg': form.cleaned_data['body'],
            'account': get_current_account(self.request)
        }
        self.send(ctx_dict, attachments=((self.object.name, self.object.file.read(), None),))
        return redirect(self.get_success_url())

    def get_success_message(self):
        messages.success(self.request, _('Documents were shared'))

    def get_success_url(self):
        account_url = get_current_account(self.request).url
        if self.object.folder is not None:
            self.object.folder.get_absolute_url()
        else:
            return reverse('folders:rootfolder_detail', kwargs={'url': account_url})


class DocumentMoveView(AjaxableResponseMixin, DocumentQuerysetMixin,
                       PermissionMixin, SelectBoardRequiredMixin, View):
    permission = (Document, PERMISSIONS.edit)

    def and_permission(self, account, membership):
        target = get_object_or_404(Folder, account=account, slug=self.request.POST.get('target_slug'))
        self.target = target
        return target.can_add_files and has_object_permission(membership, target, PERMISSIONS.add)

    def get_permission_object(self):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs['document_id'])

    def post(self, request, *args, **kwargs):
        document = self.get_permission_object()

        form = FolderMoveForm(request.POST)
        if form.is_valid():
            document.folder = self.target
            document.save()
            return self.render_to_json_response({'result': 'ok'})
        else:
            # QUESTION: Is there already converter ErrorDict -> Dict[String, String]?
            return self.render_to_json_response({'result': 'failed', 'errors': 'TODO'})


class DocumentPdfPreviewView(DocumentQuerysetMixin, PermissionMixin, SelectBoardRequiredMixin, View):
    permission = (Document, PERMISSIONS.view)

    def get(self, request, *args, **kwargs):
        document = get_object_or_404(self.get_queryset(), pk=kwargs['pk'])
        assert isinstance(document, Document)
        if not document.pdf_preview:
            temp_dir = tempfile.mkdtemp()
            try:
                temp_name = temp_dir + "/temp." + document.extension()
                with open(temp_name, "w+b") as temp, document.file as f:
                    # Simple copy because it can be S3
                    while True:
                        buf = f.read(1024 * 1024)
                        if not buf:
                            break
                        temp.write(buf)

                process_kwargs = {
                    'stdout': PIPE,
                    'stderr': PIPE,
                }
                # For windows development:
                if os.name != 'nt':
                    process_kwargs['close_fds'] = True

                process = subprocess.Popen([settings.LIBRE_OFFICE_BINARY, '--convert-to', 'pdf', '--outdir', temp_dir, temp_name, '--headless'],
                                           **process_kwargs)
                stdout, stderr = process.communicate()
                if process.returncode:
                    raise ValueError("Error while calling LibreOffice, code: %d, stdout: %s, stderr: %s" % (process.returncode, stdout, stderr))

                with open(temp_dir + '/temp.pdf', 'r') as temp:
                    name, ext = splitext(basename(document.file.path))
                    document.pdf_preview.save(name + '.pdf', File(temp))
            finally:
                shutil.rmtree(temp_dir)

        return DocumentDownloadView.do_download_file(document.pdf_preview, document.name + '.pdf')
