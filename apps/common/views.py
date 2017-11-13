# -*- coding: utf-8 -*-
from django.http import HttpResponse, Http404, JsonResponse
from django.views.generic import TemplateView, CreateView, View
from django.core.urlresolvers import reverse_lazy, reverse
from django.shortcuts import redirect
from django.views.generic.base import RedirectView

from common.mixins import LoginRequiredMixin
from .forms import ContactForm
from .models import Feedback
from billing.models import Plan

from .authhelper import get_google_signin_url, get_office_signin_url, \
    get_google_token_from_code, get_office_token_from_code, \
    get_google_me, get_office_me, \
    get_google_calendars, get_office_calendars, \
    create_office_event, create_google_event, \
    get_google_events, get_office_events

from accounts.account_helper import get_current_account
from meetings.models import CalendarConnection, Meeting

from django.utils import timezone
import time


class MainView(TemplateView):
    template_name = 'index.html'


main = MainView.as_view()


class ContactView(CreateView):
    model = Feedback
    template_name = 'contactus.html'
    form_class = ContactForm
    success_url = reverse_lazy('thankyou')

    def form_valid(self, form):
        form.save()
        return redirect(self.success_url)


class PricingView(TemplateView):
    template_name = 'pricing.html'

    def get_context_data(self, **kwargs):
        ctx = super(PricingView, self).get_context_data(**kwargs)
        ctx['plans'] = Plan.list_available_plans()
        ctx['show_trial_button'] = True
        return ctx


class DomainView(View):
    def get(self, request, *args, **kwargs):
        return HttpResponse('mEOu0wA')


def get_office_token(request):
    try:
        auth_code = request.GET['code']
        user = get_current_account(request)
        redirect_uri = request.build_absolute_uri(reverse('office_token'))

        token = get_office_token_from_code(auth_code, redirect_uri)

        try:
            raise Http404("Cannot get Token from Office: %s" % token['error'])
        except KeyError:
            pass

        access_token = token['access_token']
        office_user = get_office_me(access_token)
        refresh_token = token['refresh_token']
        expires_in = token['expires_in']

        # expires_in is in seconds
        # Get current timestamp (seconds since Unix Epoch) and
        # add expires_in to get expiration time
        # Subtract 5 minutes to allow for clock differences
        expiration = int(time.time()) + expires_in - 300

        try:
            # if exists, update
            cal_conn = CalendarConnection.objects.get(account=user, provider='office')
            cal_conn.email = office_user['EmailAddress']
            cal_conn.access_token = access_token
            cal_conn.refresh_token = refresh_token
            cal_conn.expires_in = expiration
            cal_conn.save()

        except CalendarConnection.DoesNotExist:
            # if nonexist, create
            CalendarConnection.objects.create(
                account=user,
                provider='office',
                email=office_user['EmailAddress'],
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=expiration
            )

    except KeyError as e:
        raise Http404("Cannot get Token from Office %s" % e)
    except Exception as e:
        raise Http404(e)

    return redirect(reverse('calendar-setting', kwargs={'connect_type': 'office'}))


def get_google_token(request):
    try:
        auth_code = request.GET['code']
        user = get_current_account(request)
        redirect_uri = request.build_absolute_uri(reverse('google_token'))

        token = get_google_token_from_code(auth_code, redirect_uri)

        try:
            raise Http404("Cannot get Token from Google: %s" % token['error'])
        except KeyError:
            pass

        access_token = token['access_token']
        google_user = get_google_me(access_token)
        refresh_token = token['refresh_token']
        expires_in = token['expires_in']

        # expires_in is in seconds
        # Get current timestamp (seconds since Unix Epoch) and
        # add expires_in to get expiration time
        # Subtract 5 minutes to allow for clock differences
        expiration = int(time.time()) + expires_in - 300

        try:
            # if exists, update
            cal_conn = CalendarConnection.objects.get(account=user, provider='google')
            cal_conn.email = google_user['email']
            cal_conn.access_token = access_token
            cal_conn.refresh_token = refresh_token
            cal_conn.expires_in = expiration
            cal_conn.save()

        except CalendarConnection.DoesNotExist:
            # if nonexist, create
            CalendarConnection.objects.create(
                account=user,
                provider='google',
                email=google_user['email'],
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=expiration
            )

    except KeyError as e:
        raise Http404("Cannot get Token from Google %s" % e)
    except Exception as e:
        raise Http404(e)

    return redirect(reverse('calendar-setting', kwargs={'connect_type': 'google'}))


class CalendarConnectionView(TemplateView):
    template_name = 'calendar_connection.html'

    def get_context_data(self, **kwargs):
        context = super(CalendarConnectionView, self).get_context_data(**kwargs)

        cur_account = get_current_account(self.request)

        redirect_google_uri = self.request.build_absolute_uri(reverse('google_token'))
        redirect_office_uri = self.request.build_absolute_uri(reverse('office_token'))

        context['google_url'] = get_google_signin_url(redirect_google_uri)
        context['office_url'] = get_office_signin_url(redirect_office_uri)
        context['ical_url'] = '#'

        context['is_google_connected'] = False
        context['is_office_connected'] = False
        context['is_ical_connected'] = False

        cal_connections = CalendarConnection.objects.filter(account=cur_account)
        for conn in cal_connections:
            if conn.provider == 'google':
                context['is_google_connected'] = True

            if conn.provider == 'office':
                context['is_office_connected'] = True

            if conn.provider == 'ical':
                context['is_ical_connected'] = True

        return context


class CalendarDisconnectView(View):
    def get(self, request, *args, **kwargs):
        cur_account = get_current_account(request)
        connect_type = self.kwargs['connect_type']

        try:
            cal_conn = CalendarConnection.objects.get(account=cur_account, provider=connect_type)
            cal_conn.delete()
        except CalendarConnection.DoesNotExist:
            pass

        return redirect(reverse('calendar-connection'))


class CalendarSettingView(TemplateView):
    template_name = 'calendar_setting.html'

    def get_context_data(self, **kwargs):
        context = super(CalendarSettingView, self).get_context_data(**kwargs)
        cur_account = get_current_account(self.request)

        connect_type = self.kwargs['connect_type']

        # get calendarconnection object
        cal_conn = CalendarConnection.objects.get(account=cur_account, provider=connect_type)

        # google
        if connect_type == 'google':
            # get access_token
            redirect_uri = self.request.build_absolute_uri(reverse('google_token'))
            access_token = cal_conn.get_access_token(redirect_uri)

            # get calendars from google
            google_calendars = get_google_calendars(access_token)
            calendars = google_calendars['items']

        # office
        if connect_type == 'office':
            # get access_token
            redirect_uri = self.request.build_absolute_uri(reverse('office_token'))
            access_token = cal_conn.get_access_token(redirect_uri)

            # get calendars from office
            office_calendars = get_office_calendars(access_token, cal_conn.email)
            calendars = office_calendars['value']

        context['cal_conn'] = cal_conn
        context['calendars'] = calendars
        context['checked_cal_list'] = cal_conn.calendar_check_list.split('/') if cal_conn.calendar_check_list else []

        return context

    def post(self, request, *args, **kwargs):
        cur_account = get_current_account(request)

        connect_type = request.POST['connect_type']
        checked_add = request.POST.get('checked_add', None)
        checked_conflict = request.POST.get('checked_conflict', None)
        cal_list = request.POST.getlist('calendar_list', None)

        try:
            cal_conn = CalendarConnection.objects.get(account=cur_account, provider=connect_type)
            cal_conn.checked_add = True if checked_add else False
            cal_conn.checked_conflict = True if checked_conflict else False
            cal_conn.calendar_id = request.POST['calendar_id']
            cal_conn.calendar_check_list = '/'.join(cal_list) if cal_list else None
            cal_conn.save()
        except CalendarConnection.DoesNotExist:
            return JsonResponse({'result': 'fail'})

        return JsonResponse({'result': 'success'})


def add_event_to_calendar(request):
    connect_type = request.POST['connect_type']
    meeting_id = request.POST['meeting_id']

    try:
        cur_account = get_current_account(request)
        meeting = Meeting.objects.get(pk=meeting_id)
        cal_conn = CalendarConnection.objects.get(account=cur_account, provider=connect_type)

        calendar_id = cal_conn.calendar_id
        if calendar_id is None:
            return JsonResponse({'result': 'fail', 'msg': 'Please set calendar name in setting page.'})

        start_time = meeting.start.isoformat()
        end_time = meeting.end.isoformat()
        my_timezone = timezone.get_current_timezone().zone
        extra_members = meeting.extra_members.all()

        result = None

        ''' 
            Create event to GOOGLE
        '''

        if connect_type == 'google':
            # get access_token
            redirect_uri = request.build_absolute_uri(reverse('google_token'))
            access_token = cal_conn.get_access_token(redirect_uri)

            # check conflict
            if cal_conn.checked_conflict and cal_conn.calendar_check_list:
                parameters = {
                    'timeMin': start_time,
                    'timeMax': end_time,
                    'timeZone': my_timezone
                }

                cal_ids = cal_conn.calendar_check_list.split('/')
                for cal_id in cal_ids:
                    existing_events = get_google_events(access_token, cal_id, parameters)
                    try:
                        if len(existing_events['items']):
                            return JsonResponse({
                                'result': 'fail',
                                'msg': 'Foundout conflict in your google calendar. Event name: %s' % existing_events['items'][0]['summary']
                            })
                    except KeyError:
                        pass

            # create event
            attendees = []
            if extra_members.count() > 0:
                for v in extra_members:
                    attendees.append({"email": v.user.email})
            event_object = {
                "summary": meeting.name,
                "location": meeting.location,
                "description": meeting.description,
                "start": {
                    "dateTime": start_time,
                    "timeZone": my_timezone
                },
                "end": {
                    "dateTime": end_time,
                    "timeZone": my_timezone
                },
                "attendees": attendees,
            }

            result = create_google_event(access_token, calendar_id, event_object)
        ''' 
            Create event to OFFICE 365
        '''
        if connect_type == 'office':
            # get access_token
            redirect_uri = request.build_absolute_uri(reverse('office_token'))
            user_email = cal_conn.email
            access_token = cal_conn.get_access_token(redirect_uri)

            # check conflict
            if cal_conn.checked_conflict and cal_conn.calendar_check_list:
                parameters = {
                    'startDateTime': start_time,
                    'endDateTime': end_time
                }
                cal_ids = cal_conn.calendar_check_list.split('/')
                for cal_id in cal_ids:
                    existing_events = get_office_events(access_token, user_email, cal_id, parameters)
                    try:
                        if len(existing_events['value']):
                            return JsonResponse({
                                'result': 'fail',
                                'msg': 'Foundout conflict in your Office calendar. Event name: %s' % existing_events['value'][0]['Subject']
                            })
                    except KeyError:
                        pass

            # create event
            attendees = []
            if extra_members.count() > 0:
                for v in extra_members:
                    attendees.append({
                        "EmailAddress": {
                            "Address": v.user.email,
                            "Name": v.get_full_name()
                        },
                        "Type": "Required"
                    })
            event_object = {
                "Subject": meeting.name,
                "Body": {
                    "ContentType": "HTML",
                    "Content": meeting.description
                },
                "Start": {
                    "DateTime": start_time,
                    "TimeZone": my_timezone
                },
                "End": {
                    "DateTime": end_time,
                    "TimeZone": my_timezone
                },
                "Location": {
                    "DisplayName": meeting.location
                },
                "Attendees": attendees
            }

            result = create_office_event(access_token, user_email, calendar_id, event_object)

    except Exception as e:
        return JsonResponse({'result': 'fail', 'msg': e})

    try:
        result_msg = "Failed add to {0} calendar: {1}!".format(connect_type, result['error'])
        return JsonResponse({'result': 'fail', 'msg': result_msg})
    except KeyError:
        result_msg = "This meeting has been added successfully to {0} calendar !".format(connect_type)
        return JsonResponse({'result': 'success', 'msg': result_msg})


class MarkUpdateNotificationsAsRead(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        user = request.user
        user.date_notifications_read = timezone.now()
        user.save()

        return redirect(request.GET['back'])
