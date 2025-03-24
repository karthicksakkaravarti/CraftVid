"""
Custom template tags for the workspaces app.
"""
from django import template

register = template.Library()

@register.simple_tag
def count_scripts(workspace):
    """Count the number of scripts in a workspace."""
    return workspace.scripts.count()

@register.simple_tag
def count_finalized_scripts(workspace):
    """Count the number of finalized scripts in a workspace."""
    return workspace.scripts.filter(status='finalized').count()

@register.simple_tag
def count_videos(workspace):
    """Count the number of screens in a workspace."""
    return workspace.screens.count()

@register.simple_tag
def count_generated_videos(workspace):
    """Count the number of screens with output files in a workspace."""
    return workspace.screens.filter(output_file__isnull=False).count()

@register.filter
def get_item(dictionary, key):
    """
    Template filter to get an item from a dictionary by key.
    
    Usage:
        {{ my_dict|get_item:key_variable }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key) 