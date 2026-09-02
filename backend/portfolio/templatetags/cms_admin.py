"""Template access to portfolio.assets."""
from django import template

from ..assets import asset_url

register = template.Library()


@register.simple_tag
def cms_asset(path: str) -> str:
    return asset_url(path)
