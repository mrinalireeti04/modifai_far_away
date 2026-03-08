"""Add execution_arn, intent, config_json to projects

Revision ID: a3b8c1d2e4f5
Revises: d9e626f2d8ac
Create Date: 2026-03-08 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3b8c1d2e4f5'
down_revision: Union[str, None] = 'd9e626f2d8ac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('projects', sa.Column('intent', sa.String(), nullable=True))
    op.add_column('projects', sa.Column('config_json', sa.Text(), nullable=True))
    op.add_column('projects', sa.Column('execution_arn', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('projects', 'execution_arn')
    op.drop_column('projects', 'config_json')
    op.drop_column('projects', 'intent')
