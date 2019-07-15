#!/usr/bin env python

from auth import get_auth,  get_github_api_host
from urllib.request import Request
from utils import construct_request, get_response, ensure_directory
from loguru import logger
import json

def get_authenticated_user(username, password):
    template = 'https://{0}/user'.format(get_github_api_host())
    logger.info (f'THis is the template from authenticated_user {template}')
    data = retrieve_data(username, password, template, single_request=True)
    return data[0]

def retrieve_data(username, password, template, query_args=None, single_request=False):
    return list(retrieve_data_gen(username, password, template, query_args, single_request))

def retrieve_data_gen(username, password, template, query_args=None, single_request=False):
    auth = get_auth(username, password)
    #query_args = get_query_args(query_args)
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
    username = "graphicaldot"
    password = "mitthuparishweta"

    output_dirname = "/Users/kaali/Programs/github-backup/python-github-backup/app/account"
    
    # if args.lfs_clone:
    #     check_git_lfs_install()
    ensure_directory(output_dirname)
    logger.info('Backing up user {0} to {1}'.format(username, output_dirname))

    authenticated_user = get_authenticated_user(username, password)

    print (authenticated_user)
    #repositories = retrieve_repositories(args, authenticated_user)
    # repositories = filter_repositories(args, repositories)
    # backup_repositories(args, output_directory, repositories)
    # backup_account(args, output_directory)

if __name__ == "__main__":
    main()