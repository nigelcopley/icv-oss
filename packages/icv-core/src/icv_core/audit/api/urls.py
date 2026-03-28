"""URL configuration for the icv-core audit API."""

from rest_framework.routers import DefaultRouter

from icv_core.audit.api.views import AdminActivityLogViewSet, AuditEntryViewSet, SystemAlertViewSet

router = DefaultRouter()
router.register(r"entries", AuditEntryViewSet, basename="audit-entry")
router.register(r"admin-activity", AdminActivityLogViewSet, basename="audit-admin-activity")
router.register(r"alerts", SystemAlertViewSet, basename="audit-alert")

urlpatterns = router.urls
