"""Management command to validate icv-core configuration."""

from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _


class Command(BaseCommand):
    help = _("Validate icv-core configuration and report common issues.")

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--fix",
            action="store_true",
            help=_("Attempt to auto-correct common configuration issues."),
        )

    def handle(self, *args, **options) -> None:
        from icv_core import conf

        issues: list[str] = []

        if conf.ICV_CORE_TRACK_CREATED_BY:
            from django.conf import settings

            middleware = getattr(settings, "MIDDLEWARE", [])
            if "icv_core.middleware.CurrentUserMiddleware" not in middleware:
                issues.append("ICV_CORE_TRACK_CREATED_BY=True but CurrentUserMiddleware is not in MIDDLEWARE.")

        if conf.ICV_CORE_AUDIT_ENABLED:
            from django.conf import settings

            middleware = getattr(settings, "MIDDLEWARE", [])
            if "icv_core.audit.middleware.AuditRequestMiddleware" not in middleware:
                issues.append("ICV_CORE_AUDIT_ENABLED=True but AuditRequestMiddleware is not in MIDDLEWARE.")

        if issues:
            self.stderr.write(self.style.WARNING(_("icv-core configuration issues found:")))
            for issue in issues:
                self.stderr.write(f"  - {issue}")
        else:
            self.stdout.write(self.style.SUCCESS(_("icv-core configuration OK.")))
