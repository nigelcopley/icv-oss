"""Admin configuration for icv-core.

No concrete models in the core layer. Provides IcvSoftDeleteAdmin mixin
for consuming projects.
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _


class IcvSoftDeleteAdmin(admin.ModelAdmin):
    """
    Admin mixin for SoftDeleteModel subclasses.

    Includes soft-deleted records in the admin queryset and provides
    restore/soft-delete bulk actions.

    Usage::

        @admin.register(MyModel)
        class MyModelAdmin(IcvSoftDeleteAdmin):
            ...
    """

    list_filter = ("is_active",)

    def get_queryset(self, request):
        """Include soft-deleted records in the admin list."""
        return self.model.all_objects.all()

    actions = ["soft_delete_selected", "restore_selected"]

    @admin.action(description=_("Soft-delete selected records"))
    def soft_delete_selected(self, request, queryset) -> None:
        for obj in queryset.filter(is_active=True):
            obj.soft_delete()

    @admin.action(description=_("Restore selected records"))
    def restore_selected(self, request, queryset) -> None:
        for obj in queryset.filter(is_active=False):
            obj.restore()
