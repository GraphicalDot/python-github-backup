

from urllib.parse import urlparse
from urllib.parse import quote as urlquote
from urllib.parse import urlencode
from urllib.request import Request
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from urllib.request import Request
from urllib.request import HTTPRedirectHandler
from urllib.request import build_opener
import socket
import os
import json
from loguru import logger
from errors import request_http_error, request_url_error
import subprocess
import sys
import select


def logging_subprocess(popenargs,
                       logger,
                       stdout_log_level=logger.debug,
                       stderr_log_level=logger.error,
                       **kwargs):
    """
    Variant of subprocess.call that accepts a logger instead of stdout/stderr,
    and logs stdout messages via logger.debug and stderr messages via
    logger.error.
    """
    child = subprocess.Popen(popenargs, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, **kwargs)
    if sys.platform == 'win32':
        log_info("Windows operating system detected - no subprocess logging will be returned")

    log_level = {child.stdout: stdout_log_level,
                 child.stderr: stderr_log_level}

    def check_io():
        if sys.platform == 'win32':
            return
        ready_to_read = select.select([child.stdout, child.stderr],
                                      [],
                                      [],
                                      1000)[0]
        for io in ready_to_read:
            line = io.readline()
            if not logger:
                continue
            if not (io == child.stderr and not line):
                logger.log(log_level[io], line[:-1])

    # keep checking stdout/stderr until the child exits
    while child.poll() is None:
        check_io()

    check_io()  # check again to catch anything after the process exits

    rc = child.wait()

    if rc != 0:
        print ('{} returned {}:'.format(popenargs[0], rc), file=sys.stderr)
        print('\t', ' '.join(popenargs), file=sys.stderr)

    return rc


def mask_password(url, secret='*****'):
    parsed = urlparse(url)

    if not parsed.password:
        return url
    elif parsed.password == 'x-oauth-basic':
        return url.replace(parsed.username, secret)

    return url.replace(parsed.password, secret)


def mkdir_p(*args):
    for path in args:
        try:
            os.makedirs(path)
        except OSError as exc:  # Python >2.5
            if exc.errno == errno.EEXIST and os.path.isdir(path):
                pass
            else:
                raise


def ensure_directory(dirname):
    output_directory = os.path.realpath(dirname)
    if not os.path.isdir(output_directory):
        logger.debug('Create output directory {0}'.format(dirname))

        mkdir_p(output_directory)
    return
    # if args.lfs_clone:
    #     check_git_lfs_install()



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
    logger.info('Requesting {}?{}'.format(template, querystring))
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
            errors, should_continue = request_http_error(exc, auth, errors)  # noqa
            r = exc
        except URLError as e:
            logger.warning(e.reason)
            should_continue = request_url_error(template, retry_timeout)
            if not should_continue:
                raise
        except socket.error as e:
            logger.warning(e.strerror)
            should_continue = request_url_error(template, retry_timeout)
            if not should_continue:
                raise

        if should_continue:
            continue

        break
    return r, errors


def c_pretty_print(data):
    p = json.dumps(data, indent=4, sort_keys=True)
    logger.info(p)