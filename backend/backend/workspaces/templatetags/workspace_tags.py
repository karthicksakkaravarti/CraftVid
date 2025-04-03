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
    """Get an item from a dictionary using a key."""
    return dictionary.get(key, {})

@register.filter
def filter_published_scripts(scripts):
    """Count scripts that have at least one published platform."""
    published_count = 0
    for script in scripts:
        for platform in script.PUBLISHING_PLATFORMS:
            info = script.publishing_info.get(platform, {})
            if info.get('status') == 'published':
                published_count += 1
                break
    return published_count 