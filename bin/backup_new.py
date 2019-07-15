#!/usr/bin env python

from auth import get_auth,  get_github_api_host
from urllib.request import Request
from utils import construct_request, get_response

def mkdir_p(*args):
    for path in args:
        try:
            os.makedirs(path)
        except OSError as exc:  # Python >2.5
            if exc.errno == errno.EEXIST and os.path.isdir(path):
                pass
            else:
                raise

def get_authenticated_user():
    template = 'https://{0}/user'.format(get_github_api_host())
    print (f'THis is the template from authenticated_user {template}')
    data = retrieve_data(template, single_request=True)
    return data[0]

def retrieve_data(args, template, query_args=None, single_request=False):
    return list(retrieve_data_gen(args, template, query_args, single_request))

def retrieve_data_gen(username, password, template, query_args=None, single_request=False):
    auth = get_auth(username, password)
    #query_args = get_query_args(query_args)
    per_page = 100
    page = 0

    while True:
        page = page + 1
        request = construct_request(per_page, page, query_args, template, auth)  # noqa
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
            log_error(errors)

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
            log_error(errors)

        if single_request:
            break






def main():
    print ("Execution started")
    output_directory = "."
    user_name = "graphicaldot"
    password = "mitthuparishweta"
    output_directory = os.path.realpath(output_directory)
    if not os.path.isdir(output_directory):
        log_info('Create output directory {0}'.format(output_directory))
        mkdir_p(output_directory)

    # if args.lfs_clone:
    #     check_git_lfs_install()

    log_info('Backing up user {0} to {1}'.format(args.user, output_directory))

    authenticated_user = get_authenticated_user(args)

    print (authnticated_user)
    #repositories = retrieve_repositories(args, authenticated_user)
    # repositories = filter_repositories(args, repositories)
    # backup_repositories(args, output_directory, repositories)
    # backup_account(args, output_directory)