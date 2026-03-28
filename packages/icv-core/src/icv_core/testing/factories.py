"""
factory-boy factories for icv-core models.

These are provided for consuming projects to use in their own tests.
icv-core itself has no concrete models, so this module provides base
factory classes and audit model factories.

Usage::

    from icv_core.testing.factories import AuditEntryFactory

    entry = AuditEntryFactory(action="CREATE", event_type="DATA")
"""

import factory
from factory.django import DjangoModelFactory


class AuditEntryFactory(DjangoModelFactory):
    """Factory for AuditEntry records."""

    event_type = factory.Iterator(["SECURITY", "DATA", "SYSTEM", "AUTHENTICATION"])
    action = factory.Iterator(["CREATE", "UPDATE", "DELETE", "LOGIN"])
    user = None
    ip_address = factory.Faker("ipv4")
    user_agent = factory.Faker("user_agent")
    description = factory.Faker("sentence")
    metadata = factory.LazyFunction(dict)

    class Meta:
        model = "icv_core.AuditEntry"


class SystemAlertFactory(DjangoModelFactory):
    """Factory for SystemAlert records."""

    alert_type = "system"
    severity = "warning"
    title = factory.Faker("sentence", nb_words=4)
    message = factory.Faker("paragraph")
    metadata = factory.LazyFunction(dict)
    is_resolved = False

    class Meta:
        model = "icv_core.SystemAlert"
