from django.contrib import admin
from .models import Workspace, WorkspaceMember, Media, Screen, Script, Channel


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    """Admin interface for Channel model."""
    list_display = ('name', 'website', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'logo', 'website')
        }),
        ('Prompt Templates', {
            'fields': ('prompt_templates',),
            'description': 'JSON dictionary mapping template keys to template file paths'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    """Admin interface for Workspace model."""
    list_display = ('name', 'owner', 'visibility', 'created_at')
    list_filter = ('visibility', 'created_at')
    search_fields = ('name', 'description', 'owner__username')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('owner',)
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'visibility', 'owner', 'thumbnail', 'tags')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(WorkspaceMember)
class WorkspaceMemberAdmin(admin.ModelAdmin):
    """Admin interface for WorkspaceMember model."""
    list_display = ('workspace', 'user', 'role', 'joined_at')
    list_filter = ('role', 'joined_at')
    search_fields = ('workspace__name', 'user__username')
    raw_id_fields = ('workspace', 'user')


@admin.register(Media)
class MediaAdmin(admin.ModelAdmin):
    """Admin interface for Media model."""
    list_display = ('name', 'workspace', 'file_type', 'file_size', 'created_at')
    list_filter = ('file_type', 'created_at')
    search_fields = ('name', 'workspace__name')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('workspace', 'uploaded_by')


@admin.register(Screen)
class ScreenAdmin(admin.ModelAdmin):
    """Admin interface for Screen model."""
    list_display = ('name', 'workspace', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('name', 'workspace__name')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('workspace',)


# @admin.register(Script)
# class ScriptAdmin(admin.ModelAdmin):
#     """Admin interface for Script model."""
#     list_display = ('title', 'workspace', 'version', 'status', 'created_at')
#     list_filter = ('status', 'created_at')
#     search_fields = ('title', 'workspace__name', 'topic')
#     readonly_fields = ('created_at', 'updated_at')
#     raw_id_fields = ('workspace', 'screen', 'created_by') 