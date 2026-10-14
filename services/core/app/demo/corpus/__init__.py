"""Synthetic corpus for the Northside demo tenant (13-demo-data §2-§4).

Pure data + bytes, no database access:
    build_catalog(today)            master data (single source of truth for the seed)
    plan_day(catalog, day, n, seed) POs/GRNs + invoice documents for one day, heroes included
    PlannedDoc.render()             PDF / dock-photo JPEG bytes + field bboxes
"""

from .catalog import (
    Catalog,
    Contract,
    ContractPrice,
    Entity,
    GLAccount,
    Item,
    Location,
    Vendor,
    build_catalog,
)
from .confidence import doc_confidence
from .heroes import HERO_KEYS, HEROES
from .invoices import PlannedDoc, RenderedDoc, hero_docs, plan_day
from .rng import SEED

__all__ = [
    "HERO_KEYS",
    "HEROES",
    "SEED",
    "Catalog",
    "Contract",
    "ContractPrice",
    "Entity",
    "GLAccount",
    "Item",
    "Location",
    "PlannedDoc",
    "RenderedDoc",
    "Vendor",
    "build_catalog",
    "doc_confidence",
    "hero_docs",
    "plan_day",
]
