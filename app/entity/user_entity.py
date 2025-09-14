from sqlalchemy import MetaData, Table, Column, Integer, String, TIMESTAMP

meta = MetaData()

users = Table('users', meta,
    Column('user_id', Integer, primary_key=True, autoincrement=True),
    Column('name', String(50)),
    Column('email', String(50)),
    Column('phone', Integer),
    Column('profile_photo', String(50)),
    Column('role', String(50)),
    Column('location', String(50)),
    Column('created_at', TIMESTAMP),
    Column('bio', String(50)),
    Column('password', String(50)),
)