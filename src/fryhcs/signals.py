# based on django_browser_reload

from pathlib import Path

from django.dispatch import receiver
from django.utils.autoreload import autoreload_started, file_changed, is_django_path
from django.contrib.staticfiles.finders import get_finders

from fryhcs.config import fryconfig

import threading
import logging

RELOAD_DEBOUNCE_TIME = 0.05

browser_reload_event = threading.Event()
browser_reload_timer = None

css_generator = None
js_generator = None

incremental_generation_count = 0

logger = logging.getLogger('fryhcs.signals')

def trigger_browser_reload():
    browser_reload_event.set()

def browser_reload_soon():
    global browser_reload_timer
    if browser_reload_timer is not None:
        browser_reload_timer.cancel()
    browser_reload_timer = threading.Timer(RELOAD_DEBOUNCE_TIME, trigger_browser_reload)
    browser_reload_timer.start()


def staticfiles_storages():
    for finder in get_finders():
        if hasattr(finder, 'storages') and isinstance(finder.storages, dict):
            yield from finder.storages.values()


@receiver(autoreload_started, dispatch_uid='fryhcs_start_generator')
def start_generator(sender, **kwargs):
    # django框架只监控了django模板的变更，为了浏览器自动更新，
    # 添加对静态资源的监控
    for storage in staticfiles_storages():
        if hasattr(storage, 'location'):
            sender.watch_dir(Path(storage.location), '**/*')

    from fryhcs.utils import create_css_generator, create_js_generator
    global js_generator
    global css_generator
    js_generator = create_js_generator()
    js_generator.generate()
    css_generator = create_css_generator()
    css_generator.generate()


@receiver(file_changed, dispatch_uid='fryhcs_file_changed')
def template_changed(sender, file_path, **kwargs):
    global incremental_generation_count
    if is_django_path(file_path):
        # 我处理不了，不行就重启吧（服务端reload）
        return

    if file_path.is_dir():
        # 目录变更，不触发服务端reload
        return True

    if file_path.suffix == '.swp':
        # vim编辑临时文件，不触发服务端reload
        return True

    # 当有html/pyx文件发生变化时，更新css/js文件
    if file_path.suffix in ('.html', '.pyx'):
        logger.info("generate css for %s...", file_path)
        incremental_generation_count += 1
        if incremental_generation_count >= 10:
            # 为减少垃圾样式信息，每10次增量生成后，做一次全量生成
            incremental_generation_count = 0
            css_generator.generate()
        else:
            css_generator.generate(file_path)
        if file_path.suffix == '.pyx':
            logger.info("generate js for %s...", file_path)
            js_generator.generate([file_path])

    # 当有html、js或css文件发生变更时，不需要服务端reoad，但浏览器需要reload
    if file_path.suffix in ('.html', '.js', '.css'):
        from .views import update_serverid
        update_serverid()
        return True
    # 其他情况，可能要服务端reload
    else:
        return
