import click
from flask.cli import with_appcontext
from sqlalchemy import func

from app.extensions import db
from app.models import User


@click.command("create-admin")
@click.option("--name", prompt="Administrator full name")
@click.option("--email", prompt="Administrator email")
@click.password_option("--password", confirmation_prompt=True)
@with_appcontext
def create_admin(name, email, password):
    """Create an administrator account from a trusted server shell."""
    email = email.strip().lower()
    if not name.strip() or len(password) < 12:
        raise click.ClickException("A name is required and the password must be at least 12 characters.")
    if User.query.filter(func.lower(User.email) == email).first():
        raise click.ClickException("An account with that email already exists.")
    user = User(full_name=name.strip(), email=email, role="admin", is_active=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    click.echo(f"Administrator account created for {email}.")
