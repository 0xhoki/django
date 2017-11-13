import os

ALLOWED_HOSTS = ['127.0.0.1', '54.183.41.1']
DOMAIN = os.environ.get('DOMAIN')
if DOMAIN is not None:
    ALLOWED_HOSTS.insert(0, DOMAIN)


SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = '1036098598697-moc8vrjh5kadbnn165c87jp5gg1d9gsv.apps.googleusercontent.com'
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = 'u9t-RZNQRw8drcr7nUJW3lv3'

SOCIAL_AUTH_LINKEDIN_OAUTH2_KEY = '77yyi62dvjoyde'
SOCIAL_AUTH_LINKEDIN_SECRET = 'igjhZWsVlajjmnt6'

SOCIAL_AUTH_FACEBOOK_KEY = '278462052611210'
SOCIAL_AUTH_FACEBOOK_SECRET = '14690d3decc5f4cea14af6ae9a574b68'

SOCIAL_AUTH_TWITTER_KEY = 'Xcg97q0hcRY8moH4EVls6nSIq'
SOCIAL_AUTH_TWITTER_SECRET = 'aV54Ayh9lwaPSAGoyGnNf3p1G5pzYBvqcWKKo559NTcIcrWQch'

# google calendar (enable calendar api)
GOOGLE_CLIENT_ID = '1036098598697-bkbqigjufqtq7a7hl8a1340fgjtmd14a.apps.googleusercontent.com'
GOOGLE_CLIENT_SECRET = 'OQir9VOx0ohVmNZPLEYalvwV'

# office 365 calendar (add calendars ... on Delegated Permissions)
OFFICE_CLIENT_ID = 'bc549a4b-c8a2-4e17-b780-193cc837c993'
OFFICE_CLIENT_SECRET = 'uSgDUshTeKm55QRArneyn5Y'