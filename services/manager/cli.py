import click
import sys
import os
import requests
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from services.manager.interviewer import Interviewer
from services.manager.feature_interviewer import FeatureInterviewer


LIBRARIAN_URL = "http://localhost:8001"


@click.group()
def cli():
    """Sea Qwens Manager - Interview users and create ProjectSpecs"""
    pass


@cli.command()
def interview():
    """Conduct a project requirements interview"""
    click.echo("=" * 60)
    click.echo("SEA QWENS MANAGER - Project Requirements Interview")
    click.echo("=" * 60)
    click.echo()

    interviewer = Interviewer(librarian_url=LIBRARIAN_URL)

    while not interviewer.is_complete():
        question = interviewer.get_next_question()
        if not question:
            break

        click.echo(click.style(f"\n{question.text}", fg="green", bold=True))
        answer = click.prompt("Your answer")
        interviewer.record_response(answer, question.category)

        # After getting project name, try to load code context
        if question.category == "overview" and interviewer.questions_asked == 1:
            project_name = interviewer.responses[-1]["answer"].strip()
            if project_name:
                click.echo(click.style(f"\nChecking for existing project: {project_name}...", fg="yellow"))
                interviewer.load_code_context(project_name, [])
                if interviewer.code_context:
                    overview = interviewer.code_context.get_project_overview(project_name)
                    if overview:
                        click.echo(click.style(
                            f"Found existing code: {overview['total_files']} files, "
                            f"{overview['total_functions']} functions, "
                            f"{overview['total_classes']} classes",
                            fg="cyan"
                        ))
                    else:
                        click.echo(click.style("No existing code found for this project.", fg="yellow"))
                else:
                    click.echo(click.style("Could not connect to code database.", fg="yellow"))

    # Extract and display spec
    spec = interviewer.extract_project_spec()

    # Show existing features if code context is available
    if interviewer.code_context and spec["features"]:
        click.echo(click.style("\nChecking existing features...", fg="yellow"))
        feature_map = interviewer.code_context.find_existing_features(
            spec["name"], spec["features"]
        )
        for feature, info in feature_map.items():
            if info["found"]:
                match_names = ", ".join(m["name"] for m in info["matches"])
                click.echo(click.style(
                    f"  ✓ '{feature}' — found: {match_names}",
                    fg="green"
                ))
            else:
                click.echo(click.style(
                    f"  ✗ '{feature}' — not found (new implementation needed)",
                    fg="yellow"
                ))

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


@cli.command()
def add_feature():
    """Add a new feature to an existing project."""
    click.echo("=" * 60)
    click.echo("SEA QWENS MANAGER - Add Feature to Existing Project")
    click.echo("=" * 60)
    click.echo()

    interviewer = FeatureInterviewer(librarian_url=LIBRARIAN_URL)

    # Step 1: List existing projects
    projects = interviewer.list_projects()
    if not projects:
        click.echo(click.style(
            "No existing projects found. Run `interview` first to create a project.",
            fg="yellow"
        ))
        return

    click.echo(click.style("\nSelect a project to extend:", fg="green", bold=True))
    for i, project in enumerate(projects, 1):
        tech = ", ".join(project.get("tech_stack", []))
        features = ", ".join(project.get("features", []))
        click.echo(f"  {i}. {project['name']} (tech: {tech}, features: {features})")

    click.echo()
    choice = click.prompt(
        "Enter project number",
        type=click.IntRange(1, len(projects))
    )

    selected = projects[choice - 1]
    interviewer.selected_project = selected
    project_name = selected["name"]

    # Step 2: Load code context
    click.echo(click.style(f"\nLoading code context for {project_name}...", fg="yellow"))
    interviewer.load_project_context(project_name)

    if interviewer.code_context_overview:
        click.echo(click.style(
            f"Found existing code: {interviewer.code_context_overview}",
            fg="cyan"
        ))
    else:
        click.echo(click.style("Could not load code context.", fg="yellow"))
        interviewer.code_context_overview = "Code context unavailable."

    # Step 3: Get feature description
    click.echo()
    click.echo(click.style(
        f"Describe the feature you want to add to {project_name}:",
        fg="green", bold=True
    ))
    feature_description = click.prompt("Feature description")

    # Step 4: LLM-driven clarifying questions
    click.echo()
    click.echo(click.style("Analyzing your description...", fg="yellow"))

    while True:
        questions = interviewer.generate_questions(feature_description, interviewer.code_context_overview)
        if questions is None:
            break

        for question in questions:
            click.echo(click.style(f"\n{question}", fg="green", bold=True))
            answer = click.prompt("Your answer")
            interviewer.record_response(question, answer)

    # Step 5: Build and display spec
    spec = interviewer.build_spec(feature_description)

    click.echo()
    click.echo("=" * 60)
    click.echo("EXTRACTED FEATURE SPEC")
    click.echo("=" * 60)
    click.echo(f"Name: {spec['name']}")
    click.echo(f"Parent Project: {spec['parent_project']}")
    click.echo(f"Tech Stack: {', '.join(spec['tech_stack'])}")
    click.echo(f"Features: {', '.join(spec['features'])}")
    if spec.get('constraints'):
        click.echo(f"Constraints: {', '.join(spec['constraints'])}")
    click.echo()

    # Step 6: Confirm and send
    if click.confirm("Send this FeatureSpec to the Librarian?"):
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
