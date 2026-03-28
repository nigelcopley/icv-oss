"""
Template tags for icv-taxonomy.

Usage::

    {% load icv_taxonomy %}

    {# All terms for an object #}
    {% get_terms for product as terms %}

    {# Terms from a specific vocabulary #}
    {% get_terms for product vocabulary "colours" as colour_terms %}

    {# All terms in a vocabulary #}
    {% get_vocabulary_terms "colours" as colours %}

    {# Roots only #}
    {% get_vocabulary_terms "categories" roots_only=True as top_categories %}

    {# Boolean term check #}
    {% has_term product "colours" "red" as is_red %}

All tags silently return an empty queryset / False on any service or model
lookup error so that template rendering is not disrupted by missing data.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django import template

if TYPE_CHECKING:
    from django.db.models import QuerySet

logger = logging.getLogger(__name__)

register = template.Library()


# ---------------------------------------------------------------------------
# get_terms — custom Node tag
# ---------------------------------------------------------------------------


class GetTermsNode(template.Node):
    """Resolves terms for a model instance and stores them in a context var.

    Syntax::

        {% get_terms for <obj> as <varname> %}
        {% get_terms for <obj> vocabulary "<slug>" as <varname> %}
    """

    def __init__(
        self,
        obj_var: str,
        varname: str,
        vocabulary_slug: str | None = None,
    ) -> None:
        self.obj_var = template.Variable(obj_var)
        self.varname = varname
        self.vocabulary_slug = vocabulary_slug

    def render(self, context: template.Context) -> str:  # type: ignore[override]
        try:
            obj = self.obj_var.resolve(context)
            from icv_taxonomy.services import get_terms_for_object

            queryset = get_terms_for_object(obj, vocabulary_slug=self.vocabulary_slug)
            context[self.varname] = queryset
        except template.VariableDoesNotExist:
            context[self.varname] = _empty_term_queryset()
        except Exception:  # noqa: BLE001
            logger.exception("icv_taxonomy: get_terms tag failed silently")
            context[self.varname] = _empty_term_queryset()
        return ""


@register.tag("get_terms")
def do_get_terms(
    parser: template.base.Parser,
    token: template.base.Token,
) -> GetTermsNode:
    """Parse ``{% get_terms for <obj> [vocabulary "<slug>"] as <varname> %}``.

    Raises ``TemplateSyntaxError`` for malformed syntax so template authors
    get immediate feedback during development rather than silent failures.
    """
    bits = token.split_contents()
    tag_name = bits[0]

    # Minimal form: {% get_terms for <obj> as <varname> %}
    # Extended:     {% get_terms for <obj> vocabulary "<slug>" as <varname> %}

    if len(bits) == 4 and bits[1] == "for" and bits[3] == "as":  # noqa: PLR2004
        raise template.TemplateSyntaxError(f"'{tag_name}' tag: missing variable name after 'as'.")

    if len(bits) == 5 and bits[1] == "for" and bits[3] == "as":  # noqa: PLR2004
        # {% get_terms for obj as varname %}
        return GetTermsNode(obj_var=bits[2], varname=bits[4])

    if (
        len(bits) == 7  # noqa: PLR2004
        and bits[1] == "for"
        and bits[3] == "vocabulary"
        and bits[5] == "as"
    ):
        # {% get_terms for obj vocabulary "slug" as varname %}
        vocabulary_slug = bits[4].strip("\"'")
        return GetTermsNode(
            obj_var=bits[2],
            varname=bits[6],
            vocabulary_slug=vocabulary_slug,
        )

    raise template.TemplateSyntaxError(
        f"'{tag_name}' tag requires the syntax: "
        f"{{% {tag_name} for <obj> as <varname> %}} or "
        f'{{% {tag_name} for <obj> vocabulary "<slug>" as <varname> %}}'
    )


# ---------------------------------------------------------------------------
# get_vocabulary_terms — simple_tag
# ---------------------------------------------------------------------------


@register.simple_tag
def get_vocabulary_terms(
    vocabulary_slug: str,
    roots_only: bool = False,
) -> QuerySet:
    """Return active terms for a vocabulary, optionally roots only.

    Usage::

        {% get_vocabulary_terms "colours" as colours %}
        {% get_vocabulary_terms "categories" roots_only=True as top_categories %}

    Returns an empty queryset silently on any error.
    """
    try:
        from icv_taxonomy.conf import get_term_model

        Term = get_term_model()
        qs = Term.objects.filter(vocabulary__slug=vocabulary_slug).select_related("vocabulary")
        if roots_only:
            qs = qs.filter(parent__isnull=True)
        return qs
    except Exception:  # noqa: BLE001
        logger.exception(
            "icv_taxonomy: get_vocabulary_terms tag failed for slug=%r",
            vocabulary_slug,
        )
        return _empty_term_queryset()


# ---------------------------------------------------------------------------
# has_term — simple_tag
# ---------------------------------------------------------------------------


@register.simple_tag
def has_term(
    obj: object,
    vocabulary_slug: str,
    term_slug: str,
) -> bool:
    """Return True if *obj* is tagged with the named term in the given vocabulary.

    Usage::

        {% has_term product "colours" "red" as is_red %}

    Returns False silently on any error.
    """
    try:
        from django.contrib.contenttypes.models import ContentType

        from icv_taxonomy.conf import get_term_model

        Term = get_term_model()

        # Resolve the term — use all_objects to include inactive in check
        try:
            term = Term.objects.get(
                slug=term_slug,
                vocabulary__slug=vocabulary_slug,
            )
        except Term.DoesNotExist:
            return False

        from django.apps import apps

        TermAssociation = apps.get_model("icv_taxonomy", "TermAssociation")
        content_type = ContentType.objects.get_for_model(obj)
        return TermAssociation.objects.filter(
            term=term,
            content_type=content_type,
            object_id=str(obj.pk),  # type: ignore[attr-defined]
        ).exists()
    except Exception:  # noqa: BLE001
        logger.exception(
            "icv_taxonomy: has_term tag failed silently for vocab=%r term=%r",
            vocabulary_slug,
            term_slug,
        )
        return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _empty_term_queryset() -> QuerySet:
    """Return a guaranteed-empty QuerySet for the Term model."""
    try:
        from icv_taxonomy.conf import get_term_model

        return get_term_model().objects.none()
    except Exception:  # noqa: BLE001
        # Absolute last-resort: return a plain empty list disguised as iterable.
        # This should never be reached in a correctly configured project.
        return []  # type: ignore[return-value]
