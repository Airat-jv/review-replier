"""Add MarketplaceAccount model

Revision ID: c1772fd60a4e
Revises: 3c7266e0696d
Create Date: 2024-11-20 16:44:29.647097

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1772fd60a4e'
down_revision: Union[str, None] = '3c7266e0696d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('users', 'marketplaces')
    op.drop_column('users', 'api_keys')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('users', sa.Column('api_keys', sa.VARCHAR(), autoincrement=False, nullable=True))
    op.add_column('users', sa.Column('marketplaces', sa.VARCHAR(), autoincrement=False, nullable=True))
    # ### end Alembic commands ###
