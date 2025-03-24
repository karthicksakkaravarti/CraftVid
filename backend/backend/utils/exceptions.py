from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError
from django.db import IntegrityError


def custom_exception_handler(exc, context):
    """
    Custom exception handler for standardized error responses
    """
    
    # First, get the standard error response
    response = exception_handler(exc, context)
    
    # If response is None, there was an unhandled exception
    if response is None:
        if isinstance(exc, ValidationError):
            data = {
                "status": "error",
                "code": status.HTTP_400_BAD_REQUEST,
                "message": "Validation error occurred",
                "errors": exc.message_dict if hasattr(exc, 'message_dict') else str(exc)
            }
            return Response(data, status=status.HTTP_400_BAD_REQUEST)
            
        elif isinstance(exc, IntegrityError):
            data = {
                "status": "error",
                "code": status.HTTP_409_CONFLICT,
                "message": "Database integrity error",
                "errors": str(exc)
            }
            return Response(data, status=status.HTTP_409_CONFLICT)
            
        else:
            data = {
                "status": "error",
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "An unexpected error occurred",
                "errors": str(exc)
            }
            return Response(data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # For pre-handled exceptions, standardize the response format
    error_data = {
        "status": "error",
        "code": response.status_code,
        "message": "Request failed",
        "errors": response.data
    }
    
    response.data = error_data
    return response 