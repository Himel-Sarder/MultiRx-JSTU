#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
import io

# Handle PyInstaller stdout/stderr issues
if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'multirx.settings')

    # 🧩 Add --noreload in PyInstaller bundled mode
    if getattr(sys, 'frozen', False):
        os.environ["DJANGO_RUN_MAIN"] = "true"
        if '--noreload' not in sys.argv:
            sys.argv.append('--noreload')

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError("Couldn't import Django.") from exc

    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()
