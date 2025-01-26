""" cordinates updated rides

Revision ID: f9d1327d4ce5
Revises: c7d2bab40efd
Create Date: 2025-01-25 13:39:27.723555

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f9d1327d4ce5'
down_revision: Union[str, None] = 'c7d2bab40efd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('drivers', 'dropoff_longitude')
    op.drop_column('drivers', 'dropoff_latitude')
    op.add_column('rides', sa.Column('dropoff_latitude', sa.Float(), nullable=True))
    op.add_column('rides', sa.Column('dropoff_longitude', sa.Float(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('rides', 'dropoff_longitude')
    op.drop_column('rides', 'dropoff_latitude')
    op.add_column('drivers', sa.Column('dropoff_latitude', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True))
    op.add_column('drivers', sa.Column('dropoff_longitude', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True))
    # ### end Alembic commands ###
