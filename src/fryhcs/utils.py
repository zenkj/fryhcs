from pathlib import Path

from fryhcs.config import fryconfig
from fryhcs.css.generator import CSSGenerator
from fryhcs.js.generator import JSGenerator

import os
import inspect

if fryconfig.django_ok:
    from django.template.autoreload import get_template_directories as django_template_directories
    def jinja_template_directories():
        try:
            from django.template.backends.jinja2 import Jinja2
            from django.template import engines
        except ImportError:
            return set()
        cwd = Path.cwd()
        items = set()
        for backend in engines.all():
            if not isinstance(backend, Jinja2):
                continue

            loader = backend.env.loader  # type: ignore [attr-defined]
            if hasattr(loader, searchpath) and isinstance(loader.searchpath, (list, tuple)):
                items.update([cwd / Path(fspath) for fspath in loader.searchpath])
        return items

    def template_directories():
        dirs = django_template_directories()
        dirs.update(jinja_template_directories())
        return dirs

def pyx_files():
    input_files = []
    if fryconfig.django_ok:
        from django.apps import apps
        input_files = [(ac.path, '**/*.pyx') for ac in apps.get_app_configs()]
    elif fryconfig.flask_ok:
        from flask import current_app
        try:
            input_files = [(current_app.root_path, '**/*.pyx')]
        except RuntimeError:
            pass
    if not input_files:
        raise RuntimeError('django or flask is not configured')
    return input_files

def create_css_generator():
    # input_files = [(dir, '**/*.html') for dir in template_directories()]
    return CSSGenerator(pyx_files(), fryconfig.css_file)

def create_js_generator():
    return JSGenerator(pyx_files(), fryconfig.js_root)


def static_url(path):
    if fryconfig.django_ok:
        from django.contrib.staticfiles.storage import staticfiles_storage
        return staticfiles_storage.url(path)
    elif fryconfig.flask_ok:
        from flask import current_app
        try:
            return current_app.static_url_path.rstrip('/') + '/' + path.lstrip('/')
        except RuntimeError:
            pass
    return path

def component_name(fn):
    if inspect.isfunction(fn) or inspect.isclass(fn):
        if fryconfig.django_ok:
            from django.apps import apps
            ac = apps.get_containing_app_config(fn.__module__)
            if ac:
                return ac.label + ':' + fn.__name__
        elif fryconfig.flask_ok:
            from flask import current_app
            try:
                name = current_app.name
                if name:
                    return name + ':' + fn.__name__
            except RuntimeError:
                pass
        return fn.__name__
    return str(fn)
