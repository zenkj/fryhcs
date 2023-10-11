"""
    fryhcs.__main__
    ~~~~~~~~~~~~~~~

    Main entry point for ``python -m fryhcs``

    :copyright: Copyright 2023 by zenkj<juzejian@gmail.com>
    :license: BSD, see LICENSE for details.
"""

import sys
from fryhcs.cmdline import main

try:
    sys.exit(main())
except KeyboardInterrupt:
    sys.exit(1)
