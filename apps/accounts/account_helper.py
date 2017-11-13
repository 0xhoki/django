def set_current_account(request, account):
    request.session['current_account_id'] = account.id
    request.current_account = account


def get_current_account(request):
    if not hasattr(request, 'current_account'):
        if 'current_account_id' in request.session:
            # To remove circular dependency
            from accounts.models import Account

            request.current_account = Account.objects.get(pk=request.session['current_account_id'])
        else:
            request.current_account = None

    return request.current_account


def set_current_account_temp(request, account):
    """Just sets cached value but no session storage"""
    request.current_account = account


def clear_current_account(request):
    if hasattr(request, 'current_account'):
        del request.current_account

    del request.session['current_account_id']
