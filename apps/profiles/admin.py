# -*- coding: utf-8 -*-
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib import admin
from django.contrib.auth.models import Group
from django.utils.translation import ugettext as _

from .forms import UserChangeForm, UserCreationForm
from .models import User, Membership


class UserAdmin(BaseUserAdmin):
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {'fields': ()}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2')}
         ),
    )
    form = UserChangeForm
    add_form = UserCreationForm
    list_display = ('email', 'is_staff')
    list_filter = ('is_staff', 'is_superuser', 'is_active')
    search_fields = ('email',)
    ordering = ('email',)
    filter_horizontal = ()


class MembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_active', 'is_admin', 'role', 'account')

admin.site.register(User)
admin.site.register(Membership, MembershipAdmin)
admin.site.unregister(Group)
