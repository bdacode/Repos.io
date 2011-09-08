from copy import copy

from github2.client import Github
from github2.users import User
from github2.request import HttpError

from django.conf import settings

from core.backends import BaseBackend, README_NAMES, README_TYPES

class GithubBackend(BaseBackend):

    name = 'github'
    auth_backend = 'github'
    needed_repository_identifiers = ('slug', 'official_owner',)
    support = copy(BaseBackend.support)
    support.update(dict(
        user_followers = True,
        user_following = True,
        user_repositories = True,
        repository_owner = True,
        repository_parent_fork = True,
        repository_followers = True,
        repository_contributors = True,
        repository_readme = True,
    ))

    def __init__(self, *args, **kwargs):
        """
        Create an empty dict to cache Github instances
        """
        super(GithubBackend, self).__init__(*args, **kwargs)
        self._github_instances = {}

    @classmethod
    def enabled(cls):
        """
        Return backend enabled status by checking basic settings
        """
        return all(hasattr(settings, name) for name in ('GITHUB_APP_ID', 'GITHUB_API_SECRET'))

    def _get_exception(self, exception, what, access_token=None):
        """
        Return an internal exception (BackendError)
        """
        if isinstance(exception, HttpError):
            return self.get_exception(exception.code, what)
        else:
            return self.get_exception(None, what)

    def create_github_instance(self, *args, **kwargs):
        """
        Create a Github instance from the given parameters.
        Add, if not provided, the `requests_per_second` and `cache` ones.
        """
        kwargs.setdefault('requests_per_second', 1)
        # for debugging, only if set
        if getattr(settings, 'GITHUB_CACHE_DIR', None):
            kwargs.setdefault('cache', settings.GITHUB_CACHE_DIR)
        return Github(*args, **kwargs)

    def github(self, access_token=None):
        """
        Return (and if not exists create and cache) a Github instance
        authenticated for the given access_token, or an anonymous one if
        there is no access_token
        """
        access_token = access_token or None
        if access_token not in self._github_instances:
            self._github_instances[access_token] = self.create_github_instance(access_token=access_token)
        return self._github_instances[access_token]

    def user_fetch(self, account, access_token=None):
        """
        Fetch the account from the provider and update the object
        """
        # get/create the github instance
        github = self.github(access_token)

        # get user data fromgithub
        try:
            guser = github.users.show(account.slug)
        except Exception, e:
            raise self._get_exception(e, '%s' % account.slug)

        # associate github user and account
        rmap = self.user_map(guser)
        for key, value in rmap.items():
            setattr(account, key, value)

    def user_map(self, user):
        """
        Map the given user, which is an object (or dict)
        got from the backend, to a dict usable for creating/updating
        an Account core object
        # in this backend, we attend User objects only
        """
        simple_mapping = dict(
            slug = 'login',
            name = 'name',
            homepage = 'blog',
            avatar = 'avatar_url',
            official_created = 'created_at',
            official_followers_count = 'followers_count',
            official_following_count = 'following_count',
        )

        result = {}

        for internal_key, backend_key in simple_mapping.items():
            value = getattr(user, backend_key, None)
            if value is not None:
                result[internal_key] = value

        if 'avatar' not in result and getattr(user, 'gravatar_id', None):
                result['avatar'] = 'http://www.gravatar.com/avatar/%s' % user.gravatar_id

        result['url'] = 'https://github.com/%s/' % user.login

        return result


    def user_following(self, account, access_token=None):
        """
        Fetch the accounts followed by the given one
        """
        # get/create the github instance
        github = self.github(access_token)

        # get users data from github
        try:
            gusers = github.users.following(account.slug)
        except Exception, e:
            raise self._get_exception(e, '%s\'s following' % account.slug)

        result = []

        for guser in gusers:
            result.append(self.user_map(User(login=guser)))

        return result

    def user_followers(self, account, access_token=None):
        """
        Fetch the accounts following the given one
        """
        # get/create the github instance
        github = self.github(access_token)

        # get users data from github
        try:
            gusers = github.users.followers(account.slug)
        except Exception, e:
            raise self._get_exception(e, '%s\'s followers' % account.slug)

        result = []

        # make a dict for each
        for guser in gusers:
            result.append(self.user_map(User(login=guser)))

        return result

    def user_repositories(self, account, access_token=None):
        """
        Fetch the repositories owned/watched by the given accont
        """
        # get/create the github instance
        github = self.github(access_token)

        # get repositories data from github
        try:
            grepos = github.repos.watching(account.slug)
        except Exception, e:
            raise self._get_exception(e, '%s\'s repositories' % account.slug)

        result = []

        # make a dict for each
        for grepo in grepos:
            result.append(self.repository_map(grepo))

        return result

    def repository_project(self, repository):
        """
        Return a project name the provider can use
        """
        if repository.owner_id:
            owner = repository.owner.slug
        else:
            owner = repository.official_owner
        return self.github().project_for_user_repo(owner, repository.slug)

    def parse_project(self, project):
        """
        Try to get at least a slug, and if the backend can, a user
        by using the given project name
        """
        owner,  name = project.split('/')
        return dict(slug = name, official_owner = owner)

    def repository_fetch(self, repository, access_token=None):
        """
        Fetch the repository from the provider and update the object
        """
        # get/create the github instance
        github = self.github(access_token)

        # get repository data fromgithub
        project = repository.get_project()
        try:
            grepo = github.repos.show(project)
        except Exception, e:
            raise self._get_exception(e, '%s' % repository.project)

        # associate github repo to core one
        rmap = self.repository_map(grepo)
        for key, value in rmap.items():
            setattr(repository, key, value)

    def repository_map(self, repository):
        """
        Map the given repository, which is an object (or dict)
        got from the backend, to a dict usable for creating/updating
        a Repository core object
        # in this backend, we attend Repository objects only
        """

        simple_mapping = dict(
            slug = 'name',
            name = 'name',
            url = 'url',
            description = 'description',
            homepage = 'homepage',
            official_owner = 'owner',
            official_forks_count = 'forks',
            official_fork_of = 'parent',
            official_followers_count = 'watchers',
            is_fork = 'fork',
            private = 'private',
            official_created = 'created_at',
            official_modified = 'pushed_at',
            default_branch = 'master_branch',
        )

        result = {}


        for internal_key, backend_key in simple_mapping.items():
            value = getattr(repository, backend_key, None)
            if value is not None:
                result[internal_key] = value

        return result

    def repository_followers(self, repository, access_token=None):
        """
        Fetch the accounts following the given repository
        """
        # get/create the github instance
        github = self.github(access_token)

        # get users data from github
        try:
            gusers = github.repos.watchers(repository.project)
        except Exception, e:
            raise self._get_exception(e, '%s\'s followers' % repository.project)

        result = []

        # make a dict for each
        for guser in gusers:
            result.append(self.user_map(User(login=guser)))

        return result

    def repository_contributors(self, repository, access_token=None):
        """
        Fetch the accounts contributing the given repository
        For each account (dict) returned, the number of contributions is stored
        in ['__extra__']['contributions']
        """
        # get/create the github instance
        github = self.github(access_token)

        # get users data from github
        try:
            gusers = github.repos.list_contributors(repository.project)
        except Exception, e:
            raise self._get_exception(e, '%s\'s contributors' % repository.project)

        result = []

        # make a dict for each
        for guser in gusers:
            if guser != 'invalid-email-address':
                account_dict = self.user_map(guser)
                # TODO : nb of contributions not used yet but later...
                account_dict.setdefault('__extra__', {})['contributions'] = guser.contributions
                result.append(account_dict)

        return result

    def repository_readme(self, repository, access_token=None):
        """
        Try to get a readme in the repository
        """
        # get/create the github instance
        github = self.github(access_token)

        # try with each name
        commits = None
        for name in README_NAMES:
            # we start by getting the last commit id for a file starting with this name
            try:
                commits = github.commits.list(
                    project = repository.project,
                    branch = repository.default_branch or 'master',
                    file = '%s*' % name
                )
            except HttpError, e:
                if e.code == 404:
                    continue
                raise self._get_exception(e, '%s\'s commits' % repository.project)
            except Exception, e:
                raise self._get_exception(e, '%s\'s commits' % repository.project)
            else:
                found_name = name
                break

        # no commit found => no readme
        if not commits:
            return ('', None)

        for commit in commits:

            # get more information about this commit
            try:
                commit_infos = github.commits.show(repository.project, commits[0].id)
            except Exception, e:
                raise self._get_exception(e, '%s\'s commits' % repository.project)

            # nothing added or modified ?
            if not commit_infos.added and not commit_infos.modified:
                continue

            # get files that looks like a readme file
            files = set()
            if commit_infos.added:
                files.update([file for file in commit_infos.added if file.startswith(found_name)])
            if commit_infos.modified:
                files.update([diff['filename'] for diff in commit_infos.modified if diff['filename'].startswith(found_name)])

            if not files:
                continue

            # get contents for all these files
            contents = []
            for filename in files:
                try:
                    blob = github.get_blob_info(repository.project, commit.id, filename)
                except Exception, e:
                    raise self._get_exception(e, '%s\'s readme file' % repository.project)
                else:
                    contents.append((filename, blob.get('data', 0)))

            if not contents:
                continue

            # keep the biggest
            filename, content = sorted(contents, key=len)[-1]

            # find the type
            filetype = 'txt'
            try:
                extension = filename.split('.')[-1]
                for ftype, extensions in README_TYPES:
                    if extension in extensions:
                        filetype = ftype
                        break
            except:
                pass

            return content, filetype

        return ('', None)


BACKENDS = { 'github': GithubBackend, }