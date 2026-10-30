from django import forms, template
from django.contrib.humanize.templatetags.humanize import intcomma

register = template.Library()


@register.filter
def bs(field, extra=''):
    """Render a form field with the right Bootstrap class for its widget."""
    widget = field.field.widget
    if isinstance(widget, (forms.CheckboxInput,)):
        css = 'form-check-input'
    elif isinstance(widget, (forms.Select, forms.SelectMultiple)) and not isinstance(widget, forms.CheckboxSelectMultiple):
        css = 'form-select'
    elif isinstance(widget, (forms.RadioSelect, forms.CheckboxSelectMultiple)):
        css = ''
    else:
        css = 'form-control'
    if field.errors:
        css += ' is-invalid'
    attrs = {'class': f'{css} {extra}'.strip()}
    return field.as_widget(attrs=attrs)


@register.filter
def widget_kind(field):
    widget = field.field.widget
    if isinstance(widget, forms.CheckboxSelectMultiple):
        return 'multi'
    if isinstance(widget, forms.RadioSelect):
        return 'radio'
    if isinstance(widget, forms.CheckboxInput):
        return 'switch'
    return 'default'


@register.filter
def category_icon(category):
    from properties.models import CATEGORY_META
    return CATEGORY_META.get(category, ('bi-house',))[0]


@register.filter
def taka(value):
    """12000 -> ৳ 12,000"""
    if value in (None, ''):
        return '-'
    try:
        return f'৳ {intcomma(int(round(float(value))))}'
    except (TypeError, ValueError):
        return value


@register.filter
def stars(value):
    try:
        value = float(value or 0)
    except (TypeError, ValueError):
        value = 0
    full = int(round(value))
    return '★' * full + '☆' * (5 - full)


@register.filter
def is_bool(value):
    return isinstance(value, bool)


@register.filter
def reason_class(value):
    if value >= 1:
        return 'yes'
    return 'part' if value > 0 else 'no'


@register.filter
def match_color(percentage):
    if percentage >= 85:
        return '#16a34a'
    if percentage >= 65:
        return '#d97706'
    return '#64748b'


@register.simple_tag
def area_datalist():
    from django.utils.html import format_html, format_html_join

    from properties.models import POPULAR_AREAS
    options = format_html_join('', '<option value="{}">', ((a,) for a in POPULAR_AREAS))
    return format_html('<datalist id="area-list">{}</datalist>', options)


@register.simple_tag
def page_url(query_string, number):
    return f'?{query_string}&page={number}' if query_string else f'?page={number}'
