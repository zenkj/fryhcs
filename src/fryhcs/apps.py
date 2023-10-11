from django.apps import AppConfig


class FryhcsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'fryhcs'

    def ready(self):
        # 注册信号处理函数
        from . import signals

        # 让python可以import .pyx文件
        from .pyx.pyxloader import install_path_hook
        install_path_hook()
