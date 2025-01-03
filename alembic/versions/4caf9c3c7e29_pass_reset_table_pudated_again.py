"""pass reset table pudated again

Revision ID: 4caf9c3c7e29
Revises: 65d139cd141e
Create Date: 2024-12-26 10:17:49.619175

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4caf9c3c7e29'
down_revision: Union[str, None] = '65d139cd141e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('password_resets_reset_token_key', 'password_resets', type_='unique')
    op.drop_column('password_resets', 'reset_token')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('password_resets', sa.Column('reset_token', sa.VARCHAR(), autoincrement=False, nullable=False))
    op.create_unique_constraint('password_resets_reset_token_key', 'password_resets', ['reset_token'])
    # ### end Alembic commands ###
