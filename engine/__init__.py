"""
Recipe 双引擎

engine/schema.py  — Recipe Schema（Pydantic）
engine/recipe.py  — Python Recipe Evaluator（Decimal 精度，正式结算）
engine/recipe.js  — JS Recipe Evaluator（Number 精度，前端实时预览）
"""
from .schema import (
    Recipe,
    RecipeElement,
    QuantityStep,
    PriceStep,
    TierEntry,
)
from .recipe import evaluate_recipe

__all__ = [
    "Recipe", "RecipeElement",
    "QuantityStep", "PriceStep",
    "TierEntry",
    "evaluate_recipe",
]
