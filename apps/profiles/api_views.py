from rest_framework import viewsets

from common.mixins import LoginRequiredMixin, GetMembershipMixin
from common.utils import AlmostNoPagination
from permissions.rest_permissions import IsAccountAdminOrReadOnly, CheckAccountUrl
from profiles.models import Membership
from profiles.serializers import MembershipShortSerializer


class MembershipViewSet(viewsets.ReadOnlyModelViewSet, LoginRequiredMixin, GetMembershipMixin):
    serializer_class = MembershipShortSerializer
    permission_classes = [IsAccountAdminOrReadOnly, CheckAccountUrl]
    pagination_class = AlmostNoPagination

    def get_queryset(self):
        return Membership.objects.filter(account=self.get_current_account(), is_active=True)
