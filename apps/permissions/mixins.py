# -*- coding: utf-8 -*-
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.utils.decorators import method_decorator
from django.shortcuts import redirect

from accounts.account_helper import get_current_account
from permissions.shortcuts import has_role_permission, has_object_permission


class PermissionMixin(object):
    def and_permission(self, account, membership):
        return True

    def or_permission(self, account, membership):
        return False

    def get_permission_object(self):
        try:
            return self.get_object()
        except:
            return None

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        account = get_current_account(request)
        membership = request.user.get_membership(account)
        model, permission = self.permission
        obj = self.get_permission_object()
        if (self.and_permission(account, membership) and
            ((has_role_permission(membership, model, permission) or has_object_permission(membership, obj, permission)) or
             self.or_permission(account, membership))):
            return super(PermissionMixin, self).dispatch(request, *args, **kwargs)
        # Soft land folder urls to root folder instead of 403
        if 'folders/' in request.path:
            return redirect('folders:rootfolder_detail', url=account.url)
        raise PermissionDenied()
