

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
import subprocess
from Crypto.PublicKey import RSA
import requests

#curl -u "user:pass" --data '{"title":"test-key","key":"'"$(cat ~/.ssh/id_rsa.pub)"'"}' https://api.github.com/user/keys

def os_command_output(command, final_message):

    process = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
    while True:
        line = process.stdout.readline()
        if not line:
            logger.info(final_message)
            break
        yield line.decode().split("\r")[0]
    return 


def generate_new_keys():
    key = RSA.generate(4096)
    #ssh-keygen -t rsa -C "your_email@example.com"
    home = os.path.expanduser("~")
    ssh_path = os.path.join(home, ".ssh")
    public_key_path = os.path.join(ssh_path, "git_public.key")
    private_key_path = os.path.join(ssh_path, "git_private.key")
    if not os.path.exists(private_key_path):
    
        with open(private_key_path, "wb") as content_file:
            content_file.write(key.exportKey('PEM'))
        
        pubkey = key.publickey()
        with open(public_key_path, 'wb') as content_file:
            content_file.write(pubkey.exportKey('OpenSSH'))

        username = "graphicaldot"
        password = "Groot1234#"
        public_bytes = pubkey.exportKey('OpenSSH').decode()
        response = requests.post('https://api.github.com/user/keys', auth=(username, password), data=json.dumps({
                "title": "Datapod", "key": public_bytes
                }))

        
        logger.info(response.json())

    command = "ssh -T git@github.com"
    for res in os_command_output(command, "New git keys"):
        logger.info(res)
    return 



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
    logger.info(f"parsed {parsed}")

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



class S3HTTPRedirectHandler(HTTPRedirectHandler):
    """
    A subclassed redirect handler for downloading Github assets from S3.

    urllib will add the Authorization header to the redirected request to S3, which will result in a 400,
    so we should remove said header on redirect.
    """
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if PY2:
            # HTTPRedirectHandler is an old style class
            request = HTTPRedirectHandler.redirect_request(self, req, fp, code, msg, headers, newurl)
        else:
            request = super(S3HTTPRedirectHandler, self).redirect_request(req, fp, code, msg, headers, newurl)
        del request.headers['Authorization']
        return request


def download_file(url, path, auth):
    request = Request(url)
    request.add_header('Accept', 'application/octet-stream')
    request.add_header('Authorization', 'Basic '.encode('ascii') + auth)
    opener = build_opener(S3HTTPRedirectHandler)
    response = opener.open(request)

    chunk_size = 16 * 1024
    with open(path, 'wb') as f:
        while True:
            chunk = response.read(chunk_size)
            if not chunk:
                break
            f.write(chunk)


def check_git_lfs_install():
    exit_code = subprocess.call(['git', 'lfs', 'version'])
    if exit_code != 0:
        log_error('The argument --lfs requires you to have Git LFS installed.\nYou can get it from https://git-lfs.github.com.')