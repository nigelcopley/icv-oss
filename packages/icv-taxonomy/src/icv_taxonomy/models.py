"""
icv-taxonomy models.

Provides:
  VocabularyType        — text choices enum (flat / hierarchical / faceted)
  RelationshipType      — text choices enum for term-to-term relationships
  AbstractVocabulary    — abstract vocabulary model; subclass to customise
  Vocabulary            — concrete default vocabulary model
  AbstractTerm          — abstract term model (extends TreeNode); subclass to customise
  Term                  — concrete default term model
  AbstractTermRelationship  — abstract typed link between two terms
  TermRelationship      — concrete default term-relationship model
  AbstractTermAssociation   — abstract generic association of a term to any object
  TermAssociation       — concrete default term-association model
  create_term_m2m()     — factory function for typed term M2M join tables
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings as django_settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from icv_tree.models import TreeManager, TreeNode, TreeQuerySet

if TYPE_CHECKING:
    pass

# ------------------------------------------------------------------
# Optional icv-core base model (ADR-007 pattern)
# ------------------------------------------------------------------

try:
    from icv_core.models import BaseModel as _CoreBaseModel

    _BASE = _CoreBaseModel
except ImportError:
    _BASE = models.Model  # type: ignore[assignment,misc]


# ------------------------------------------------------------------
# Enums
# ------------------------------------------------------------------


class VocabularyType(models.TextChoices):
    """Controls structural constraints applied to terms in a vocabulary."""

    FLAT = "flat", _("Flat")
    HIERARCHICAL = "hierarchical", _("Hierarchical")
    FACETED = "faceted", _("Faceted")


class RelationshipType(models.TextChoices):
    """Semantic relationship types between terms (broadly SKOS-aligned)."""

    SYNONYM = "synonym", _("Synonym")
    RELATED = "related", _("Related")
    SEE_ALSO = "see_also", _("See also")
    BROADER = "broader", _("Broader")
    NARROWER = "narrower", _("Narrower")


# ------------------------------------------------------------------
# Managers
# ------------------------------------------------------------------


class ActiveVocabularyManager(models.Manager):
    """Default manager — returns only active vocabularies."""

    def get_queryset(self) -> models.QuerySet:
        return super().get_queryset().filter(is_active=True)


class TaxonomyTermQuerySet(TreeQuerySet):
    """TreeQuerySet subclass filtered to active terms."""

    def active(self) -> TaxonomyTermQuerySet:
        """Return only active terms."""
        return self.filter(is_active=True)


class TaxonomyTermManager(TreeManager):
    """Default manager for AbstractTerm subclasses — returns active terms only."""

    def get_queryset(self) -> TaxonomyTermQuerySet:
        return TaxonomyTermQuerySet(self.model, using=self._db).filter(is_active=True)


# ------------------------------------------------------------------
# AbstractVocabulary
# ------------------------------------------------------------------


class AbstractVocabulary(_BASE):  # type: ignore[valid-type,misc]
    """Abstract vocabulary model.

    A vocabulary defines a named collection of terms with a structural type
    (flat, hierarchical, or faceted). Vocabularies may be open (anyone may add
    terms) or closed (terms are fixed at creation / by staff only).

    Subclass this when you need to extend the vocabulary with project-specific
    fields. The concrete default is ``Vocabulary``.
    """

    name = models.CharField(
        max_length=255,
        unique=True,
        verbose_name=_("name"),
        help_text=_("Human-readable name for the vocabulary. Must be unique."),
    )
    slug = models.SlugField(
        max_length=255,
        unique=True,
        verbose_name=_("slug"),
        help_text=_("URL-safe identifier. Auto-generated from name if left blank (ICV_TAXONOMY_AUTO_SLUG=True)."),
    )
    description = models.TextField(
        blank=True,
        default="",
        verbose_name=_("description"),
        help_text=_("Optional description of the vocabulary's purpose."),
    )
    vocabulary_type = models.CharField(
        max_length=20,
        choices=VocabularyType.choices,
        default=VocabularyType.FLAT,
        verbose_name=_("vocabulary type"),
        help_text=_("Structural type of this vocabulary. Cannot be changed once terms exist (BR-TAX-002)."),
    )
    is_open = models.BooleanField(
        default=True,
        verbose_name=_("is open"),
        help_text=_(
            "If True, new terms may be added freely. If False, the vocabulary is closed to new terms (BR-TAX-003)."
        ),
    )
    allow_multiple = models.BooleanField(
        default=True,
        verbose_name=_("allow multiple"),
        help_text=_("If True, objects may be tagged with multiple terms from this vocabulary."),
    )
    max_depth = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("max depth"),
        help_text=_(
            "Maximum allowed term depth (zero-based). "
            "Null means unlimited. Only meaningful for hierarchical vocabularies."
        ),
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("metadata"),
        help_text=_("Arbitrary key/value metadata. Must be a JSON object."),
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name=_("is active"),
        help_text=_("Inactive vocabularies are hidden from default querysets."),
    )

    objects = ActiveVocabularyManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        """Validate vocabulary business rules.

        BR-TAX-002: vocabulary_type is immutable once terms exist.
        """
        super().clean()

        # Use `not _state.adding` to correctly identify existing instances even when
        # BaseModel auto-assigns a UUID pk at instantiation time.
        if not self._state.adding and self.pk:
            # Check for vocabulary_type change with existing terms (BR-TAX-002).
            try:
                db_instance = self.__class__.all_objects.get(pk=self.pk)
            except self.__class__.DoesNotExist:
                pass
            else:
                if db_instance.vocabulary_type != self.vocabulary_type and self.terms.exists():
                    raise ValidationError(
                        {"vocabulary_type": _("Cannot change vocabulary type once terms exist (BR-TAX-002).")}
                    )

    def save(self, *args, **kwargs) -> None:  # type: ignore[override]
        """Auto-generate and normalise slug before saving.

        BR-TAX-043: Auto-generate slug from name when blank.
        BR-TAX-034: Lowercase slug when ICV_TAXONOMY_CASE_SENSITIVE_SLUGS is False.
        """
        from .conf import get_setting

        auto_slug = get_setting("ICV_TAXONOMY_AUTO_SLUG", True)
        case_sensitive = get_setting("ICV_TAXONOMY_CASE_SENSITIVE_SLUGS", False)
        max_length = get_setting("ICV_TAXONOMY_SLUG_MAX_LENGTH", 255)

        if not self.slug and auto_slug and self.name:
            self.slug = slugify(self.name)[:max_length]

        if self.slug and not case_sensitive:
            self.slug = self.slug.lower()

        super().save(*args, **kwargs)


# ------------------------------------------------------------------
# Vocabulary (concrete default)
# ------------------------------------------------------------------


class Vocabulary(AbstractVocabulary):
    """Default concrete vocabulary model.

    Install ``icv_taxonomy`` and use this directly, or point
    ``ICV_TAXONOMY_VOCABULARY_MODEL`` to your own subclass of
    ``AbstractVocabulary``.
    """

    class Meta(AbstractVocabulary.Meta):
        abstract = False
        db_table = "icv_taxonomy_vocabulary"
        verbose_name = _("vocabulary")
        verbose_name_plural = _("vocabularies")


# ------------------------------------------------------------------
# AbstractTerm
# ------------------------------------------------------------------


class AbstractTerm(TreeNode, _BASE):  # type: ignore[valid-type,misc]
    """Abstract term model.

    Inherits ``TreeNode`` (hard dependency on icv-tree) for materialised-path
    tree behaviour and optionally ``BaseModel`` (uuid PK + timestamps) when
    icv-core is installed.

    A term belongs to exactly one vocabulary. Slug uniqueness is enforced within
    a vocabulary, not globally. Parent must be in the same vocabulary.

    Path uniqueness is scoped per vocabulary via ``tree_scope_field`` so that
    multiple vocabularies can each have independent path numbering without
    collisions.

    Subclass this when you need to extend terms with project-specific fields.
    The concrete default is ``Term``.
    """

    tree_scope_field = "vocabulary"

    vocabulary = models.ForeignKey(
        getattr(django_settings, "ICV_TAXONOMY_VOCABULARY_MODEL", "icv_taxonomy.Vocabulary"),
        on_delete=models.CASCADE,
        related_name="terms",
        verbose_name=_("vocabulary"),
        help_text=_("The vocabulary this term belongs to."),
    )
    name = models.CharField(
        max_length=255,
        verbose_name=_("name"),
        help_text=_("Human-readable term label."),
    )
    slug = models.SlugField(
        max_length=255,
        verbose_name=_("slug"),
        help_text=_(
            "URL-safe identifier, unique within its vocabulary. Auto-generated from name if left blank (BR-TAX-007)."
        ),
    )
    description = models.TextField(
        blank=True,
        default="",
        verbose_name=_("description"),
        help_text=_("Optional description of this term."),
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name=_("is active"),
        help_text=_("Inactive terms are hidden from default querysets."),
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("metadata"),
        help_text=_("Arbitrary key/value metadata. Must be a JSON object."),
    )

    objects = TaxonomyTermManager()
    all_objects = TreeManager()

    class Meta(TreeNode.Meta):
        abstract = True
        ordering = ["path"]
        unique_together = [("vocabulary", "slug"), ("vocabulary", "path")]

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        """Validate term business rules.

        BR-TAX-003: Closed vocabulary rejects new terms.
        BR-TAX-008: Flat vocabulary terms must be root-level (no parent).
        BR-TAX-009: Term depth must not exceed vocabulary max_depth.
        BR-TAX-010: vocabulary FK must not change after creation.
        BR-TAX-014: Parent must belong to the same vocabulary.
        """
        super().clean()

        from .conf import get_setting

        enforce_type = get_setting("ICV_TAXONOMY_ENFORCE_VOCABULARY_TYPE", True)

        # BR-TAX-003: Closed vocabulary rejects new terms.
        # Use _state.adding rather than `not self.pk` because BaseModel (icv-core)
        # assigns a UUID default at instantiation time, making pk truthy even for
        # unsaved instances.
        if self._state.adding and self.vocabulary_id:
            try:
                vocab = self.vocabulary
            except Exception:
                pass
            else:
                if not vocab.is_open:
                    raise ValidationError(_("This vocabulary is closed and does not accept new terms (BR-TAX-003)."))

        # BR-TAX-010: vocabulary must not change after creation.
        # Use `not _state.adding` to correctly identify existing instances even when
        # BaseModel auto-assigns a UUID pk at instantiation time.
        if not self._state.adding and self.pk:
            try:
                db_instance = self.__class__.all_objects.get(pk=self.pk)
            except self.__class__.DoesNotExist:
                pass
            else:
                if db_instance.vocabulary_id != self.vocabulary_id:
                    raise ValidationError(
                        {"vocabulary": _("A term's vocabulary cannot be changed after creation (BR-TAX-010).")}
                    )

        # BR-TAX-014: Parent must belong to same vocabulary.
        if self.parent_id and self.vocabulary_id:
            parent_vocab_id = (
                self.__class__.all_objects.filter(pk=self.parent_id).values_list("vocabulary_id", flat=True).first()
            )
            if parent_vocab_id is not None and parent_vocab_id != self.vocabulary_id:
                raise ValidationError({"parent": _("Parent term must belong to the same vocabulary (BR-TAX-014).")})

        # BR-TAX-008: Flat vocabulary terms must have no parent.
        if enforce_type and self.parent_id and self.vocabulary_id:
            try:
                vocab = self.vocabulary
            except Exception:
                pass
            else:
                if vocab.vocabulary_type == VocabularyType.FLAT:
                    raise ValidationError(
                        {"parent": _("Terms in a flat vocabulary must not have a parent (BR-TAX-008).")}
                    )

        # BR-TAX-009: Depth must not exceed vocabulary max_depth.
        if self.parent_id and self.vocabulary_id:
            try:
                vocab = self.vocabulary
            except Exception:
                pass
            else:
                if vocab.max_depth is not None:
                    # depth is set by icv-tree pre_save; for new nodes we
                    # must compute it from parent.depth + 1.
                    if self._state.adding:
                        try:
                            parent_depth = self.__class__.all_objects.filter(pk=self.parent_id).values_list(
                                "depth", flat=True
                            )[0]
                            candidate_depth = parent_depth + 1
                        except IndexError:
                            candidate_depth = 0
                    else:
                        candidate_depth = self.depth

                    if candidate_depth > vocab.max_depth:
                        raise ValidationError(
                            _(
                                "Term depth %(depth)s exceeds the vocabulary's "
                                "maximum depth of %(max_depth)s (BR-TAX-009)."
                            )
                            % {
                                "depth": candidate_depth,
                                "max_depth": vocab.max_depth,
                            }
                        )

    def save(self, *args, **kwargs) -> None:  # type: ignore[override]
        """Auto-generate slug with collision resolution before saving (BR-TAX-007).

        Appends a numeric suffix when the base slug is already taken within
        this vocabulary, e.g. "my-term", "my-term-2", "my-term-3".
        """
        from .conf import get_setting

        auto_slug = get_setting("ICV_TAXONOMY_AUTO_SLUG", True)
        case_sensitive = get_setting("ICV_TAXONOMY_CASE_SENSITIVE_SLUGS", False)
        max_length = get_setting("ICV_TAXONOMY_SLUG_MAX_LENGTH", 255)

        if not self.slug and auto_slug and self.name:
            base_slug = slugify(self.name)[:max_length]
            if not case_sensitive:
                base_slug = base_slug.lower()
            self.slug = self._resolve_slug_collision(base_slug, max_length)
        elif self.slug and not case_sensitive:
            self.slug = self.slug.lower()

        super().save(*args, **kwargs)

    def _resolve_slug_collision(self, base_slug: str, max_length: int) -> str:
        """Return a slug unique within this vocabulary, appending suffix if needed."""
        qs = self.__class__.all_objects.filter(vocabulary_id=self.vocabulary_id)
        if self.pk:
            qs = qs.exclude(pk=self.pk)

        candidate = base_slug
        counter = 2
        while qs.filter(slug=candidate).exists():
            suffix = f"-{counter}"
            candidate = base_slug[: max_length - len(suffix)] + suffix
            counter += 1
        return candidate


# ------------------------------------------------------------------
# Term (concrete default)
# ------------------------------------------------------------------


class Term(AbstractTerm):
    """Default concrete term model.

    Install ``icv_taxonomy`` and use this directly, or point
    ``ICV_TAXONOMY_TERM_MODEL`` to your own subclass of ``AbstractTerm``.
    """

    class Meta(AbstractTerm.Meta):
        abstract = False
        db_table = "icv_taxonomy_term"
        verbose_name = _("term")
        verbose_name_plural = _("terms")


# ------------------------------------------------------------------
# AbstractTermRelationship
# ------------------------------------------------------------------


class AbstractTermRelationship(models.Model):
    """Abstract typed relationship between two terms.

    Enables SKOS-style semantic links (broader/narrower/related/synonym/see_also)
    between terms. Relationships are directed: term_from → term_to.

    Subclass this when you need project-specific relationship metadata.
    The concrete default is ``TermRelationship``.
    """

    term_from = models.ForeignKey(
        getattr(django_settings, "ICV_TAXONOMY_TERM_MODEL", "icv_taxonomy.Term"),
        on_delete=models.CASCADE,
        related_name="relationships_from",
        verbose_name=_("term from"),
        help_text=_("Origin term of the relationship."),
    )
    term_to = models.ForeignKey(
        getattr(django_settings, "ICV_TAXONOMY_TERM_MODEL", "icv_taxonomy.Term"),
        on_delete=models.CASCADE,
        related_name="relationships_to",
        verbose_name=_("term to"),
        help_text=_("Target term of the relationship."),
    )
    relationship_type = models.CharField(
        max_length=20,
        choices=RelationshipType.choices,
        verbose_name=_("relationship type"),
        help_text=_("Semantic type of the relationship between the two terms."),
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("metadata"),
        help_text=_("Arbitrary key/value metadata. Must be a JSON object."),
    )

    class Meta:
        abstract = True
        unique_together = [("term_from", "term_to", "relationship_type")]

    def __str__(self) -> str:
        return f"{self.term_from} —[{self.get_relationship_type_display()}]→ {self.term_to}"

    def clean(self) -> None:
        """Validate relationship rules.

        BR-TAX-021: A term may not have a relationship with itself.
        """
        super().clean()

        if self.term_from_id and self.term_to_id and self.term_from_id == self.term_to_id:
            raise ValidationError(_("A term cannot have a relationship with itself (BR-TAX-021)."))


# ------------------------------------------------------------------
# TermRelationship (concrete default)
# ------------------------------------------------------------------


class TermRelationship(AbstractTermRelationship):
    """Default concrete term-relationship model."""

    class Meta(AbstractTermRelationship.Meta):
        abstract = False
        db_table = "icv_taxonomy_termrelationship"
        verbose_name = _("term relationship")
        verbose_name_plural = _("term relationships")


# ------------------------------------------------------------------
# AbstractTermAssociation
# ------------------------------------------------------------------


class AbstractTermAssociation(models.Model):
    """Abstract generic association of a term to any Django object.

    Uses Django's ``GenericForeignKey`` so a single table records which terms
    are applied to any model in the project. Ordered for consistent display.

    Subclass this when you need additional metadata on associations.
    The concrete default is ``TermAssociation``.
    """

    term = models.ForeignKey(
        getattr(django_settings, "ICV_TAXONOMY_TERM_MODEL", "icv_taxonomy.Term"),
        on_delete=models.CASCADE,
        related_name="associations",
        verbose_name=_("term"),
        help_text=_("The taxonomy term applied to the object."),
    )
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        verbose_name=_("content type"),
        help_text=_("Content type of the associated object."),
    )
    object_id = models.CharField(
        max_length=255,
        verbose_name=_("object ID"),
        help_text=_(
            "Primary key of the associated object, stored as a string to support integer, UUID, and other PK types."
        ),
    )
    content_object = GenericForeignKey("content_type", "object_id")

    order = models.PositiveIntegerField(
        default=0,
        verbose_name=_("order"),
        help_text=_("Display order of this term association within the object."),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("created at"),
        help_text=_("Timestamp when this association was created."),
    )

    class Meta:
        abstract = True
        unique_together = [("term", "content_type", "object_id")]
        ordering = ["order", "created_at"]

    def __str__(self) -> str:
        return f"{self.term} → {self.content_type}:{self.object_id}"


# ------------------------------------------------------------------
# TermAssociation (concrete default)
# ------------------------------------------------------------------


class TermAssociation(AbstractTermAssociation):
    """Default concrete term-association model."""

    class Meta(AbstractTermAssociation.Meta):
        abstract = False
        db_table = "icv_taxonomy_termassociation"
        verbose_name = _("term association")
        verbose_name_plural = _("term associations")


# ------------------------------------------------------------------
# create_term_m2m factory
# ------------------------------------------------------------------


def create_term_m2m(
    model_class: type[models.Model] | str,
    related_name: str = "taxonomy_terms",
) -> type[models.Model]:
    """Create and return an abstract M2M join-table model linking a model to terms.

    This factory produces a project-specific abstract model that can be made
    concrete by the consuming app. It provides a standardised join table with
    ordering and timestamp support (BR-TAX-044).

    Args:
        model_class: The concrete model to link to terms. Pass a string in
            ``"app_label.ModelName"`` format for forward references.
        related_name: The reverse accessor name on the model for term associations.
            Defaults to ``"taxonomy_terms"``.

    Returns:
        An abstract ``models.Model`` subclass with ``term``, ``content_object``,
        ``order``, and ``created_at`` fields plus a ``unique_together`` constraint.

    Raises:
        TypeError: If ``model_class`` is not a string or a concrete model class.

    Example::

        # In your app's models.py
        ArticleTermM2M = create_term_m2m(Article, related_name="article_terms")

        class ArticleTerm(ArticleTermM2M):
            class Meta(ArticleTermM2M.Meta):
                db_table = "myapp_articleterm"
    """
    if not isinstance(model_class, (str, type)):
        raise TypeError(
            f"create_term_m2m: model_class must be a string or a model class, got {type(model_class)!r} (BR-TAX-044)."
        )

    if isinstance(model_class, type) and (not issubclass(model_class, models.Model) or model_class._meta.abstract):
        raise TypeError(
            f"create_term_m2m: model_class must be a concrete model class, got {model_class!r} (BR-TAX-044)."
        )

    # Build the FK target — either the class itself or a lazy string reference.
    fk_target: type[models.Model] | str = model_class

    attrs: dict = {
        "term": models.ForeignKey(
            getattr(django_settings, "ICV_TAXONOMY_TERM_MODEL", "icv_taxonomy.Term"),
            on_delete=models.CASCADE,
            related_name=related_name,
            verbose_name=_("term"),
        ),
        "content_object": models.ForeignKey(
            fk_target,
            on_delete=models.CASCADE,
            related_name="term_m2m_entries",
            verbose_name=_("object"),
        ),
        "order": models.PositiveIntegerField(
            default=0,
            verbose_name=_("order"),
        ),
        "created_at": models.DateTimeField(
            auto_now_add=True,
            verbose_name=_("created at"),
        ),
        "__str__": lambda self: f"{self.term} → {self.content_object}",
        "Meta": type(
            "Meta",
            (),
            {
                "abstract": True,
                "unique_together": [("term", "content_object")],
                "ordering": ["order", "created_at"],
            },
        ),
        "__module__": __name__,
    }

    model_name = model_class.__name__ if isinstance(model_class, type) else model_class.split(".")[-1]
    class_name = f"{model_name}TermM2M"

    return type(class_name, (models.Model,), attrs)
