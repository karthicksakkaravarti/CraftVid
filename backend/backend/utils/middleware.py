from django.utils.deprecation import MiddlewareMixin
from rest_framework.response import Response


class StandardizedResponseMiddleware(MiddlewareMixin):
    """
    Middleware to standardize successful API responses
    """
    
    def process_response(self, request, response):
        # Only process API responses
        if not request.path.startswith('/api/'):
            return response
            
        # Only process REST framework responses
        if not isinstance(response, Response):
            return response
            
        # Don't modify error responses
        if not 200 <= response.status_code < 300:
            return response
            
        # Standardize the success response
        data = {
            "status": "success",
            "code": response.status_code,
            "message": "Operation successful",
            "data": response.data
        }
        
        # Handle pagination
        if isinstance(response.data, dict) and 'count' in response.data:
            data.update({
                "meta": {
                    "pagination": {
                        "total": response.data.get('count'),
                        "per_page": len(response.data.get('results', [])),
                        "current_page": request.query_params.get('page', 1),
                        "total_pages": (response.data.get('count', 0) + 
                                      len(response.data.get('results', [])) - 1) // 
                                      len(response.data.get('results', [])) 
                                      if response.data.get('results') else 1
                    }
                }
            })
            data['data'] = response.data.get('results', [])
            
        response.data = data
        return response 