"""
    fryhcs.cmdline
    ~~~~~~~~~~~~~~~~

    Command line interface.

    :copyright: Copyright 2023 by zenkj<juzejian@gmail.com>
    :license: BSD, see LICENSE for details.
"""


import fnmatch
import os
import subprocess
import sys
import threading
import time
import traceback
import typing as t
from itertools import chain
from pathlib import PurePath, Path

import werkzeug
from werkzeug.serving import make_server
from flask.cli import FlaskGroup, shell_command, routes_command, CertParamType, pass_script_info, get_debug_flag, _debug_option

import click

from fryhcs.utils import create_css_generator, create_js_generator

css_generator = None 
js_generator = None

import logging

logger = logging.getLogger(__name__)

_log_add_style = True

if os.name == "nt":
    try:
        __import__("colorama")
    except ImportError:
        _log_add_style = False


# The various system prefixes where imports are found. Base values are
# different when running in a virtualenv. All reloaders will ignore the
# base paths (usually the system installation). The stat reloader won't
# scan the virtualenv paths, it will only include modules that are
# already imported.
_ignore_always = tuple({sys.base_prefix, sys.base_exec_prefix})
prefix = {*_ignore_always, sys.prefix, sys.exec_prefix}

if hasattr(sys, "real_prefix"):
    # virtualenv < 20
    prefix.add(sys.real_prefix)

_stat_ignore_scan = tuple(prefix)
del prefix
_ignore_common_dirs = {
    "__pycache__",
    ".git",
    ".hg",
    ".tox",
    ".nox",
    ".pytest_cache",
    ".mypy_cache",
}


def _iter_module_paths() -> t.Iterator[str]:
    """Find the filesystem paths associated with imported modules."""
    # List is in case the value is modified by the app while updating.
    for module in list(sys.modules.values()):
        name = getattr(module, "__file__", None)

        if name is None or name.startswith(_ignore_always):
            continue

        while not os.path.isfile(name):
            # Zip file, find the base file without the module path.
            old = name
            name = os.path.dirname(name)

            if name == old:  # skip if it was all directories somehow
                break
        else:
            yield name


def _remove_by_pattern(paths, exclude_patterns):
    for pattern in exclude_patterns:
        paths.difference_update(fnmatch.filter(paths, pattern))


def _find_stat_paths(extra_files, exclude_patterns) -> t.Iterable[str]:
    """Find paths for the stat reloader to watch. Returns imported
    module files, Python files under non-system paths. Extra files and
    Python files under extra directories can also be scanned.

    System paths have to be excluded for efficiency. Non-system paths,
    such as a project root or ``sys.path.insert``, should be the paths
    of interest to the user anyway.
    """
    paths = set()

    for path in chain(list(sys.path), extra_files):
        path = os.path.abspath(path)

        if os.path.isfile(path):
            # zip file on sys.path, or extra file
            paths.add(path)
            continue

        parent_has_py = {os.path.dirname(path): True}

        for root, dirs, files in os.walk(path):
            # Optimizations: ignore system prefixes, __pycache__ will
            # have a py or pyc module at the import path, ignore some
            # common known dirs such as version control and tool caches.
            if (
                root.startswith(_stat_ignore_scan)
                or os.path.basename(root) in _ignore_common_dirs
            ):
                dirs.clear()
                continue

            has_py = False

            for name in files:
                if name.endswith((".py", ".pyc")):
                    has_py = True
                    paths.add(os.path.join(root, name))

            # Optimization: stop scanning a directory if neither it nor
            # its parent contained Python files.
            if not (has_py or parent_has_py[os.path.dirname(root)]):
                dirs.clear()
                continue

            parent_has_py[root] = has_py

    paths.update(_iter_module_paths())
    _remove_by_pattern(paths, exclude_patterns)
    return paths


def _find_watchdog_paths(extra_files, exclude_patterns) -> t.Iterable[str]:
    """Find paths for the stat reloader to watch. Looks at the same
    sources as the stat reloader, but watches everything under
    directories instead of individual files.
    """
    dirs = set()

    for name in chain(list(sys.path), extra_files):
        name = os.path.abspath(name)

        if os.path.isfile(name):
            name = os.path.dirname(name)

        dirs.add(name)

    for name in _iter_module_paths():
        dirs.add(os.path.dirname(name))

    _remove_by_pattern(dirs, exclude_patterns)
    return _find_common_roots(dirs)


def _find_common_roots(paths: t.Iterable[str]) -> t.Iterable[str]:
    root: dict[str, dict] = {}

    for chunks in sorted((PurePath(x).parts for x in paths), key=len, reverse=True):
        node = root

        for chunk in chunks:
            node = node.setdefault(chunk, {})

        node.clear()

    rv = set()

    def _walk(node: t.Mapping[str, dict], path: tuple[str, ...]) -> None:
        for prefix, child in node.items():
            _walk(child, path + (prefix,))

        if not node:
            rv.add(os.path.join(*path))

    _walk(root, ())
    return rv


def _get_args_for_reloading():
    """Determine how the script was executed, and return the args needed
    to execute it again in a new process.
    """
    if sys.version_info >= (3, 10):
        # sys.orig_argv, added in Python 3.10, contains the exact args used to invoke
        # Python. Still replace argv[0] with sys.executable for accuracy.
        return [sys.executable, *sys.orig_argv[1:]]

    rv = [sys.executable]
    py_script = sys.argv[0]
    args = sys.argv[1:]
    # Need to look at main module to determine how it was executed.
    __main__ = sys.modules["__main__"]

    # The value of __package__ indicates how Python was called. It may
    # not exist if a setuptools script is installed as an egg. It may be
    # set incorrectly for entry points created with pip on Windows.
    if getattr(__main__, "__package__", None) is None or (
        os.name == "nt"
        and __main__.__package__ == ""
        and not os.path.exists(py_script)
        and os.path.exists(f"{py_script}.exe")
    ):
        # Executed a file, like "python app.py".
        py_script = os.path.abspath(py_script)

        if os.name == "nt":
            # Windows entry points have ".exe" extension and should be
            # called directly.
            if not os.path.exists(py_script) and os.path.exists(f"{py_script}.exe"):
                py_script += ".exe"

            if (
                os.path.splitext(sys.executable)[1] == ".exe"
                and os.path.splitext(py_script)[1] == ".exe"
            ):
                rv.pop(0)

        rv.append(py_script)
    else:
        # Executed a module, like "python -m werkzeug.serving".
        if os.path.isfile(py_script):
            # Rewritten by Python from "-m script" to "/path/to/script.py".
            py_module = t.cast(str, __main__.__package__)
            name = os.path.splitext(os.path.basename(py_script))[0]

            if name != "__main__":
                py_module += f".{name}"
        else:
            # Incorrectly rewritten by pydevd debugger from "-m script" to "script".
            py_module = py_script

        rv.extend(("-m", py_module.lstrip(".")))

    rv.extend(args)
    return rv


class ReloaderLoop:
    name = ""

    def __init__(
        self,
        extra_files = None,
        exclude_patterns = None,
        interval = 1,
    ) -> None:
        self.extra_files: set[str] = {os.path.abspath(x) for x in extra_files or ()}
        self.exclude_patterns: set[str] = set(exclude_patterns or ())
        self.interval = interval

    def __enter__(self):
        """Do any setup, then run one step of the watch to populate the
        initial filesystem state.
        """
        self.run_step()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):  # type: ignore
        """Clean up any resources associated with the reloader."""
        pass

    def run(self) -> None:
        """Continually run the watch step, sleeping for the configured
        interval after each step.
        """
        while True:
            self.run_step()
            time.sleep(self.interval)

    def run_step(self) -> None:
        """Run one step for watching the filesystem. Called once to set
        up initial state, then repeatedly to update it.
        """
        pass

    def restart_with_reloader(self) -> int:
        """Spawn a new Python interpreter with the same arguments as the
        current one, but running the reloader thread.
        """
        while True:
            logger.info(f" * Restarting with {self.name}")
            args = _get_args_for_reloading()
            new_environ = os.environ.copy()
            new_environ["FRYHCS_RUN_MAIN"] = "true"
            exit_code = subprocess.call(args, env=new_environ, close_fds=False)

            if exit_code != 3:
                return exit_code

    def trigger_reload(self, filename: str) -> None:
        self.log_reload(filename)
        generate_static(filename)
        sys.exit(3)

    def log_reload(self, filename: str) -> None:
        filename = os.path.abspath(filename)
        logger.info(f" * Detected change in {filename!r}, reloading")


class StatReloaderLoop(ReloaderLoop):
    name = "stat"

    def __enter__(self) -> ReloaderLoop:
        self.mtimes: dict[str, float] = {}
        return super().__enter__()

    def run_step(self) -> None:
        for name in _find_stat_paths(self.extra_files, self.exclude_patterns):
            try:
                mtime = os.stat(name).st_mtime
            except OSError:
                continue

            old_time = self.mtimes.get(name)

            if old_time is None:
                self.mtimes[name] = mtime
                continue

            if mtime > old_time:
                self.trigger_reload(name)


class WatchdogReloaderLoop(ReloaderLoop):
    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        from watchdog.observers import Observer
        from watchdog.events import PatternMatchingEventHandler
        from watchdog.events import EVENT_TYPE_OPENED
        from watchdog.events import FileModifiedEvent

        super().__init__(*args, **kwargs)
        trigger_reload = self.trigger_reload

        class EventHandler(PatternMatchingEventHandler):
            def on_any_event(self, event: FileModifiedEvent):  # type: ignore
                if event.event_type == EVENT_TYPE_OPENED:
                    return

                trigger_reload(event.src_path)

        reloader_name = Observer.__name__.lower()  # type: ignore[attr-defined]

        if reloader_name.endswith("observer"):
            reloader_name = reloader_name[:-8]

        self.name = f"watchdog ({reloader_name})"
        self.observer = Observer()
        # Extra patterns can be non-Python files, match them in addition
        # to all Python files in default and extra directories. Ignore
        # __pycache__ since a change there will always have a change to
        # the source file (or initial pyc file) as well. Ignore Git and
        # Mercurial internal changes.
        extra_patterns = [p for p in self.extra_files if not os.path.isdir(p)]
        self.event_handler = EventHandler(
            patterns=["*.py", "*.pyc", "*.zip", *extra_patterns],
            ignore_patterns=[
                *[f"*/{d}/*" for d in _ignore_common_dirs],
                *self.exclude_patterns,
            ],
        )
        self.should_reload = False

    def trigger_reload(self, filename: str) -> None:
        # This is called inside an event handler, which means throwing
        # SystemExit has no effect.
        # https://github.com/gorakhargosh/watchdog/issues/294
        self.should_reload = True
        self.log_reload(filename)
        generate_static(filename)


    def __enter__(self) -> ReloaderLoop:
        self.watches: dict[str, t.Any] = {}
        self.observer.start()
        return super().__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):  # type: ignore
        self.observer.stop()
        self.observer.join()

    def run(self) -> None:
        while not self.should_reload:
            self.run_step()
            time.sleep(self.interval)

        sys.exit(3)

    def run_step(self) -> None:
        to_delete = set(self.watches)

        for path in _find_watchdog_paths(self.extra_files, self.exclude_patterns):
            if path not in self.watches:
                try:
                    self.watches[path] = self.observer.schedule(
                        self.event_handler, path, recursive=True
                    )
                except OSError:
                    # Clear this path from list of watches We don't want
                    # the same error message showing again in the next
                    # iteration.
                    self.watches[path] = None

            to_delete.discard(path)

        for path in to_delete:
            watch = self.watches.pop(path, None)

            if watch is not None:
                self.observer.unschedule(watch)


reloader_loops = {
    "stat": StatReloaderLoop,
    "watchdog": WatchdogReloaderLoop,
}

try:
    __import__("watchdog.observers")
except ImportError:
    reloader_loops["auto"] = reloader_loops["stat"]
else:
    reloader_loops["auto"] = reloader_loops["watchdog"]


def ensure_echo_on() -> None:
    """Ensure that echo mode is enabled. Some tools such as PDB disable
    it which causes usability issues after a reload."""
    # tcgetattr will fail if stdin isn't a tty
    if sys.stdin is None or not sys.stdin.isatty():
        return

    try:
        import termios
    except ImportError:
        return

    attributes = termios.tcgetattr(sys.stdin)

    if not attributes[3] & termios.ECHO:
        attributes[3] |= termios.ECHO
        termios.tcsetattr(sys.stdin, termios.TCSANOW, attributes)


def run_with_reloader(
    main_func,
    extra_files = None,
    exclude_patterns = None,
    interval = 1,
    reloader_type = "auto",
) -> None:
    """Run the given function in an independent Python interpreter."""
    import signal

    signal.signal(signal.SIGTERM, lambda *args: sys.exit(0))
    reloader = reloader_loops[reloader_type](
        extra_files=extra_files, exclude_patterns=exclude_patterns, interval=interval
    )

    try:
        if os.environ.get("FRYHCS_RUN_MAIN") == "true":
            ensure_echo_on()
            t = threading.Thread(target=main_func, args=())
            t.daemon = True

            # Enter the reloader to set up initial state, then start
            # the app thread and reloader update loop.
            with reloader:
                t.start()
                reloader.run()
        else:
            sys.exit(reloader.restart_with_reloader())
    except KeyboardInterrupt:
        pass


def is_running_from_reloader() -> bool:
    """Check if the server is running as a subprocess within the
    fryhcs reloader.

    .. versionadded:: 0.10
    """
    return os.environ.get("FRYHCS_RUN_MAIN") == "true"

def _ansi_style(value: str, *styles: str) -> str:
    if not _log_add_style:
        return value

    codes = {
        "bold": 1,
        "red": 31,
        "green": 32,
        "yellow": 33,
        "magenta": 35,
        "cyan": 36,
    }

    for style in styles:
        value = f"\x1b[{codes[style]}m{value}"

    return f"{value}\x1b[0m"


def run(
    hostname,
    port,
    app,
    use_reloader = True,
    use_debugger = True,
    use_evalex = True,
    extra_files = None,
    exclude_patterns = None,
    reloader_interval = 0.5,
    reloader_type = "auto",
    threaded = False,
    processes = 1,
    request_handler = None,
    static_files = {},
    passthrough_errors = False,
    ssl_context = None,
) -> None:
    """Start a development server for a WSGI application. Various
    optional features can be enabled.

    .. warning::

        Do not use the development server when deploying to production.
        It is intended for use only during local development. It is not
        designed to be particularly efficient, stable, or secure.

    :param hostname: The host to bind to, for example ``'localhost'``.
        Can be a domain, IPv4 or IPv6 address, or file path starting
        with ``unix://`` for a Unix socket.
    :param port: The port to bind to, for example ``8080``. Using ``0``
        tells the OS to pick a random free port.
    :param application: The WSGI application to run.
    :param use_reloader: Use a reloader process to restart the server
        process when files are changed.
    :param use_debugger: Use Werkzeug's debugger, which will show
        formatted tracebacks on unhandled exceptions.
    :param use_evalex: Make the debugger interactive. A Python terminal
        can be opened for any frame in the traceback. Some protection is
        provided by requiring a PIN, but this should never be enabled
        on a publicly visible server.
    :param extra_files: The reloader will watch these files for changes
        in addition to Python modules. For example, watch a
        configuration file.
    :param exclude_patterns: The reloader will ignore changes to any
        files matching these :mod:`fnmatch` patterns. For example,
        ignore cache files.
    :param reloader_interval: How often the reloader tries to check for
        changes.
    :param reloader_type: The reloader to use. The ``'stat'`` reloader
        is built in, but may require significant CPU to watch files. The
        ``'watchdog'`` reloader is much more efficient but requires
        installing the ``watchdog`` package first.
    :param threaded: Handle concurrent requests using threads. Cannot be
        used with ``processes``.
    :param processes: Handle concurrent requests using up to this number
        of processes. Cannot be used with ``threaded``.
    :param request_handler: Use a different
        :class:`~BaseHTTPServer.BaseHTTPRequestHandler` subclass to
        handle requests.
    :param static_files: A dict mapping URL prefixes to directories to
        serve static files from using
        :class:`~werkzeug.middleware.SharedDataMiddleware`.
    :param passthrough_errors: Don't catch unhandled exceptions at the
        server level, let the server crash instead. If ``use_debugger``
        is enabled, the debugger will still catch such errors.
    :param ssl_context: Configure TLS to serve over HTTPS. Can be an
        :class:`ssl.SSLContext` object, a ``(cert_file, key_file)``
        tuple to create a typical context, or the string ``'adhoc'`` to
        generate a temporary self-signed certificate.

    .. versionchanged:: 2.1
        Instructions are shown for dealing with an "address already in
        use" error.

    .. versionchanged:: 2.1
        Running on ``0.0.0.0`` or ``::`` shows the loopback IP in
        addition to a real IP.

    .. versionchanged:: 2.1
        The command-line interface was removed.

    .. versionchanged:: 2.0
        Running on ``0.0.0.0`` or ``::`` shows a real IP address that
        was bound as well as a warning not to run the development server
        in production.

    .. versionchanged:: 2.0
        The ``exclude_patterns`` parameter was added.

    .. versionchanged:: 0.15
        Bind to a Unix socket by passing a ``hostname`` that starts with
        ``unix://``.

    .. versionchanged:: 0.10
        Improved the reloader and added support for changing the backend
        through the ``reloader_type`` parameter.

    .. versionchanged:: 0.9
        A command-line interface was added.

    .. versionchanged:: 0.8
        ``ssl_context`` can be a tuple of paths to the certificate and
        private key files.

    .. versionchanged:: 0.6
        The ``ssl_context`` parameter was added.

    .. versionchanged:: 0.5
       The ``static_files`` and ``passthrough_errors`` parameters were
       added.
    """
    if not isinstance(port, int):
        raise TypeError("port must be an integer")

    global css_generator, js_generator
    with app.app_context():
        css_generator = create_css_generator()
        js_generator = create_js_generator()

    if use_reloader:
        from uuid import uuid4
        server_id = uuid4().hex
        @app.get('/_hotreload')
        def fryhcs_hotreload():
            return f'{{"serverId": "{server_id}"}}'

    static_files = static_files if static_files else {}

    with app.app_context():
        from fryhcs.config import fryconfig
        static_files[fryconfig.static_url] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    
    if static_files:
        from werkzeug.middleware.shared_data import SharedDataMiddleware

        app.wsgi_app = SharedDataMiddleware(app.wsgi_app, static_files)

    if use_debugger:
        from werkzeug.debug import DebuggedApplication

        app.wsgi_app = DebuggedApplication(app.wsgi_app, evalex=use_evalex)

    if not is_running_from_reloader():
        fd = None
    else:
        fd = int(os.environ["FRYHCS_SERVER_FD"])

    srv = make_server(
        hostname,
        port,
        app,
        threaded,
        processes,
        request_handler,
        passthrough_errors,
        ssl_context,
        fd=fd,
    )
    srv.socket.set_inheritable(True)
    os.environ["FRYHCS_SERVER_FD"] = str(srv.fileno())

    if not is_running_from_reloader():
        srv.log_startup()
        generate_static()
        logger.info(_ansi_style("Press CTRL+C to quit", "yellow"))

    if use_reloader:
        try:
            run_with_reloader(
                srv.serve_forever,
                extra_files=extra_files,
                exclude_patterns=exclude_patterns,
                interval=reloader_interval,
                reloader_type=reloader_type,
            )
        finally:
            srv.server_close()
    else:
        srv.serve_forever()


def generate_static(path=None):
    if not css_generator or not js_generator:
        return
    if not path:
        logger.info("Regenerating all js files and css files from .pyx files...")
        css_generator.generate()
        js_generator.generate(clean=True)
    else:
        path = Path(path).absolute()
        if path.suffix == '.pyx':
            logger.info(f"Regenerating js files and css file for {str(path)}...")
            css_generator.generate(path)
            js_generator.generate([path])


def show_server_banner(debug, app_import_path):
    """Show extra startup messages the first time the server is run,
    ignoring the reloader.
    """
    if is_running_from_reloader():
        return

    if app_import_path is not None:
        click.echo(f" * Serving Fryhcs app '{app_import_path}'")

    if debug is not None:
        click.echo(f" * Debug mode: {'on' if debug else 'off'}")


def _validate_key(ctx, param, value):
    """The ``--key`` option must be specified when ``--cert`` is a file.
    Modifies the ``cert`` param to be a ``(cert, key)`` pair if needed.
    """
    cert = ctx.params.get("cert")
    is_adhoc = cert == "adhoc"

    try:
        import ssl
    except ImportError:
        is_context = False
    else:
        is_context = isinstance(cert, ssl.SSLContext)

    if value is not None:
        if is_adhoc:
            raise click.BadParameter(
                'When "--cert" is "adhoc", "--key" is not used.', ctx, param
            )

        if is_context:
            raise click.BadParameter(
                'When "--cert" is an SSLContext object, "--key is not used.', ctx, param
            )

        if not cert:
            raise click.BadParameter('"--cert" must also be specified.', ctx, param)

        ctx.params["cert"] = cert, value

    else:
        if cert and not (is_adhoc or is_context):
            raise click.BadParameter('Required when using "--cert".', ctx, param)

    return value


class SeparatedPathType(click.Path):
    """Click option type that accepts a list of values separated by the
    OS's path separator (``:``, ``;`` on Windows). Each value is
    validated as a :class:`click.Path` type.
    """

    def convert(self, value, param, ctx):
        items = self.split_envvar_value(value)
        super_convert = super().convert
        return [super_convert(item, param, ctx) for item in items]


@click.command("run", short_help="Run a development server.")
@click.option("--host", "-h", default="127.0.0.1", help="The interface to bind to.")
@click.option("--port", "-p", default=5000, help="The port to bind to.")
@click.option(
    "--cert",
    type=CertParamType(),
    help="Specify a certificate file to use HTTPS.",
    is_eager=True,
)
@click.option(
    "--key",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    callback=_validate_key,
    expose_value=False,
    help="The key file to use when specifying a certificate.",
)
@click.option(
    "--reload/--no-reload",
    default=None,
    help="Enable or disable the reloader. By default the reloader "
    "is active if debug is enabled.",
)
@click.option(
    "--debugger/--no-debugger",
    default=None,
    help="Enable or disable the debugger. By default the debugger "
    "is active if debug is enabled.",
)
@click.option(
    "--with-threads/--without-threads",
    default=True,
    help="Enable or disable multithreading.",
)
@click.option(
    "--extra-files",
    default=None,
    type=SeparatedPathType(),
    help=(
        "Extra files that trigger a reload on change. Multiple paths"
        f" are separated by {os.path.pathsep!r}."
    ),
)
@click.option(
    "--exclude-patterns",
    default=None,
    type=SeparatedPathType(),
    help=(
        "Files matching these fnmatch patterns will not trigger a reload"
        " on change. Multiple patterns are separated by"
        f" {os.path.pathsep!r}."
    ),
)
@pass_script_info
def run_command(
    info,
    host,
    port,
    reload,
    debugger,
    with_threads,
    cert,
    extra_files,
    exclude_patterns,
):
    """Run a local development server.

    This server is for development purposes only. It does not provide
    the stability, security, or performance of production WSGI servers.

    The reloader and debugger are enabled by default with the '--debug'
    option.
    """
    try:
        app = info.load_app()
    except Exception as e:
        if is_running_from_reloader():
            # When reloading, print out the error immediately, but raise
            # it later so the debugger or server can handle it.
            traceback.print_exc()
            err = e

            def app(environ, start_response):
                raise err from None

        else:
            # When not reloading, raise the error immediately so the
            # command fails.
            raise e from None

    debug = get_debug_flag()

    if reload is None:
        reload = debug

    if debugger is None:
        debugger = debug

    show_server_banner(debug, info.app_import_path)

    run(
        host,
        port,
        app,
        use_reloader=reload,
        use_debugger=debugger,
        threaded=with_threads,
        ssl_context=cert,
        extra_files=extra_files,
        exclude_patterns=exclude_patterns,
    )

run_command.params.insert(0, _debug_option)


@click.command("build", short_help="Build js files and css style file for all .pyx files.")
@pass_script_info
def build_command(info):
    """Build js files and css style file for all .pyx files."""
    app = info.load_app()
    with app.app_context():
        css_generator = create_css_generator()
        js_generator = create_js_generator()
        logger.info("Regenerating all js files and css files from .pyx files...")
        css_generator.generate()
        js_generator.generate(clean=True)


@click.command("x2y", short_help="Convert specified .pyx file into .py file.")
@click.argument("pyxfile")
def x2y_command(pyxfile):
    """Convert specified .pyx file into .py file."""
    from fryhcs.pyx.generator import pyx_to_py
    path = Path(pyxfile)
    if not path.is_file():
        print("Error: can't open file '{pyxfile}'.")
        sys.exit(1)
    with path.open('r') as f:
        data = f.read()
    print(pyx_to_py(data))


class FryhcsGroup(FlaskGroup):
    def __init__(self, **extra):
        extra.pop('add_default_commands', None)
        super().__init__(add_default_commands=False, **extra) 
        self.add_command(run_command)
        self.add_command(build_command)
        self.add_command(x2y_command)
        self.add_command(shell_command)
        self.add_command(routes_command)

cli = FryhcsGroup(
    name="fryhcs",
    help="""\
A general utility for Fryhcs applications.

An application to load must be given with the '--app' option,
'FLASK_APP' environment variable, or with a 'wsgi.py' or 'app.py' file
in the current directory.
""",
)


def main():
    # 让python可以import .pyx文件
    from fryhcs.pyx.pyxloader import install_path_hook
    install_path_hook()
    cli.main()


if __name__ == "__main__":
    main()
