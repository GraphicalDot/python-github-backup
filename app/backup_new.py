#!/usr/bin env python
import os
import sys
from auth import get_auth,  get_github_api_host
from urllib.request import Request
from utils import construct_request, get_response, ensure_directory, \
        c_pretty_print, mask_password, logging_subprocess,  GithubIdentity,\
             retrieve_data, retrieve_data_gen

from backup_functions import  backup_issues, backup_pulls

import time 
from loguru import logger
from pprint import pformat
import json
import subprocess
__version__ = "3.9.9"
FNULL = open(os.devnull, 'w')



def get_authenticated_user(username, password):
    template = 'https://{0}/user'.format(get_github_api_host())
    logger.info (f'THis is the template from authenticated_user {template}')
    data = retrieve_data(username, password, template, single_request=True)
    return data[0]





def retrieve_repositories(username, password):
    single_request = False

    template = 'https://{0}/user/repos'.format(get_github_api_host())
        
    # print (f"Template for retrieve_repos is {template}")
    # else:
        # if args.private and not args.organization:
    #         log_warning('Authenticated user is different from user being backed up, thus private repositories cannot be accessed')
    #     template = 'https://{0}/users/{1}/repos'.format(
    #         get_github_api_host(args),
    #         args.user)

    # if args.organization:
    # orgnization_repos_template = 'https://{0}/orgs/{1}/repos'.format(
    #         get_github_api_host(args),
    #         args.user)

    ##If you want to fetch only one repository
    # repository_template = 'https://{0}/repos/{1}/{2}'.format(
    #         get_github_api_host(args),
    #         args.user,
    #         args.repository)

    repos = retrieve_data(username, password, template, single_request=single_request)

    #c_pretty_print(repos[0])
    ##append start repos 
    starred_template = 'https://{0}/users/{1}/starred'.format(get_github_api_host(), username)
    starred_repos = retrieve_data(username, password, starred_template, single_request=False)
    # flag each repo as starred for downstream processing
    for item in starred_repos:
        item.update({'is_starred': True})
    
    logger.info("Starred Repos first element")
    #c_pretty_print(starred_repos[0])

    ##append start repos 
    repos.extend(starred_repos)


    ###appemd gists
    gists_template = 'https://{0}/users/{1}/gists'.format(get_github_api_host(), username)
    gists = retrieve_data(username, password, gists_template, single_request=False)
    # flag each repo as a gist for downstream processing
    for item in gists:
        item.update({'is_gist': True})

    logger.info("GIST first element")
    #c_pretty_print(gists[0])
    repos.extend(gists)


    ##append star gists by the user
    starred_gists_template = 'https://{0}/gists/starred'.format(get_github_api_host())
    starred_gists = retrieve_data(username, password, starred_gists_template, single_request=False)
    # flag each repo as a starred gist for downstream processing
    for item in starred_gists:
        item.update({'is_gist': True,
                        'is_starred': True})
    repos.extend(starred_gists)



    return repos

def get_github_host():
    ##TODO include gitgub host too
    # if args.github_host:
    #     host = args.github_host
    # else:
    #     host = 'github.com'
    
    host = 'github.com'
    return host

def get_github_repo_url(username, password, repository, prefer_ssh=True):
    # if args.prefer_ssh:
    #     return repository['ssh_url']
    if repository.get('is_gist'):
        return repository['git_pull_url']
    
    if prefer_ssh:
        return repository['ssh_url']

    


    ##if its a private url
    auth = get_auth(username, password, False)
    if auth:
        logger.info(f"Auth is prsent {auth}")
        repo_url = 'https://{0}@{1}/{2}/{3}.git'.format(
            auth,
            get_github_host(),
            repository['owner']['login'],
            repository['name'])
    else:
        repo_url = repository['clone_url']

    return repo_url

def backup_repositories(username, password, output_directory, repositories):
    logger.info('Backing up repositories')
    repos_template = 'https://{0}/repos'.format(get_github_api_host())

    #if args.incremental:
    last_update = max(list(repository['updated_at'] for repository in repositories) or [time.strftime('%Y-%m-%dT%H:%M:%SZ', time.localtime())])  # noqa
    last_update_path = os.path.join(output_directory, 'last_update')
    if os.path.exists(last_update_path):
        since = open(last_update_path).read().strip()
    else:
        since = None

    logger.info(last_update)

    logger.info(f"Since value is {last_update}")
    logger.info(f"Lat update path  is {last_update_path}")

    for repository in repositories:
        time.sleep(5)
        if repository.get('is_gist'):
            repo_cwd = os.path.join(output_directory, 'gists', repository['id'])
        elif repository.get('is_starred'):
            # put starred repos in -o/starred/${owner}/${repo} to prevent collision of
            # any repositories with the same name
            repo_cwd = os.path.join(output_directory, 'starred', repository['owner']['login'], repository['name'])
        else:
            repo_cwd = os.path.join(output_directory, 'repositories', repository['name'])

        repo_dir = os.path.join(repo_cwd, 'repository')
        repo_url = get_github_repo_url(username, password, repository)
        #ensure_directory(repo_dir)

        masked_remote_url = mask_password(repo_url)

        logger.info(f"The masked_repo url on the github is {masked_remote_url} and is Private: {repository['private']}")
        
    #     #include_gists = (args.include_gists or args.include_starred_gists)
    #     #if (args.include_repository or args.include_everything) \
    #     #       or (include_gists and repository.get('is_gist')):
        repo_name = repository.get('name') if not repository.get('is_gist') else repository.get('id')
            
        fetch_repository(repo_name, repo_url, repo_dir)
        if repository.get('is_gist'):
            # dump gist information to a file as well
            output_file = '{0}/gist.json'.format(repo_cwd)
            with codecs.open(output_file, 'w', encoding='utf-8') as f:
                json_dump(repository, f)

            continue  # don't try to back anything else for a gist; it doesn't exis


        #download_wiki = (args.include_wiki or args.include_everything)
        
        if repository['has_wiki']:
            wiki_url = repo_url.replace('.git', '.wiki.git')
            logger.info(f"Trying to download wiki for {repository['name']} at {wiki_url}")

            fetch_repository(repository['name'],
                             wiki_url,
                             os.path.join(repo_cwd, 'wiki'),
                            )


        if repository.get('is_starred'):
            continue
        #if args.include_issues or args.include_everything:
        backup_issues(username, password, repo_cwd, repository, repos_template)

        # if args.include_pulls or args.include_everything:
        backup_pulls(username, password, repo_cwd, repository, repos_template)

        # if args.include_milestones or args.include_everything:
        #     backup_milestones(args, repo_cwd, repository, repos_template)

        # if args.include_labels or args.include_everything:
        #     backup_labels(args, repo_cwd, repository, repos_template)

        # if args.include_hooks or args.include_everything:
        #     backup_hooks(args, repo_cwd, repository, repos_template)

        # if args.include_releases or args.include_everything:
        #     backup_releases(args, repo_cwd, repository, repos_template,
        #                     include_assets=args.include_assets or args.include_everything)

    if args.incremental:
        open(last_update_path, 'w').write(last_update)





def fetch_repository(name,
                     remote_url,
                     local_dir,
                     skip_existing=False,
                     bare_clone=True,
                     lfs_clone=False):
    if bare_clone:
        if os.path.exists(local_dir):
            clone_exists = subprocess.check_output(['git',
                                                    'rev-parse',
                                                    '--is-bare-repository'],
                                                   cwd=local_dir) == b"true\n"
        else:
            clone_exists = False
    else:
        clone_exists = os.path.exists(os.path.join(local_dir, '.git'))

    if clone_exists and skip_existing:
        return

    masked_remote_url = mask_password(remote_url)

    initialized = subprocess.call('git ls-remote ' + remote_url,
                                  stdout=FNULL,
                                  stderr=FNULL,
                                  shell=True)
    if initialized == 128:
        logger.error("Skipping {0} ({1}) since it's not initialized".format(
            name, masked_remote_url))
        return

    if clone_exists:
        logger.info('Updating {0} in {1}'.format(name, local_dir))

        remotes = subprocess.check_output(['git', 'remote', 'show'],
                                          cwd=local_dir)
        logger.info(remotes)
        remotes = [i.strip() for i in remotes.decode('utf-8').splitlines()]

        if 'origin' not in remotes:
            git_command = ['git', 'remote', 'rm', 'origin']
            logging_subprocess(git_command, None, cwd=local_dir)
            git_command = ['git', 'remote', 'add', 'origin', remote_url]
            logging_subprocess(git_command, None, cwd=local_dir)
        else:
            git_command = ['git', 'remote', 'set-url', 'origin', remote_url]
            logging_subprocess(git_command, None, cwd=local_dir)

        if lfs_clone:
            git_command = ['git', 'lfs', 'fetch', '--all', '--force', '--tags', '--prune']
        else:
            git_command = ['git', 'fetch', '--all', '--force', '--tags', '--prune']
        logging_subprocess(git_command, None, cwd=local_dir)
    else:
        logger.info('Cloning {0} repository from {1} to {2}'.format(
            name,
            masked_remote_url,
            local_dir))
        if bare_clone:
            if lfs_clone:
                git_command = ['git', 'lfs', 'clone', '--mirror', remote_url, local_dir]
            else:
                git_command = ['git', 'clone', '--mirror', remote_url, local_dir]
        else:
            if lfs_clone:
                git_command = ['git', 'lfs', 'clone', remote_url, local_dir]
            else:
                git_command = ['git', 'clone', remote_url, local_dir]
        logging_subprocess(git_command, None)















def main():
    from config import config_object
    try:
        username = sys.argv[1]
        password = sys.argv[2]
        logger.info(f"USERNAME=={username} and PASSWORD == {password}")
    except :
        logger.error("Please provide username and password for your github") 
    print ("Execution started")
    
    try:
        inst = GithubIdentity("github.com", "Macpod")
        inst.add(username, password)

    except Exception as e:
       logger.error(e)

    
    #generate_new_keys(username, password)
    # dirname = os.path.dirname(os.path.abspath(__file__))
    # output_directory = os.path.join(dirname, "account") 
    # if args.lfs_clone:
    #     check_git_lfs_install()
    logger.info('Backing up user {0} to {1}'.format(username, config_object.GITHUB_OUTPUT_DIR))

    ensure_directory(config_object.GITHUB_OUTPUT_DIR)

    authenticated_user = get_authenticated_user(username, password)

    logger.info(f"The user for which the backup will happend {authenticated_user['login']}")
    repositories = retrieve_repositories(username, password)
    #repositories = filter_repositories(args, repositories)
    backup_repositories(username, password, config_object.GITHUB_OUTPUT_DIR, repositories)
    # # backup_account(args, output_directory)
    
if __name__ == "__main__":
    main()