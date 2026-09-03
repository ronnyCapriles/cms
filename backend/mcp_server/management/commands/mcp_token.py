"""Create an MCP token from the shell."""
from django.core.management.base import BaseCommand

from mcp_server.models import Scope, issue_token


class Command(BaseCommand):
    help = "Create an MCP bearer token and print it once."

    def add_arguments(self, parser):
        parser.add_argument("label", help="What the token is for, e.g. 'claude code'.")
        parser.add_argument("--scope", choices=[Scope.READ, Scope.WRITE],
                            default=Scope.WRITE)

    def handle(self, *args, **options):
        _, raw = issue_token(options["label"], scope=options["scope"])
        self.stdout.write(self.style.SUCCESS(raw))
        self.stdout.write(
            self.style.WARNING("Stored as a hash. This is the only time it is shown.")
        )
