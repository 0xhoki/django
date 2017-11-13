# -*- coding: utf-8 -*-
from django import forms
from django.db.models import Q
from django.utils.translation import ugettext_lazy as _
from django.utils import timezone

from common.shortcuts import reorder_form_fields
from profiles.models import Membership
from .models import Meeting
from committees.models import Committee
from permissions import PERMISSIONS
from permissions.shortcuts import has_role_permission


class MeetingFilter(forms.Form):
    order_by = forms.ChoiceField([('asc', _('Nearest first')), ('desc', _('Latest first'))],
                                 required=False, widget=forms.Select(attrs={'class': 'submit-form default selectize-it'}))

    def __init__(self, membership, *args, **kwargs):
        super(MeetingFilter, self).__init__(*args, **kwargs)
        committee_options = ([('', _('Any committee')),
                              ('__full__', _('All Board Members'))]
                             + [(c.id, c.name) for c in Committee.objects.for_membership(membership)])
        self.fields['committee'] = forms.ChoiceField(committee_options, required=False,
                                                     widget=forms.Select(attrs={'class': 'submit-form default selectize-it committee-select'}))


def meeting_action_choices(meeting, membership, allow_update=True):
    """
    That's kind of magic selection in which situation what is possible. At first it was just select all the times.
    Then it was replaced with hidden field (for Publish button) and dynamic hidden in update.
    """
    if meeting.pk:
        if not meeting.is_published:
            actions = []
            if allow_update:
                actions.append(('update', _('Update')))  # Note: this is correct, update at this stage is without emails sending
                actions.append(('update-no-email', _('Update without email')))  # Note: this is correct, update at this stage is without emails sending
            else:
                actions.append(('publish', _('Publish')))
        else:
            actions = []
            if allow_update:
                actions.append(('update', _('Update')))
                if membership.is_admin or membership.id == meeting.creator.id:
                    actions.append(('update-no-email', _('Update without notification')))

        return actions
    else:
        return [
            ('update-no-email', _('Save as draft')),  # Note: this is correct, update is essentially don't change anything
            ('publish', _('Publish'))]


class MeetingPublishForm(forms.Form):
    def __init__(self, meeting, membership, *args, **kwargs):
        super(MeetingPublishForm, self).__init__(*args, **kwargs)
        self.fields['action'] = forms.ChoiceField(meeting_action_choices(meeting, membership, allow_update=False))


class MeetingAddForm(forms.ModelForm):
    action = forms.ChoiceField()
    repeat_end_type = forms.CharField(widget=forms.RadioSelect(choices=Meeting.REPEAT_END_TYPES))

    def __init__(self, *args, **kwargs):
        is_event = kwargs.pop('is_event')

        super(MeetingAddForm, self).__init__(*args, **kwargs)
        self.fields['committee'].label = _('Attendees')
        self.fields['committee'].empty_label = _('All Board Members')
        self.fields['name'].widget.attrs['placeholder'] = _('Untitled Event') if is_event else _('Untitled Meeting')
        self.fields['description'].widget.attrs['placeholder'] = _('Event Description') if is_event else _('Meeting Description')

        membership = self.initial.pop('membership')
        account = self.initial.pop('account')
        meeting = self.instance
        assert isinstance(meeting, Meeting)

        queryset = Committee.objects.filter(account=account)
        if has_role_permission(membership, Committee, PERMISSIONS.add):
            # can add meeting for any committee
            self.fields['committee'].queryset = queryset
        else:
            # can add meeting only if chairman
            self.fields['committee'].queryset = queryset.filter(Q(chairman=membership) | Q(chairman__in=membership.get_bosses()))

        self.fields['repeat_end_date'] = forms.DateField(label=_('Repeat end date'), input_formats=['%b. %d, %Y'],
                                              widget=forms.DateInput(
                                                  attrs={'placeholder': '{:%b. %d, %Y}'.format(timezone.now())}
                                              ), required=False)
        self.fields['date'] = forms.DateField(label=_('Date'), input_formats=['%b. %d, %Y'],
                                              widget=forms.DateInput(
                                                  attrs={'placeholder': '{:%b. %d, %Y}'.format(timezone.now())}
                                              ), required=True)
        self.fields['time_start'] = forms.TimeField(label=_('From'), input_formats=['%I:%M %p'],
                                                    widget=forms.TimeInput(attrs={'class': 'from'}), required=True)
        self.fields['time_end'] = forms.TimeField(label=_('To'), input_formats=['%I:%M %p'],
                                                  widget=forms.TimeInput(attrs={'class': 'to'}), required=True)
        self.fields['action'] = forms.ChoiceField(meeting_action_choices(meeting, membership))

        members = Membership.objects.filter(account=account, user__is_active=True, is_active=True).select_related('user')
        self.fields['extra_members'] = forms.ModelMultipleChoiceField(members, label=_('Additional Attendees'), required=False,
                                                                      widget=forms.SelectMultiple(attrs={'class': 'default'}))

        key_order = ['name', 'description', 'committee', 'extra_members', 'date', 'time_start', 'time_end', 'location', 'action',
                                'repeat_type', 'repeat_interval', 'repeat_max_count', 'repeat_end_date', 'repeat_week_days', 'repeat_end_type']
        self.fields = reorder_form_fields(self.fields, key_order)

        if not is_event:
            self.fields['board_book'] = forms.FileField(label=_('Add Board Book'), required=False)
            self.fields['agenda'] = forms.FileField(label=_('Add Agenda'), required=False)
            self.fields['minutes'] = forms.FileField(label=_('Add Minutes'), required=False)

        self.fields['other'] = forms.FileField(label=_('Add Other Documents'), required=False)
        self.fields['uploaded'] = forms.CharField(widget=forms.HiddenInput(), required=False)
        self.fields['repeat_end_type'].initial = meeting.repeat_end_type

        if meeting.pk:
            start = timezone.localtime(meeting.start)
            end = timezone.localtime(meeting.end)
            self.fields['date'].initial = start.strftime("%b. %d, %Y")
            self.initial['repeat_end_date'] = meeting.repeat_end_date.strftime("%b. %d, %Y") if meeting.repeat_end_date else None
            self.fields['time_start'].initial = start.strftime("%I:%M %p")
            self.fields['time_end'].initial = end.strftime("%I:%M %p")

    def clean(self):
        cleaned_data = super(MeetingAddForm, self).clean()
        repeat_end_type = cleaned_data['repeat_end_type']

        if repeat_end_type == Meeting.REPEAT_END_TYPES.max_count:
            cleaned_data['repeat_end_date'] = None
        elif repeat_end_type == Meeting.REPEAT_END_TYPES.end_date:
            cleaned_data['repeat_max_count'] = None
        else:
            cleaned_data['repeat_max_count'] = None
            cleaned_data['repeat_end_date'] = None

        return cleaned_data

    class Meta:
        model = Meeting
        exclude = ['account', 'start', 'end', 'status']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'txt title', 'placeholder': _('Untitled Meeting')}),
            'description': forms.Textarea(attrs={'class': 'txt textarea', 'placeholder': _('Untitled Meeting'), 'rows': 3}),
            'location': forms.TextInput(attrs={'class': 'txt location', 'placeholder': _('Add location details')}),
        }
