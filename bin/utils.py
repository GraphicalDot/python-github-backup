

from urllib.parse import urlparse
from urllib.parse import quote as urlquote
from urllib.parse import urlencode
from urllib.request import Request



def construct_request(per_page, page, template, auth):
    querystring = urlencode(dict(list({
        'per_page': per_page,
        'page': page
    }.items()) 
        #+ list(query_args.items())
    ))

    request = Request(template + '?' + querystring)
    if auth is not None:
        request.add_header('Authorization', 'Basic '.encode('ascii') + auth)
    log_info('Requesting {}?{}'.format(template, querystring))
    return request


def get_response(request, auth, template):
    retry_timeout = 3
    errors = []
    # We'll make requests in a loop so we can
    # delay and retry in the case of rate-limiting
    while True:
        should_continue = False
        try:
            r = urlopen(request)
        except HTTPError as exc:
            errors, should_continue = _request_http_error(exc, auth, errors)  # noqa
            r = exc
        except URLError as e:
            log_warning(e.reason)
            should_continue = _request_url_error(template, retry_timeout)
            if not should_continue:
                raise
        except socket.error as e:
            log_warning(e.strerror)
            should_continue = _request_url_error(template, retry_timeout)
            if not should_continue:
                raise

        if should_continue:
            continue

        break
    return r, errors


def _request_http_error(exc, auth, errors):
    # HTTPError behaves like a Response so we can
    # check the status code and headers to see exactly
    # what failed.

    should_continue = False
    headers = exc.headers
    limit_remaining = int(headers.get('x-ratelimit-remaining', 0))

    if exc.code == 403 and limit_remaining < 1:
        # The X-RateLimit-Reset header includes a
        # timestamp telling us when the limit will reset
        # so we can calculate how long to wait rather
        # than inefficiently polling:
        gm_now = calendar.timegm(time.gmtime())
        reset = int(headers.get('x-ratelimit-reset', 0)) or gm_now
        # We'll never sleep for less than 10 seconds:
        delta = max(10, reset - gm_now)

        limit = headers.get('x-ratelimit-limit')
        print('Exceeded rate limit of {} requests; waiting {} seconds to reset'.format(limit, delta),  # noqa
              file=sys.stderr)

        if auth is None:
            print('Hint: Authenticate to raise your GitHub rate limit',
                  file=sys.stderr)

        time.sleep(delta)
        should_continue = True
    return errors, should_continue


def request_url_error(template, retry_timeout):
    # Incase of a connection timing out, we can retry a few time
    # But we won't crash and not back-up the rest now
    log_info('{} timed out'.format(template))
    retry_timeout -= 1

    if retry_timeout >= 0:
        return True

    log_error('{} timed out to much, skipping!')
    return False