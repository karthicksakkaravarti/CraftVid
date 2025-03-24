from django import template
from datetime import date

register = template.Library()

@register.filter
def get_current_month(monthly_usage):
    """Get the current month's usage data from the monthly_usage dictionary."""
    current_month = date.today().strftime("%Y-%m")
    return monthly_usage.get(current_month, {})

@register.filter
def get_feature_limit(features, feature_name):
    """Get the limit for a specific feature from the subscription features."""
    return features.get(f"{feature_name}_limit", 0)

@register.filter
def percentage_of(value, max_value):
    """Calculate what percentage value is of max_value."""
    if max_value <= 0:
        return 0
    return min(100, int((value / max_value) * 100)) 