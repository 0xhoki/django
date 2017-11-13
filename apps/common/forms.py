# -*- coding: utf-8 -*-
from django import forms
from django.utils.safestring import mark_safe
from .models import Feedback, TemplateModel


class ContactForm(forms.ModelForm):
    class Meta:
        model = Feedback
        exclude = []


class RichTextWidget(forms.Textarea):
    class Media:
        css = {
            'all': ('css/kendo.common.min.css', 'css/kendo.default.min.css')
        }
        js = ('js/jquery-1.8.3.min.js', 'js/kendo.web.min.js', 'js/preview.js')

    def render(self, name, value, attrs=None, renderer=None):
        return mark_safe(super(RichTextWidget, self).render(name, value, attrs, renderer))


class TemplateForm(forms.ModelForm):
    class Meta:
        model = TemplateModel
        exclude = []
        widgets = {
            'html': RichTextWidget(attrs={'class': 'kendo_editor', 'style': 'height: 500px;'})
        }
