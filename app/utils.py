
#-*- coding: utf-8 -*-
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
import paramiko
import platform
from auth import get_auth
import time
#curl -u "user:pass" --data '{"title":"test-key","key":"'"$(cat ~/.ssh/id_rsa.pub)"'"}' https://api.github.com/user/keys

class GithubIdentity(object):
    """
    Add new ssh keys to login into the github account on ssh
    protocol, if the host is already exists the whole process will 
    abort, The public key will be added automatically to the github
    account and the config file in .ssh directory will be updated 
    with the new private key, The keys generated is rsa 2048
    """

    def __init__(self, hostname, key_name, ssh_dir=None):
        """
        ssh_dir directory for the .ssh configuration and 
        keypairs 
        key_name: This will be reflected in your github account
        username: username for the host
        password: password for the host
        """
        self.hostname = hostname
        self.key_name = key_name
        if not ssh_dir:
            home = os.path.expanduser("~")
            self.ssh_dir = os.path.join(home, ".ssh") 
        else:
            self.ssh_dir = ssh_dir

        ##check if identity for the host already exists or not
        if self.identity_exist():
            raise Exception(f"Identity for {self.hostname} already exists")
        logger.info(f"Identity for {hostname} doesnt exists, Please run add method to generte a new identity")
        self.public_key = os.path.join(self.ssh_dir, "git_pub.key")
        self.private_key = os.path.join(self.ssh_dir, "git_priv.key")

        return 
    
    def identity_exist(self):
        """
        Check if git identity already exists on the user machine, 
        If it does then abort generating new keys and configuring remote github account
        Use Paramiko
        """
        

        conf = paramiko.SSHConfig()
        try:
            with open(os.path.join(self.ssh_dir, "config")) as f:
                conf.parse(f)
        except FileNotFoundError:
            return False

        host_config = conf.lookup(self.hostname)
        logger.info(host_config)

        if not host_config.get("identityfile"):
            return False

        return True

    def add(self, username, password):
        privkey, pubkey = self.generate_new_keys()

        ##uploading the keys to the host
        self.github_upload_keys(pubkey, username, password)
        
        ##writing keys to the local ssh configuration files
        with open(self.private_key, "wb") as content_file:
            content_file.write(privkey)

        command = f"chmod 400 {self.private_key}"
        for res in self.os_command_output(command, f"Setting up permissions for {self.hostname} private key"):
            logger.info(res)

        with open(self.public_key, 'wb') as content_file:
            content_file.write(pubkey)


        self.append_ssh_config()
        self.add_identity()
        return 
    


    def generate_new_keys(self):
        """
        Change this if you want to use any other cryptographic 
        algorithm to generate Asymmetric Key pairs
        """
        logger.info("Generating RSA keys")

        key = RSA.generate(4096)
        privkey = key.exportKey('PEM')
        pubkey = key.publickey().exportKey('OpenSSH')
        return privkey, pubkey 

    def github_upload_keys(self, pubkey, username, password):
        """
        Upload the generated public key on the github
        """
        response = requests.post('https://api.github.com/user/keys', auth=(username, password), data=json.dumps({
                "title": self.key_name, "key": pubkey.decode()
                }))

        res = response.json()
        if response.status_code == 401:
            raise Exception(res.get("message"))
        if response.status_code == 422:
            raise Exception(res.get("message"))

        logger.success(res)
        return 


    def os_command_output(self, command, final_message):

        process = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
        while True:
            line = process.stdout.readline()
            if not line:
                logger.info(final_message)
                break
            yield line.decode().split("\r")[0]
        return 


    def append_ssh_config(self):

        if platform.system() == "Darwin":
            conf_string = f"Host *\n\tAddKeysToAgent yes\n\tUseKeychain yes\n\tIdentityFile  {self.private_key}"
        else:
            conf_string = f"Host github.com\n\tHostname github.com\n\tPreferredAuthentications publickey\n\tIdentityFile  {self.private_key}"
        logger.info(f"String which will be appended to the config file is {conf_string}")
        with open(os.path.join(self.ssh_dir, "config"), "a+") as f:
            f.write(conf_string)
        return 

    def flush_all_identities(self):
        """
        Removes all previous entries from the ssh, if the user already has 
        any identitiy added for github , it will be flushed, please handle it 
        with care 
        """
        command = "ssh-add -D"
        for res in self.os_command_output(command, "New git keys"):
            logger.info(res)

    def add_identity(self):
        """
        """
        if platform.system() == "Darwin":
            command = f"ssh-add -K {self.private_key}"
        else:
            command = f"ssh-add {self.private_key}"
        for res in self.os_command_output(command, "Adding new keys to ssh"):
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
            if os.path.isdir(path):
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

def retrieve_data(username, password, template, query_args=None, single_request=False):
    return list(retrieve_data_gen(username, password, template, query_args, single_request))

def get_query_args(query_args=None):
    if not query_args:
        query_args = {}
    return query_args

def retrieve_data_gen(username, password, template, query_args=None, single_request=False):
    auth = get_auth(username, password)
    query_args = get_query_args(query_args)
    
    logger.info(f"The auth for the user is {auth}")
    per_page = 100
    page = 0

    while True:
        page = page + 1
        request = construct_request(per_page, page, template, auth)  # noqa
        r, errors = get_response(request, auth, template)

        status_code = int(r.getcode())

        retries = 0
        while retries < 3 and status_code == 502:
            print('API request returned HTTP 502: Bad Gateway. Retrying in 5 seconds')
            retries += 1
            time.sleep(5)
            request = construct_request(per_page, page, query_args, template, auth)  # noqa
            r, errors = get_response(request, auth, template)

            status_code = int(r.getcode())

        if status_code != 200:
            template = 'API request returned HTTP {0}: {1}'
            errors.append(template.format(status_code, r.reason))
            logger.error(errors)

        response = json.loads(r.read().decode('utf-8'))
        if len(errors) == 0:
            if type(response) == list:
                for resp in response:
                    yield resp
                if len(response) < per_page:
                    break
            elif type(response) == dict and single_request:
                yield response

        if len(errors) > 0:
            logger.error(errors)

        if single_request:
            break

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


def json_dump(data, output_file):
    json.dump(data,
              output_file,
              ensure_ascii=False,
              sort_keys=True,
              indent=4,
              separators=(',', ': '))