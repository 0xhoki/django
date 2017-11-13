from rest_framework.routers import DefaultRouter

from profiles.api_views import MembershipViewSet

profiles_router = DefaultRouter()
profiles_router.register('profiles/memberships', MembershipViewSet, 'api-profiles-memberships')
