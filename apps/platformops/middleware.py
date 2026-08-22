from django.http import JsonResponse
from cPlatform.AppLogging import app_logger

class WrongURLMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        print(f"response.status_code={response.status_code}")
        if response.status_code == 404:
            current_url = request.build_absolute_uri()
            app_logger.debug(f"Received request at WrongURL={current_url}")
            # Log or take action on incorrect URL hits here
            print(f"response={response}")
            return JsonResponse(status=404, data={'message': 'Invalid URL'})
        else:
         return self.get_response(request)



from django.utils.deprecation import MiddlewareMixin

class NoCacheMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        if request.user.is_authenticated:
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
        return response
