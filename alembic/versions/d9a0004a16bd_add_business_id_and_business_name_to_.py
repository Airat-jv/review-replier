"""Add business_id and business_name to MarketplaceAccount

Revision ID: d9a0004a16bd
Revises: 89a2e3d9c255
Create Date: 2024-11-22 17:16:08.718730

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9a0004a16bd'
down_revision: Union[str, None] = '89a2e3d9c255'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('marketplace_accounts', sa.Column('business_id', sa.String(), nullable=True))
    op.add_column('marketplace_accounts', sa.Column('business_name', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('marketplace_accounts', 'business_name')
    op.drop_column('marketplace_accounts', 'business_id')
    # ### end Alembic commands ###