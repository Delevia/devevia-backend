""" updated profile

Revision ID: 57a0ac249180
Revises: b7be5f768661
Create Date: 2024-11-08 15:51:43.231307

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '57a0ac249180'
down_revision: Union[str, None] = 'b7be5f768661'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('riders', sa.Column('nin', sa.String(length=11), nullable=True))
    op.add_column('riders', sa.Column('nin_photo', sa.LargeBinary(), nullable=True))
    op.add_column('users', sa.Column('gender', sa.Enum('male', 'female', name='genderenum'), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('users', 'gender')
    op.drop_column('riders', 'nin_photo')
    op.drop_column('riders', 'nin')
    # ### end Alembic commands ###