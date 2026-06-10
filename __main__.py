# -*- coding: utf-8 -*-
"""CLI-Entrypoint: python -m KnowledgeDigest [--gui|--web|...]"""

import sys

if "--gui" in sys.argv:
    sys.argv.remove("--gui")
    from .gui.app import launch_gui
    sys.exit(launch_gui())
elif "--web" in sys.argv:
    sys.argv.remove("--web")
    from .web_viewer import launch_web
    sys.exit(launch_web())
else:
    from .digest import main
    sys.exit(main())
