from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext as _
from django.views.generic.base import View

from accounts.account_helper import get_current_account
from common.mixins import AjaxableResponseMixin, SelectBoardRequiredMixin
from documents.models import Folder, Document
from documents.views.folder import FolderQuerysetMixin, FolderContextMixin
from permissions import PERMISSIONS
from permissions.mixins import PermissionMixin
from permissions.shortcuts import has_object_permission


class FolderLookupView(AjaxableResponseMixin, FolderContextMixin, FolderQuerysetMixin,
                       PermissionMixin, SelectBoardRequiredMixin, View):
    permission = (Folder, PERMISSIONS.view)

    # noinspection PyUnusedLocal
    def get(self, request, *args, **kwargs):
        if 'init_for_document' in request.GET:
            document = get_object_or_404(Document.objects.filter(account=get_current_account(self.request)), pk=int(request.GET['init_for_document']))
            result, _ = self.get_init_for_document(document)
            return self.render_to_json_response(result)
        elif 'init_for_folder' in request.GET:
            folder = get_object_or_404(self.get_queryset(), slug=request.GET['init_for_folder'])
            result, _ = self.get_init_for_folder(folder, folder.slug)
            return self.render_to_json_response(result)
        elif 'document_slug' in request.GET:
            folder = get_object_or_404(self.get_queryset(), slug=request.GET['document_slug'])
            result = self.get_data_for_folder(folder)
            return self.render_to_json_response(result)
        else:
            return self.render_to_json_response({'error': 'Please specify either init_for_document= or init_for_folder or document_slug in GET'}, status=400)

    def get_data_for_folder(self, folder):
        return self.build_children(folder, activate_slug=None)

    # noinspection PyTypeChecker
    def get_init_for_folder(self, folder, activate_slug=None):
        nodes = list(folder.get_ancestors(include_self=True))
        in_committee = any((n.committee is not None for n in nodes))
        in_membership = any((n.membership is not None for n in nodes))
        if in_committee:
            # set root to committe folder
            root = nodes[2]
            root_text = unicode(root)
        elif in_membership:
            # set root to private folder
            root = nodes[2]
            root_text = _(u'My Documents')
        else:
            # set root to account root
            root = nodes[0]
            root_text = unicode(root) + ' (' + _('root') + ')'
        result = [{
            'id': root.slug,
            'text': root_text,
            'icon': 'fa fa-folder folder-icon',
            'state': {'opened': True},
        }]
        target = result[0]

        prev = result
        for node in nodes:
            children = self.build_children(node, activate_slug)
            try:
                target = next(child for child in prev if child['id'] == node.slug)
                target['state'] = {'opened': True}
                target['children'] = prev = children
            except StopIteration:
                pass

        target['children'] = False

        return result, target

    def get_init_for_document(self, document):
        result, target = self.get_init_for_folder(document.folder)
        target['children'] = self.build_children(document.folder, activate_slug=None) + [{
            'id': 'doc-' + str(document.id),
            'text': unicode(document.name) + ' ' + _('(current)'),
            'icon': 'fa fa-file-' + document.file_type() + '-o',
            'children': False,
        }]

        return result, target['children'][0]

    def build_children(self, node, activate_slug):
        children = node.children.filter(protected=False)
        membership = self.request.user.get_membership(get_current_account(self.request))
        # QUESTION: What is common import name for ugettext (__ here)? BTW, should I use u')' to keep it Unicode?
        result = []
        for child in children:
            is_requested_node = child.slug == activate_slug
            is_selectable = has_object_permission(membership, child, PERMISSIONS.add)
            if is_selectable:
                result.append({
                    'id': child.slug,
                    'text': unicode(child.name) + (' ' + _('(current)') if is_requested_node else ''),
                    'icon': 'fa fa-folder-o folder-icon' if is_requested_node else 'fa fa-folder folder-icon',
                    'children': not child.is_leaf_node(),
                })

        return result
