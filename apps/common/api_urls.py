from rest_framework.routers import DefaultRouter

from committees.api_urls import committee_router
from profiles.api_urls import profiles_router
from voting.urls import router as voting_router


class CombineRouter(DefaultRouter):
    def extend(self, router):
        self.registry.extend(router.registry)


combined_router = CombineRouter()
combined_router.extend(profiles_router)
combined_router.extend(voting_router)
combined_router.extend(committee_router)
