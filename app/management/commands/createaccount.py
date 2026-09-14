"""Create a doctor, receptionist or administrator account.

Public registration was removed, so accounts are provisioned here (or from the
admin panel / Django admin). For clinic accounts the role is derived from the
login ID prefix:

    python manage.py createaccount HF1234 --first-name Ayesha --last-name Rahman \
        --specialization Nephrologist
    python manage.py createaccount RE0001 --first-name Rafi --last-name Ahmed
    python manage.py createaccount admin-RX --role admin

An ID of HF#### is always a doctor and RE#### always a receptionist. Any other
ID needs --role (it defaults to admin), and administrator accounts also receive
Django-admin access.
"""

from getpass import getpass

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from app.models import (
    LOGIN_ID_RE,
    normalize_login_id,
    ROLE_ADMIN,
    ROLE_CHOICES,
    ROLE_DOCTOR,
    role_for_user_id,
)


class Command(BaseCommand):
    help = "Create a doctor (HF####), receptionist (RE####) or administrator account."

    def add_arguments(self, parser):
        parser.add_argument(
            'login_id',
            help="HF#### for a doctor, RE#### for a receptionist, anything else for an admin",
        )
        parser.add_argument('--password', help="Password (prompted for if omitted)")
        parser.add_argument('--first-name', default='')
        parser.add_argument('--last-name', default='')
        parser.add_argument('--email', default='')
        parser.add_argument('--phone', default='')
        parser.add_argument('--specialization', default='', help="Doctors only")
        parser.add_argument(
            '--role', choices=[value for value, _ in ROLE_CHOICES], default=None,
            help="Role for IDs that are not HF####/RE#### (default: admin)",
        )
        parser.add_argument('--staff', action='store_true', help="Grant Django admin access")

    def handle(self, *args, **options):
        User = get_user_model()
        login_id = normalize_login_id(options['login_id'])

        derived = role_for_user_id(login_id)
        if derived and options['role'] and options['role'] != derived:
            raise CommandError(
                f"'{login_id}' is a {derived} ID; --role {options['role']} contradicts it."
            )
        role = derived or options['role'] or ROLE_ADMIN
        if not LOGIN_ID_RE.match(login_id):
            raise CommandError(
                f"'{login_id}' is not a valid login ID. Use 3-32 letters, digits, "
                f"dots, dashes or underscores."
            )

        if User.objects.filter(doctor_id__iexact=login_id).exists():
            raise CommandError(f"An account with ID {login_id} already exists.")

        password = options['password']
        if not password:
            password = getpass("Password: ")
            if password != getpass("Password (again): "):
                raise CommandError("Passwords did not match.")
        if not password:
            raise CommandError("Password cannot be empty.")

        user = User.objects.create_user(
            doctor_id=login_id,
            password=password,
            first_name=options['first_name'],
            last_name=options['last_name'],
            email=options['email'],
            phone=options['phone'],
            role=role,
            specialization=options['specialization'] if role == ROLE_DOCTOR else '',
            is_staff=options['staff'] or role == ROLE_ADMIN,
            is_superuser=role == ROLE_ADMIN,
        )

        self.stdout.write(self.style.SUCCESS(
            f"Created {user.role_label.lower()} account {user.doctor_id}"
            + (f" for {user.display_name}" if user.first_name or user.last_name else "")
        ))
