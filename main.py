import os
import sys

def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'multirx.settings')

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError("Couldn't import Django.") from exc

    # Force runserver for PyInstaller
    if getattr(sys, 'frozen', False):
        sys.argv += ['runserver', '127.0.0.1:8000']

    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()
