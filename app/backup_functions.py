

import os
from utils import mkdir_p
from loguru import logger
from utils import retrieve_data, retrieve_data_gen, json_dump
import codecs

def backup_issues(username, password, repo_cwd, repository, repos_template, since=None):
    #has_issues_dir = os.path.isdir('{0}/issues/.git'.format(repo_cwd))
    # if args.skip_existing and has_issues_dir:
    #     return

    logger.info('Retrieving {0} issues'.format(repository['full_name']))
    issue_cwd = os.path.join(repo_cwd, 'issues')
    mkdir_p(repo_cwd, issue_cwd)

    issues = {}
    issues_skipped = 0
    issues_skipped_message = ''
    _issue_template = '{0}/{1}/issues'.format(repos_template,
                                              repository['full_name'])

    should_include_pulls = True
    issue_states = ['open', 'closed']
    for issue_state in issue_states:
        query_args = {
            'filter': 'all',
            'state': issue_state
        }
        ##since os the time stamp after which everything shall be scraped
        if since:
            query_args['since'] = since

        _issues = retrieve_data(username, password,
                                _issue_template,
                                query_args=query_args)
        for issue in _issues:
            # skip pull requests which are also returned as issues
            # if retrieving pull requests is requested as well
            if 'pull_request' in issue:
                issues_skipped += 1
                continue

            issues[issue['number']] = issue

    if issues_skipped:
        issues_skipped_message = ' (skipped {0} pull requests)'.format(
            issues_skipped)

    logger.info('Saving {0} issues to disk{1}'.format(
        len(list(issues.keys())), issues_skipped_message))
    comments_template = _issue_template + '/{0}/comments'
    events_template = _issue_template + '/{0}/events'
    for number, issue in list(issues.items()):
        #if args.include_issue_comments or args.include_everything:
        template = comments_template.format(number)
        issues[number]['comment_data'] = retrieve_data(username, password, template)
        #if args.include_issue_events or args.include_everything:
        template = events_template.format(number)
        issues[number]['event_data'] = retrieve_data(username, password, template)

        issue_file = '{0}/{1}.json'.format(issue_cwd, number)
        with codecs.open(issue_file, 'w', encoding='utf-8') as f:
            json_dump(issue, f)
    return

def backup_pulls(username, password, repo_cwd, repository, repos_template):
    
    #has_pulls_dir = os.path.isdir('{0}/pulls/.git'.format(repo_cwd))
    # if args.skip_existing and has_pulls_dir:
    #     return

    logger.info(f"Retrieving {repository['full_name']} pull requests")  # noqa
    pulls_cwd = os.path.join(repo_cwd, 'pulls')
    mkdir_p(repo_cwd, pulls_cwd)

    pulls = {}
    pulls_template = f"{repos_template}/{repository['full_name']}/pulls"

    logger.info(f"Pull template is {pulls_template}")
    query_args = {
        'filter': 'all',
        'state': 'all',
        'sort': 'updated',
        'direction': 'desc',
    }

    # if not args.include_pull_details:
    #     pull_states = ['open', 'closed']
    #     for pull_state in pull_states:
    #         query_args['state'] = pull_state
    #         _pulls = retrieve_data_gen(args,
    #                                _pulls_template,
    #                                query_args=query_args)
    #         for pull in _pulls:
    #             if args.since and pull['updated_at'] < args.since:
    #                 break
    #             if not args.since or pull['updated_at'] >= args.since:
    #                 pulls[pull['number']] = pull
    # else:
    _pulls = retrieve_data_gen(username, password, 
                            pulls_template,
                            query_args=query_args)

    for pull in _pulls:
        # if args.since and pull['updated_at'] < args.since:
        #     break
        # if not args.since or pull['updated_at'] >= args.since:
             pulls[pull['number']] = retrieve_data(
                username, password,
                pulls_template + '/{}'.format(pull['number']),
                single_request=True
            )[0]

    logger.info('Saving {0} pull requests to disk'.format(
        len(list(pulls.keys()))))
    
    comments_template = pulls_template + '/{0}/comments'
    commits_template = pulls_template + '/{0}/commits'
    
    for number, pull in list(pulls.items()):
            # if args.include_pull_comments or args.include_everything:
            template = comments_template.format(number)
            pulls[number]['comment_data'] = retrieve_data(username, password, template)
            #if args.include_pull_commits or args.include_everything:
            template = commits_template.format(number)
            pulls[number]['commit_data'] = retrieve_data(username, password, template)

            pull_file = '{0}/{1}.json'.format(pulls_cwd, number)
            with codecs.open(pull_file, 'w', encoding='utf-8') as f:
                json_dump(pull, f)


def backup_milestones(args, repo_cwd, repository, repos_template):
    milestone_cwd = os.path.join(repo_cwd, 'milestones')
    if args.skip_existing and os.path.isdir(milestone_cwd):
        return

    log_info('Retrieving {0} milestones'.format(repository['full_name']))
    mkdir_p(repo_cwd, milestone_cwd)

    template = '{0}/{1}/milestones'.format(repos_template,
                                           repository['full_name'])

    query_args = {
        'state': 'all'
    }

    _milestones = retrieve_data(args, template, query_args=query_args)

    milestones = {}
    for milestone in _milestones:
        milestones[milestone['number']] = milestone

    log_info('Saving {0} milestones to disk'.format(
        len(list(milestones.keys()))))
    for number, milestone in list(milestones.items()):
        milestone_file = '{0}/{1}.json'.format(milestone_cwd, number)
        with codecs.open(milestone_file, 'w', encoding='utf-8') as f:
            json_dump(milestone, f)


def backup_labels(args, repo_cwd, repository, repos_template):
    label_cwd = os.path.join(repo_cwd, 'labels')
    output_file = '{0}/labels.json'.format(label_cwd)
    template = '{0}/{1}/labels'.format(repos_template,
                                       repository['full_name'])
    _backup_data(args,
                 'labels',
                 template,
                 output_file,
                 label_cwd)


def backup_hooks(args, repo_cwd, repository, repos_template):
    auth = get_auth(args)
    if not auth:
        log_info("Skipping hooks since no authentication provided")
        return
    hook_cwd = os.path.join(repo_cwd, 'hooks')
    output_file = '{0}/hooks.json'.format(hook_cwd)
    template = '{0}/{1}/hooks'.format(repos_template,
                                      repository['full_name'])
    try:
        _backup_data(args,
                     'hooks',
                     template,
                     output_file,
                     hook_cwd)
    except SystemExit:
        log_info("Unable to read hooks, skipping")


def backup_releases(args, repo_cwd, repository, repos_template, include_assets=False):
    repository_fullname = repository['full_name']

    # give release files somewhere to live & log intent
    release_cwd = os.path.join(repo_cwd, 'releases')
    log_info('Retrieving {0} releases'.format(repository_fullname))
    mkdir_p(repo_cwd, release_cwd)

    query_args = {}

    release_template = '{0}/{1}/releases'.format(repos_template, repository_fullname)
    releases = retrieve_data(args, release_template, query_args=query_args)

    # for each release, store it
    log_info('Saving {0} releases to disk'.format(len(releases)))
    for release in releases:
        release_name = release['tag_name']
        output_filepath = os.path.join(release_cwd, '{0}.json'.format(release_name))
        with codecs.open(output_filepath, 'w+', encoding='utf-8') as f:
            json_dump(release, f)

        if include_assets:
            assets = retrieve_data(args, release['assets_url'])
            for asset in assets:
                download_file(asset['url'], os.path.join(release_cwd, asset['name']), get_auth(args))



def backup_account(args, output_directory):
    account_cwd = os.path.join(output_directory, 'account')

    if args.include_starred or args.include_everything:
        output_file = "{0}/starred.json".format(account_cwd)
        template = "https://{0}/users/{1}/starred".format(get_github_api_host(args), args.user)
        _backup_data(args,
                     "starred repositories",
                     template,
                     output_file,
                     account_cwd)

    if args.include_watched or args.include_everything:
        output_file = "{0}/watched.json".format(account_cwd)
        template = "https://{0}/users/{1}/subscriptions".format(get_github_api_host(args), args.user)
        _backup_data(args,
                     "watched repositories",
                     template,
                     output_file,
                     account_cwd)

    if args.include_followers or args.include_everything:
        output_file = "{0}/followers.json".format(account_cwd)
        template = "https://{0}/users/{1}/followers".format(get_github_api_host(args), args.user)
        _backup_data(args,
                     "followers",
                     template,
                     output_file,
                     account_cwd)

    if args.include_following or args.include_everything:
        output_file = "{0}/following.json".format(account_cwd)
        template = "https://{0}/users/{1}/following".format(get_github_api_host(args), args.user)
        _backup_data(args,
                     "following",
                     template,
                     output_file,
                     account_cwd)


def _backup_data(args, name, template, output_file, output_directory):
    skip_existing = args.skip_existing
    if not skip_existing or not os.path.exists(output_file):
        log_info('Retrieving {0} {1}'.format(args.user, name))
        mkdir_p(output_directory)
        data = retrieve_data(args, template)

        log_info('Writing {0} {1} to disk'.format(len(data), name))
        with codecs.open(output_file, 'w', encoding='utf-8') as f:
            json_dump(data, f)