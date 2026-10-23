from app.extensions import db
from app.models import Message

def run():
    if db.session.get(Message, 1) is None:
        db.session.add(Message(text="hello world"))
        db.session.commit()
        print("messages: добавлено")
    else:
        print("messages: уже есть, пропускаю")