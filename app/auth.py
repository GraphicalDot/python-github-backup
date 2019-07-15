
from urllib.parse import urlparse
from urllib.parse import quote as urlquote
from urllib.parse import urlencode
import base64


def mask_password(url, secret='*****'):
    parsed = urlparse(url)

    if not parsed.password:
        return url
    elif parsed.password == 'x-oauth-basic':
        return url.replace(parsed.username, secret)

    return url.replace(parsed.password, secret)



def get_github_api_host():
    host = 'api.github.com'
    return host





def get_auth(username, password, encode=True):
    """
    Based on the username and password for the github, This will generate 
    a basic_auth token for github authentication, which will be a base64 encoded 
    string of username and password.
    """
    if username:
        if not password:
            raise Exception("Passsword is required for github")
            password = urlquote(args.password)
        auth = username + ':' + password
    else:
        log_error('You must specify a username for basic auth')

    if not auth:
        return None

    if not encode:
        return auth

    basic_auth = base64.b64encode(auth.encode('ascii'))
    return basic_auth
