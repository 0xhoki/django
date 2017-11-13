# -*- coding: utf-8 -*-
import re
from django import forms
from django.contrib.auth.forms import (ReadOnlyPasswordHashField,
                                       UserChangeForm as BaseUserChangeForm)
from django.utils import timezone
from django.utils.translation import ugettext as _

from committees.models import Committee
from common.shortcuts import reorder_form_fields
from .models import User, Membership


class UserChangeForm(BaseUserChangeForm):
    email = forms.EmailField(label=_('Email'), max_length=75)
    password = ReadOnlyPasswordHashField(label=_('Password'),
                                         help_text=_('Raw passwords are not stored, so there is no way to see '
                                                     "this user's password, but you can change the password "
                                                     'using <a href="password/">this form</a>.'))


class UserCreationForm(forms.ModelForm):
    email = forms.EmailField(label=_('Email'), max_length=75)
    password1 = forms.CharField(label=_('Password'),
                                widget=forms.PasswordInput)
    password2 = forms.CharField(label=_('Password confirmation'),
                                widget=forms.PasswordInput,
                                help_text=_('Enter the same password as above, for verification.'))

    class Meta:
        model = User
        fields = ('email',)

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError(_("The two password fields didn't match."))
        return password2

    def save(self, commit=True):
        user = super(UserCreationForm, self).save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class MembershipBaseForm(forms.ModelForm):
    x1 = forms.IntegerField(widget=forms.HiddenInput(), required=False)
    y1 = forms.IntegerField(widget=forms.HiddenInput(), required=False)
    x2 = forms.IntegerField(widget=forms.HiddenInput(), required=False)
    y2 = forms.IntegerField(widget=forms.HiddenInput(), required=False)
    first_name = forms.CharField(label=_('First Name'), max_length=30,
                                 widget=forms.TextInput(attrs={'class': 'txt'}), required=True)
    last_name = forms.CharField(label=_('Last Name'), max_length=30,
                                widget=forms.TextInput(attrs={'class': 'txt'}), required=True)
    email = forms.EmailField(label=_('Invitation Email'), max_length=75,
                             widget=forms.TextInput(attrs={'class': 'txt'}), required=True)
    phone_number = forms.CharField(label=_('Phone Number'), max_length=12,
                                   widget=forms.TextInput(attrs={'class': 'txt'}), required=False)
    employer = forms.CharField(label=_('Employer'), max_length=50,
                               widget=forms.TextInput(attrs={'class': 'txt'}), required=False)
    job_title = forms.CharField(label=_('Job Title'), max_length=50,
                                widget=forms.TextInput(attrs={'class': 'txt'}), required=False)
    work_email = forms.EmailField(label=_('Work Email'), max_length=75,
                                  widget=forms.TextInput(attrs={'class': 'txt'}), required=False)
    work_number = forms.CharField(label=_('Work Number'), max_length=12,
                                  widget=forms.TextInput(attrs={'class': 'txt'}), required=False)
    intro = forms.CharField(label=_('Intro'), max_length=100,
                            widget=forms.TextInput(attrs={'class': 'txt'}), required=False)
    bio = forms.CharField(label=_('Short Bio'), widget=forms.Textarea(attrs={'class': 'txt'}), required=False)
    address = forms.CharField(label=_('Address'), max_length=150,
                              widget=forms.TextInput(attrs={'class': 'txt'}), required=False)
    secondary_address = forms.CharField(label=_('Address(opt)'), max_length=150,
                                        widget=forms.TextInput(attrs={'class': 'txt'}), required=False)
    city = forms.CharField(label=_('City'), max_length=100,
                           widget=forms.TextInput(attrs={'class': 'txt'}), required=False)
    state = forms.CharField(label=_('State'), max_length=100,
                            widget=forms.TextInput(attrs={'class': 'txt'}), required=False)
    zip = forms.CharField(label=_('Zip'), max_length=50,
                          widget=forms.TextInput(attrs={'class': 'txt'}), required=False)
    country = forms.CharField(label=_('Country'), max_length=100,
                              widget=forms.TextInput(attrs={'class': 'txt'}), required=False)
    birth_date = forms.CharField(label=_('Date of Birth'), max_length=100,
                                 widget=forms.TextInput(attrs={'class': 'txt'}), required=False)
    secondary_phone = forms.CharField(label=_('Secondary Phone'), max_length=12,
                                      widget=forms.TextInput(attrs={'class': 'txt'}), required=False)
    affiliation = forms.CharField(label=_('Affiliations'), max_length=150,
                                  widget=forms.TextInput(attrs={'class': 'txt'}), required=False)
    social_media_link = forms.CharField(label=_('Social Media Links'), max_length=150,
                                        widget=forms.TextInput(attrs={'class': 'txt'}), required=False)

    def __init__(self, *args, **kwargs):
        super(MembershipBaseForm, self).__init__(*args, **kwargs)
        self.fields['timezone'].label = _('Time Zone')

    class Meta:
        model = Membership
        exclude = []

    def clean_email(self):
        email = self.cleaned_data['email']
        qs = User.objects.filter(email__iexact=email)
        if qs.count() > 0:
            raise forms.ValidationError(_('This email is already in use.'))
        return email

    def clean_phone_number(self):
        phones = self.cleaned_data['phone_number']
        pattern = r'^\d{3}-\d{3}-\d{4}$'
        for phone in phones.split(','):
            if phone and (not re.match(pattern, phone) or len(phone) != 12):
                raise forms.ValidationError(_('Phone number is invalid..'))
        return phones


class MembershipEditForm(MembershipBaseForm):
    def __init__(self, *args, **kwargs):
        super(MembershipEditForm, self).__init__(*args, **kwargs)
        if self.instance.is_guest:
            self.fields['employer'].required = False
            self.fields['job_title'].required = False
            self.fields['work_email'].required = False
            self.fields['work_number'].required = False
            self.fields['intro'].required = False
            self.fields['bio'].required = False

        if not self.initial['timezone']:
            self.initial['timezone'] = timezone.get_current_timezone()

    def clean_email(self):
        email = self.cleaned_data['email']
        if email != self.initial['email']:
            qs = User.objects.filter(email__iexact=email)
            if qs.count() > 0:
                raise forms.ValidationError(_('This email is already in use.'))
        return email

    class Meta(MembershipBaseForm.Meta):
        fields = ('first_name', 'last_name', 'email', 'phone_number', 'timezone', 'employer', 'job_title', 'work_email',
                  'work_number', 'intro', 'bio', 'address', 'secondary_address', 'city', 'state', 'zip', 'country',
                  'birth_date', 'secondary_phone', 'affiliation', 'social_media_link', 'avatar')


class MembershipAdminEditForm(MembershipEditForm):
    def __init__(self, *args, **kwargs):
        super(MembershipAdminEditForm, self).__init__(*args, **kwargs)
        roles = self.get_roles()
        status = [s for s in Membership.STATUS if s[0] in (Membership.STATUS.active, Membership.STATUS.inactive)]
        self.fields['role'] = forms.ChoiceField(label=_('Role in Organization'), choices=roles)
        self.fields['is_active'] = forms.ChoiceField(label=_('Status in Organization'), choices=status)
        self.fields['committees'].queryset = Committee.objects.filter(account=self.initial['account'])
        self.fields['term_start'] = forms.DateField(label=_('Start Date of Board Term'), input_formats=['%b. %d, %Y'],
                                                    widget=forms.DateInput(format='%b. %d, %Y', attrs={
                                                        'placeholder': '{:%b. %d, %Y}'.format(timezone.now())}
                                                                           ), required=False)
        self.fields['term_expires'] = forms.DateField(label=_('End Date of Board Term'), input_formats=['%b. %d, %Y'],
                                                      widget=forms.DateInput(format='%b. %d, %Y', attrs={
                                                          'placeholder': '{:%b. %d, %Y}'.format(timezone.now())}
                                                                             ), required=False)
        self.fields['is_admin'] = forms.BooleanField(widget=forms.CheckboxInput,
                                                    label=_('Is an Administrator?'), required=False)
        self.is_guest()

    def get_roles(self):
        role_groups = (
            (Membership.ROLES.chair, Membership.ROLES.ceo, Membership.ROLES.director, Membership.ROLES.member),
            (Membership.ROLES.assistant,),
            (Membership.ROLES.guest, Membership.ROLES.vendor, Membership.ROLES.staff, Membership.ROLES.consultant),
        )
        for group in role_groups:
            if self.instance.role in group:
                return [r for r in Membership.ROLES if r[0] in group]

    def is_guest(self):
        if self.instance.is_guest:
            self.fields['employer'].required = False
            self.fields['job_title'].required = False
            self.fields['work_email'].required = False
            self.fields['work_number'].required = False
            self.fields['intro'].required = False
            self.fields['bio'].required = False
            key_order = ['first_name', 'last_name', 'email', 'phone_number', 'role', 'is_active',
                         'timezone', 'committees', 'is_admin', 'employer', 'job_title', 'work_email', 'work_number', 'intro', 'bio',
                         'address', 'secondary_address', 'city', 'state', 'zip', 'country', 'birth_date', 'secondary_phone',
                         'affiliation', 'social_media_link', 'avatar', 'x1', 'x2', 'y1', 'y2']
            self.fields = reorder_form_fields(self.fields, key_order)

    class Meta(MembershipBaseForm.Meta):
        fields = ('first_name', 'last_name', 'email', 'phone_number', 'role', 'is_active', 'term_start', 'term_expires',
                  'timezone', 'committees', 'is_admin', 'employer', 'job_title', 'work_email', 'work_number', 'intro', 'bio',
                  'address', 'secondary_address', 'city', 'state', 'zip', 'country', 'birth_date', 'secondary_phone',
                  'affiliation', 'social_media_link', 'avatar')


class MemberAddForm(MembershipBaseForm):
    def __init__(self, *args, **kwargs):
        super(MemberAddForm, self).__init__(*args, **kwargs)
        roles = self.get_roles()
        status = [s for s in Membership.STATUS if s[0] in (Membership.STATUS.active, Membership.STATUS.inactive)]
        self.fields['add_another'] = forms.BooleanField(widget=forms.HiddenInput(), required=False, initial=False)
        self.fields['role'] = forms.ChoiceField(label=_('Role in Organization'), choices=roles)
        self.fields['is_active'] = forms.ChoiceField(label=_('Status in Organization'), choices=status)
        self.fields['committees'].queryset = Committee.objects.filter(account=self.initial['account'])
        self.fields['term_start'] = forms.DateField(label=_('Start Date of Board Term'), input_formats=['%b. %d, %Y'],
                                                    widget=forms.DateInput(format='%b. %d, %Y', attrs={
                                                        'placeholder': '{:%b. %d, %Y}'.format(timezone.now())}
                                                                           ), required=False)
        self.fields['term_expires'] = forms.DateField(label=_('End Date of Board Term'), input_formats=['%b. %d, %Y'],
                                                      widget=forms.DateInput(format='%b. %d, %Y', attrs={
                                                          'placeholder': '{:%b. %d, %Y}'.format(timezone.now())}
                                                                             ), required=False)
        self.initial['timezone'] = timezone.get_current_timezone()
        self.fields['is_admin'] = forms.BooleanField(widget=forms.CheckboxInput,
                                                     label=_('Is an Administrator?'), required=False)

        key_order = ['add_another', 'avatar', 'x1', 'x2', 'y1', 'y2', 'first_name', 'last_name', 'email',
                     'phone_number', 'role', 'is_active', 'term_start', 'term_expires', 'timezone',
                     'committees', 'is_admin', 'employer', 'job_title', 'work_email', 'work_number', 'intro',
                     'bio', 'address', 'secondary_address', 'city', 'state', 'zip', 'country',
                     'birth_date', 'secondary_phone', 'affiliation', 'social_media_link']
        self.fields = reorder_form_fields(self.fields, key_order)

    def get_roles(self):
        roles = (Membership.ROLES.chair, Membership.ROLES.ceo, Membership.ROLES.director, Membership.ROLES.member)
        return [r for r in Membership.ROLES if r[0] in roles]

    class Meta:
        model = Membership
        exclude = ('account', 'user', 'date_joined_board', 'assistant')


class GuestAddForm(MembershipBaseForm):
    def __init__(self, *args, **kwargs):
        super(GuestAddForm, self).__init__(*args, **kwargs)
        roles = self.get_roles()
        status = [s for s in Membership.STATUS if s[0] in (Membership.STATUS.active, Membership.STATUS.inactive)]
        self.fields['add_another'] = forms.BooleanField(widget=forms.HiddenInput(), required=False, initial=False)
        self.fields['role'] = forms.ChoiceField(label=_('Role in Organization'), choices=roles)
        self.fields['is_active'] = forms.ChoiceField(label=_('Status in Organization'), choices=status)
        self.fields['committees'].queryset = Committee.objects.filter(account=self.initial['account'])
        self.fields['employer'].required = False
        self.fields['job_title'].required = False
        self.fields['work_email'].required = False
        self.fields['work_number'].required = False
        self.fields['intro'].required = False
        self.fields['bio'].required = False
        self.initial['timezone'] = timezone.get_current_timezone()
        self.fields['is_admin'] = forms.BooleanField(widget=forms.CheckboxInput,
                                                     label=_('Is an Administrator?'), required=False)

    def get_roles(self):
        roles = (Membership.ROLES.guest, Membership.ROLES.vendor, Membership.ROLES.staff, Membership.ROLES.consultant)
        return [r for r in Membership.ROLES if r[0] in roles]

    class Meta(MembershipBaseForm.Meta):
        fields = ('first_name', 'last_name', 'email', 'phone_number', 'role', 'is_active',
                  'timezone', 'committees', 'is_admin', 'employer', 'job_title', 'work_email', 'work_number', 'intro',
                  'bio', 'address', 'secondary_address', 'city', 'state', 'zip', 'country', 'birth_date', 'secondary_phone',
                  'affiliation', 'social_media_link', 'avatar')


class AssistantAddForm(MembershipBaseForm):
    def __init__(self, *args, **kwargs):
        super(forms.ModelForm, self).__init__(*args, **kwargs)
        self.initial['timezone'] = timezone.get_current_timezone()

    class Meta(MembershipBaseForm.Meta):
        fields = ('first_name', 'last_name', 'email', 'timezone', 'avatar', 'phone_number')


class AssistantEditForm(MembershipEditForm):
    def __init__(self, *args, **kwargs):
        super(forms.ModelForm, self).__init__(*args, **kwargs)
        self.initial['timezone'] = timezone.get_current_timezone()

    class Meta(MembershipEditForm.Meta):
        fields = ('first_name', 'last_name', 'email', 'timezone', 'avatar', 'phone_number')
