# backend/middleware/disable_csrf.py
"""
DEV ONLY: middleware to disable CSRF checks for API paths.

This sets request._dont_enforce_csrf_checks = True for requests whose
path starts with '/api/'. It must be placed *before* Django's
CsrfViewMiddleware in MIDDLEWARE so it takes effect.
"""

from django.utils.deprecation import MiddlewareMixin

class DisableCSRFMiddleware(MiddlewareMixin):
    def process_request(self, request):
        try:
            path = request.path or ""
        except Exception:
            path = ""
        # adjust prefix if your API root differs (e.g. /api/v1/)
        if path.startswith("/api/"):
            # short-circuit CSRF enforcement for API paths
            setattr(request, "_dont_enforce_csrf_checks", True)
        # return None to continue normal processing
        return None
