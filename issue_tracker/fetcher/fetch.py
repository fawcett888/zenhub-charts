import logging
from django.conf import settings

from issue_tracker.fetcher.clients import GithubClient, ZenhubClient
from issue_tracker.fetcher.exceptions import PipelineNotFoundError
from issue_tracker.models import (
    Repo, Pipeline, PipelineNameMapping, Issue, Transfer
)

logger = logging.getLogger(__name__)


class Fetcher(object):
    def __init__(self, repo_names):
        self.repo_names = repo_names
        self.github = GithubClient(**settings.GITHUB)
        self.zenhub = ZenhubClient(**settings.ZENHUB)
        self.pipelines = {}

    def create_pipelines(self, repo, pipelines):
        Pipeline.objects.get_or_create(
            name='Closed', repo=repo,
            defaults={
                'order': 10000  # assuming there is no board with 10000 cols
            }
        )

        for order, pipeline in enumerate(pipelines):
            Pipeline.objects.update_or_create(
                name=pipeline['name'], repo=repo,
                defaults={
                    'pipeline_id': pipeline['id'],
                    'order': order
                }
            )
        self.pipelines = {
            p.name: p
            for p in Pipeline.objects.filter(repo=repo)
        }
        self.first_pipeline = Pipeline.objects.filter(
            repo=repo).earliest('order')
        self.pipeline_name_mapping = dict(PipelineNameMapping.objects.filter(
            repo=repo
        ).values_list('old_name', 'new_name'))

    def get_issue_numbers(self, pipelines):
        return [
            item['issue_number']
            for sublist in [i['issues'] for i in pipelines]
            for item in sublist
        ]

    def close_issues(self, current_issue_numbers, remote_issue_numbers):
        must_be_closed = set(current_issue_numbers) - set(remote_issue_numbers)
        closed_issues = Issue.objects.filter(number__in=must_be_closed)
        for closed_issue in closed_issues:
            github_issue = self.github.get_issue(
                closed_issue.repo.name, closed_issue.number)
            closed_at = github_issue['closed_at']
            closed_pipeline = self.pipelines['Closed']
            latest_pipeline = Transfer.objects.filter(
                issue__number=closed_issue.number
            ).latest('transfered_at').to_pipeline
            kwargs = {
                'issue': closed_issue,
                'from_pipeline': latest_pipeline,
                'to_pipeline': closed_pipeline,
                'transfered_at': closed_at,
            }
            self.create_transfer(**kwargs)

    def stupid_django_datetime_hack(self, obj):
        """
        Django does not call `to_python` on model save,
        so any `DateField` or `DateTimeField` returns string instead.
        """
        return [
            i
            for i in obj._meta.fields
            if i.name == 'transfered_at'
        ][0].to_python(obj.transfered_at)

    def create_transfer(
            self, issue, from_pipeline, to_pipeline, transfered_at):
        transfer, created = Transfer.objects.get_or_create(
            issue=issue,
            from_pipeline=from_pipeline,
            to_pipeline=to_pipeline,
            transfered_at=transfered_at
        )
        if created:
            logger.info(f'created transfer: {transfer}')
            try:
                previous_transfer = Transfer.objects.filter(
                    issue=issue,
                    to_pipeline=from_pipeline,
                ).latest('transfered_at')
            except Transfer.DoesNotExist:
                return
            delta = (
                self.stupid_django_datetime_hack(transfer)
                - previous_transfer.transfered_at
            )
            total = issue.durations.get(from_pipeline.name, 0)
            total += delta.total_seconds()
            issue.durations[from_pipeline.name] = total
            issue.latest_pipeline_name = transfer.to_pipeline.name
            issue.latest_transfer_date = transfered_at
            issue.save()
            logger.info(f'created duration')

    def get_pipeline(self, repo, name):
        try:
            return self.pipelines[self.pipeline_name_mapping.get(name, name)]
        except KeyError:
            raise PipelineNotFoundError(repo, name)

    def get_issue_events(self, repo, issue_number):
        github_issue = self.github.get_issue(repo.name, issue_number)
        zenhub_issue_events = self.zenhub.get_issue_events(
            repo.repo_id, issue_number)
        issue, created = Issue.objects.update_or_create(
            repo=repo, number=issue_number,
            defaults={'title': github_issue['title']}
        )
        transfers = [
            i for i in zenhub_issue_events if i['type'] == 'transferIssue']
        if created:
            # No transfers yet, but the issue is created
            # and it is in the first pipeline of the board
            # Use `issue.created_at` as the first date
            Transfer.objects.get_or_create(
                issue=issue,
                to_pipeline=self.first_pipeline,
                transfered_at=github_issue['created_at']
            )
        # create the oldest ones first, otherwise
        # we can not calculate durations
        transfers = sorted(transfers, key=lambda x: x['created_at'])
        for transfer in transfers:
            kwargs = {
                'issue': issue,
                'from_pipeline': (
                    self.get_pipeline(repo, transfer['from_pipeline']['name'])
                ),
                'to_pipeline': self.get_pipeline(
                    repo, transfer['to_pipeline']['name']),
                'transfered_at': transfer['created_at']
            }
            self.create_transfer(**kwargs)

    def sync(self):
        repos = Repo.objects.all()
        if self.repo_names:
            repos = repos.filter(name__in=self.repo_names)
        for repo in repos:
            current_issues = repo.issues.all()
            board = self.zenhub.get_board(repo.repo_id)
            self.create_pipelines(repo, board['pipelines'])
            remote_issue_numbers = self.get_issue_numbers(board['pipelines'])
            current_issue_numbers = current_issues.values_list(
                'number', flat=True)

            for issue_number in remote_issue_numbers:
                self.get_issue_events(repo, issue_number)

            self.close_issues(current_issue_numbers, remote_issue_numbers)