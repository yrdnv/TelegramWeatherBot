import os
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Sequence

Base = declarative_base()


class Database:
    def __init__(self, obj='sqlite:///bot_db.db'):
        engine = create_engine(obj, echo=False)

        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        self.session = Session()

    def add_user(self, username, chat_id, lat, lon, weather, last_update):
        self.user = User(username=username, chat_id=chat_id, lat=lat, lon=lon, weather=weather, last_update=last_update)
        self.session.add(self.user)
        self.session.commit()


    def get_data(self, chat_id):
        return self.session.query(User).filter(User.chat_id == chat_id).one()



class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, Sequence('user_id_seq'), primary_key=True)
    username = Column(String)
    chat_id = Column(Integer, unique=True)
    lat = Column(String)
    lon = Column(String)
    weather = Column(String)
    last_update = Column(DateTime)
    subscribe = Column(Boolean)
    period = Column(Integer)

    def __repr__(self):
        return '<User(id=%s, username=%s, chat_id=%s, lat=%s, lon=%s' \
               'weather=%s, last_update=%s, subscribe=%s, period=%s'\
               %(self.id, self.username, self.chat_id, self.lat, self.lon,
                 self.weather, self.last_update, self.subscribe, self.period)


