from pathlib import Path

try:
    from django.conf import settings as django_settings
except ImportError:
    django_settings = False

try:
    from flask import current_app as flask_app
except ImportError:
    flask_app = False

class FryConfig():
    @property
    def django_ok(self):
        try:
            return django_settings and django_settings.configured
        except:
            pass
        return False

    @property
    def flask_ok(self):
        if flask_app:
            try:
                _current_obj = flask_app._get_current_object()
                return True
            except RuntimeError:
                pass
        return False

    def item(self, django_name, flask_name, default):
        if self.django_ok:
            return getattr(django_settings, django_name, default)
        if self.flask_ok:
            return flask_app.config.get(flask_name, default)
        return default

    @property
    def js_url(self):
        return self.item('FRYHCS_JS_URL', 'FRYHCS_JS_URL', 'js/components/')

    @property
    def css_url(self):
        return self.item('FRYHCS_CSS_URL', 'FRYHCS_CSS_URL', 'css/styles.css')

    @property
    def check_reload_url(self):
        if not self.debug:
            return ''
        if self.django_ok:
            from django.urls import reverse
            return reverse('fryhcs:hotreload')
        if self.flask_ok:
            return flask_app.url_for('fryhcs_hotreload')
        return ''

    @property
    def debug(self):
        return self.item('DEBUG', 'DEBUG', True)

    @property
    def static_root(self):
        if self.django_ok:
            root_dir = getattr(django_settings, 'FRYHCS_STATIC_ROOT', '')
            if not root_dir:
                staticfiles_dirs = getattr(django_settings, 'STATICFILES_DIRS', [])
                if len(staticfiles_dirs) == 0:
                    raise Exception("'FRYHCS_STATIC_ROOT' is not specified, 'STATICFILES_DIRS' should have at least one item.")
                root_dir = staticfiles_dirs[0]
            return Path(root_dir)
        if self.flask_ok:
            return Path(flask_app.static_folder)
        return Path('.')

    @property
    def static_url(self, default='/static'):
        if self.django_ok:
            return getattr(django_settings, 'STATIC_URL', default)
        if self.flask_ok:
            return flask_app.static_url_path
        return default

    @property
    def js_root(self):
        return self.static_root / self.js_url

    @property
    def css_file(self):
        return self.static_root / self.css_url

fryconfig = FryConfig()
