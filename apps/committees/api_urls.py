from rest_framework.routers import DefaultRouter

from committees.api_views import CommitteeViewSet

committee_router = DefaultRouter()
committee_router.register('profiles/committees', CommitteeViewSet, 'api-committees-committees')
