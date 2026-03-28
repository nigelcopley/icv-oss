"""Management command to display audit entry statistics."""

from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _


class Command(BaseCommand):
    help = _("Display audit entry statistics.")

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--period",
            choices=["day", "week", "month"],
            default="week",
            help=_("Time period for statistics (default: week)."),
        )

    def handle(self, *args, **options) -> None:
        from icv_core.conf import ICV_CORE_AUDIT_ENABLED

        if not ICV_CORE_AUDIT_ENABLED:
            self.stderr.write(self.style.WARNING(_("ICV_CORE_AUDIT_ENABLED is False. No audit data available.")))
            return

        from datetime import timedelta

        from django.db.models import Count
        from django.utils import timezone

        from icv_core.audit.models import AuditEntry

        period_days = {"day": 1, "week": 7, "month": 30}
        days = period_days[options["period"]]
        since = timezone.now() - timedelta(days=days)

        total = AuditEntry.objects.filter(created_at__gte=since).count()
        by_event_type = (
            AuditEntry.objects.filter(created_at__gte=since)
            .values("event_type")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        self.stdout.write(
            self.style.SUCCESS(
                _("Audit entries in the last %(period)s: %(total)d") % {"period": options["period"], "total": total}
            )
        )
        for row in by_event_type:
            self.stdout.write(f"  {row['event_type']}: {row['count']}")
