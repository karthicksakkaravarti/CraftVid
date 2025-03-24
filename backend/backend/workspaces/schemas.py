from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiTypes

# Success Response Examples
LIST_WORKSPACE_200 = OpenApiExample(
    'Success Response',
    value={
        "status": "success",
        "code": 200,
        "message": "Workspaces retrieved successfully",
        "data": {
            "count": 1,
            "results": [{
                "id": 1,
                "name": "Marketing Team 2024",
                "description": "Our team's workspace for marketing campaigns",
                "visibility": "private",
                "owner": {
                    "id": 1,
                    "email": "owner@example.com",
                    "username": "owner"
                },
                "members": [{
                    "user": {
                        "id": 2,
                        "email": "member@example.com",
                        "username": "member"
                    },
                    "role": "editor",
                    "joined_at": "2024-03-20T10:00:00Z"
                }],
                "thumbnail": "https://example.com/thumbnails/workspace.jpg",
                "tags": ["marketing", "social-media", "2024"],
                "created_at": "2024-03-20T09:00:00Z"
            }]
        }
    }
)

CREATE_WORKSPACE_REQUEST = OpenApiExample(
    'Create Workspace Request',
    value={
        "name": "Marketing Team 2024",
        "description": "Our team's workspace for marketing campaigns",
        "visibility": "private",
        "members": ["member1@example.com", "member2@example.com"],
        "thumbnail": "https://example.com/thumbnails/workspace.jpg",
        "tags": ["marketing", "social-media", "2024"]
    }
)

CREATE_WORKSPACE_201 = OpenApiExample(
    'Success Response',
    value={
        "status": "success",
        "code": 201,
        "message": "Workspace created successfully",
        "data": {
            "id": 1,
            "name": "Marketing Team 2024",
            "description": "Our team's workspace for marketing campaigns",
            "visibility": "private",
            "owner": {
                "id": 1,
                "email": "owner@example.com",
                "username": "owner"
            },
            "members": [],
            "thumbnail": "https://example.com/thumbnails/workspace.jpg",
            "tags": ["marketing", "social-media", "2024"],
            "created_at": "2024-03-20T09:00:00Z"
        }
    }
)

ADD_MEMBER_REQUEST = OpenApiExample(
    'Add Member Request',
    value={
        "user_id": 123,
        "role": "editor"  # Optional, defaults to 'viewer'
    }
)

ADD_MEMBER_201 = OpenApiExample(
    'Success Response',
    value={
        "status": "success",
        "code": 201,
        "message": "Member added successfully",
        "data": {
            "user": {
                "id": 123,
                "email": "member@example.com",
                "username": "member"
            },
            "role": "editor",
            "joined_at": "2024-03-20T10:00:00Z"
        }
    }
)

REMOVE_MEMBER_REQUEST = OpenApiExample(
    'Remove Member Request',
    value={
        "user_id": 123
    }
)

UPDATE_MEMBER_ROLE_REQUEST = OpenApiExample(
    'Update Member Role Request',
    value={
        "user_id": 123,
        "role": "admin"  # Choices: admin, editor, viewer
    }
)

UPDATE_MEMBER_ROLE_200 = OpenApiExample(
    'Success Response',
    value={
        "status": "success",
        "code": 200,
        "message": "Member role updated successfully",
        "data": {
            "user": {
                "id": 123,
                "email": "member@example.com",
                "username": "member"
            },
            "role": "admin",
            "joined_at": "2024-03-20T10:00:00Z"
        }
    }
)

# Error Response Examples
ERROR_401 = OpenApiExample(
    'Unauthorized Error',
    value={
        "status": "error",
        "code": 401,
        "message": "Authentication failed",
        "errors": "Authentication credentials were not provided"
    }
)

ERROR_403 = OpenApiExample(
    'Permission Error',
    value={
        "status": "error",
        "code": 403,
        "message": "Permission denied",
        "errors": "You do not have permission to perform this action"
    }
)

ERROR_404 = OpenApiExample(
    'Not Found Error',
    value={
        "status": "error",
        "code": 404,
        "message": "Resource not found",
        "errors": "Resource not found"
    }
)

ERROR_409 = OpenApiExample(
    'Conflict Error',
    value={
        "status": "error",
        "code": 409,
        "message": "Database integrity error",
        "errors": "Resource already exists"
    }
)

ERROR_500 = OpenApiExample(
    'Server Error',
    value={
        "status": "error",
        "code": 500,
        "message": "Internal server error",
        "errors": "An unexpected error occurred"
    }
)

ERROR_400_VALIDATION = OpenApiExample(
    'Validation Error',
    value={
        "status": "error",
        "code": 400,
        "message": "Validation error occurred",
        "errors": "Invalid input data"
    }
)

ERROR_400_MEMBER_VALIDATION = OpenApiExample(
    'Member Validation Error',
    value={
        "status": "error",
        "code": 400,
        "message": "Validation error occurred",
        "errors": "user_id is required"
    }
)

ERROR_400_ROLE_VALIDATION = OpenApiExample(
    'Role Validation Error',
    value={
        "status": "error",
        "code": 400,
        "message": "Validation error occurred",
        "errors": "user_id and role are required"
    }
)

# Media Response Examples
LIST_MEDIA_200 = OpenApiExample(
    'List Media Success Response',
    value={
        "status": "success",
        "code": 200,
        "message": "Media files retrieved successfully",
        "data": {
            "count": 2,
            "results": [{
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "intro_video.mp4",
                "file_type": "video",
                "file": "http://example.com/media/intro_video.mp4",
                "file_size": 15728640,  # 15MB in bytes
                "file_size_display": "15.0 MB",
                "duration": 180.5,
                "thumbnail_url": "http://example.com/thumbnails/intro_video.jpg",
                "metadata": {
                    "resolution": "1920x1080",
                    "codec": "h264",
                    "fps": 30
                },
                "uploaded_by_name": "John Doe",
                "created_at": "2024-03-20T09:00:00Z",
                "updated_at": "2024-03-20T09:00:00Z"
            },
            {
                "id": "550e8400-e29b-41d4-a716-446655440001",
                "name": "background_music.mp3",
                "file_type": "audio",
                "file": "http://example.com/media/background_music.mp3",
                "file_size": 5242880,  # 5MB in bytes
                "file_size_display": "5.0 MB",
                "duration": 320.0,
                "thumbnail_url": None,
                "metadata": {
                    "bitrate": "320kbps",
                    "sample_rate": "44100Hz",
                    "channels": 2
                },
                "uploaded_by_name": "Jane Smith",
                "created_at": "2024-03-20T10:00:00Z",
                "updated_at": "2024-03-20T10:00:00Z"
            }]
        }
    }
)

# Update the UPLOAD_MEDIA_REQUEST example
UPLOAD_MEDIA_REQUEST = OpenApiExample(
    'Upload Media Request Example',
    summary="Example of media upload request",
    description="Example request for uploading a media file",
    value={
        "name": "project_video.mp4",
        "file_type": "video",
        "duration": 180.5,
        "file": "<file>",
        "metadata": {
            "resolution": "1920x1080",
            "codec": "h264",
            "fps": 30
        }
    },
    request_only=True
)

UPLOAD_MEDIA_201 = OpenApiExample(
    'Upload Media Success Response',
    value={
        "status": "success",
        "code": 201,
        "message": "Media file uploaded successfully",
        "data": {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "name": "project_video.mp4",
            "file_type": "video",
            "file": "http://example.com/media/project_video.mp4",
            "file_size": 15728640,
            "file_size_display": "15.0 MB",
            "duration": 180.5,
            "thumbnail_url": "http://example.com/thumbnails/project_video.jpg",
            "metadata": {
                "resolution": "1920x1080",
                "codec": "h264",
                "fps": 30
            },
            "uploaded_by_name": "John Doe",
            "created_at": "2024-03-20T09:00:00Z",
            "updated_at": "2024-03-20T09:00:00Z"
        }
    }
)

ERROR_400_MEDIA_VALIDATION = OpenApiExample(
    'Media Validation Error',
    value={
        "status": "error",
        "code": 400,
        "message": "Validation error occurred",
        "errors": {
            "file": ["This field is required."],
            "file_type": ["Invalid file type. Choose from: video, audio, image, document"]
        }
    }
)

ERROR_413_FILE_TOO_LARGE = OpenApiExample(
    'File Too Large Error',
    value={
        "status": "error",
        "code": 413,
        "message": "File too large",
        "errors": "The uploaded file exceeds the maximum allowed size"
    }
)

ERROR_415_UNSUPPORTED_MEDIA = OpenApiExample(
    'Unsupported Media Type Error',
    value={
        "status": "error",
        "code": 415,
        "message": "Unsupported media type",
        "errors": "The uploaded file format is not supported"
    }
) 


