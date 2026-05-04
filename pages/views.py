from django.shortcuts import render, get_object_or_404
from .models import Page


def _nav_pages():
    return Page.objects.all().order_by('order')


def home(request):
    page = get_object_or_404(Page, slug='index')
    pages = _nav_pages()
    next_page = pages.filter(order__gt=page.order).first()
    return render(request, 'pages/page.html', {
        'page': page,
        'pages': pages,
        'current_slug': 'index',
        'prev_page': None,
        'next_page': next_page,
    })


def page_detail(request, slug):
    page = get_object_or_404(Page, slug=slug)
    pages = _nav_pages()
    prev_page = pages.filter(order__lt=page.order).last()
    next_page = pages.filter(order__gt=page.order).first()
    return render(request, 'pages/page.html', {
        'page': page,
        'pages': pages,
        'current_slug': slug,
        'prev_page': prev_page,
        'next_page': next_page,
    })
