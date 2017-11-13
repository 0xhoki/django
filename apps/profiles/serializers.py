from rest_framework import serializers

from profiles.models import Membership


class MembershipShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membership
        fields = ['id', 'first_name', 'last_name', 'bio', 'is_guest', 'avatar_url']
