from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed


class CookieTokenAuthentication(TokenAuthentication):
    def authenticate(self, request):
        token_key = request.COOKIES.get('authToken')
        if not token_key:
            return None
        try:
            token = self.get_model().objects.select_related('user').get(key=token_key)
        except self.get_model().DoesNotExist:
            raise AuthenticationFailed('توکن نامعتبر است')
        if not token.user.is_active:
            raise AuthenticationFailed('کاربر غیرفعال است')
        return (token.user, token)