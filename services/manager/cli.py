import click
import sys
import requests
import json
sys.path.insert(0, '/home/loki/ideas/sea-qwens/worktrees/legion-implement')
from services.manager.interviewer import Interviewer


LIBRARIAN_URL = "http://localhost:8001"


@click.group()
def cli():
    """Legion Manager - Interview users and create ProjectSpecs"""
    pass


@cli.command()
def interview():
    """Conduct a project requirements interview"""
    click.echo("=" * 60)
    click.echo("LEGION MANAGER - Project Requirements Interview")
    click.echo("=" * 60)
    click.echo()

    interviewer = Interviewer()

    while not interviewer.is_complete():
        question = interviewer.get_next_question()
        if not question:
            break

        click.echo(click.style(f"\n{question.text}", fg="green", bold=True))
        answer = click.prompt("Your answer")
        interviewer.record_response(answer, question.category)

    # Extract and display spec
    spec = interviewer.extract_project_spec()

    click.echo()
    click.echo("=" * 60)
    click.echo("EXTRACTED PROJECT SPEC")
    click.echo("=" * 60)
    click.echo(f"Name: {spec['name']}")
    click.echo(f"Tech Stack: {', '.join(spec['tech_stack'])}")
    click.echo(f"Features: {', '.join(spec['features'])}")
    click.echo()

    # Confirm before sending
    if click.confirm("Send this ProjectSpec to the Librarian?"):
        try:
            response = requests.post(
                f"{LIBRARIAN_URL}/project-specs",
                json=spec
            )
            if response.status_code == 201:
                result = response.json()
                click.echo(click.style(
                    f"✓ ProjectSpec created with ID: {result['id']}",
                    fg="green", bold=True
                ))
            else:
                click.echo(click.style(
                    f"✗ Error: {response.text}",
                    fg="red"
                ))
        except requests.exceptions.ConnectionError:
            click.echo(click.style(
                "✗ Could not connect to Librarian. Is it running?",
                fg="red"
            ))
            click.echo(f"Spec would be: {json.dumps(spec, indent=2)}")
    else:
        click.echo("Interview cancelled. No data sent.")


if __name__ == "__main__":
    cli()
