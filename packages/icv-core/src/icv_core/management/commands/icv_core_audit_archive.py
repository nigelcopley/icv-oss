"""Management command to archive old audit entries."""

from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _


class Command(BaseCommand):
    help = _("Archive AuditEntry rows older than the configured retention period.")

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help=_("Override the retention threshold in days (default: ICV_CORE_AUDIT_RETENTION_DAYS)."),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=_("Report how many entries would be archived without making changes."),
        )

    def handle(self, *args, **options) -> None:
        from icv_core.conf import ICV_CORE_AUDIT_ENABLED

        if not ICV_CORE_AUDIT_ENABLED:
            self.stderr.write(self.style.WARNING(_("ICV_CORE_AUDIT_ENABLED is False. Nothing to archive.")))
            return

        from datetime import timedelta

        from django.utils import timezone

        from icv_core.audit.models import AuditEntry
        from icv_core.conf import ICV_CORE_AUDIT_RETENTION_DAYS

        days = options["days"] or ICV_CORE_AUDIT_RETENTION_DAYS
        cutoff = timezone.now() - timedelta(days=days)
        qs = AuditEntry.objects.filter(created_at__lt=cutoff)
        count = qs.count()

        if options["dry_run"]:
            self.stdout.write(
                self.style.SUCCESS(
                    _("Dry run: %(count)d entries eligible for archival (older than %(days)d days).")
                    % {"count": count, "days": days}
                )
            )
            return

        self.stdout.write(
            _("%(count)d entries eligible for archival. Implement archive backend to proceed.") % {"count": count}
        )
