"""Minimal test models for icv-taxonomy package tests."""

from __future__ import annotations

from django.db import models


class Article(models.Model):
    """Minimal model for testing term associations with a generic content object."""

    title = models.CharField(max_length=255)

    class Meta:
        app_label = "taxonomy_testapp"

    def __str__(self) -> str:
        return self.title


class Product(models.Model):
    """Second model for testing multi-type term associations."""

    name = models.CharField(max_length=255)

    class Meta:
        app_label = "taxonomy_testapp"

    def __str__(self) -> str:
        return self.name
