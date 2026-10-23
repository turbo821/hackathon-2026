from flask import Blueprint, jsonify
from ..extensions import db
from ..models import Message

router = Blueprint("hello", __name__)

@router.get("/hello")
def hello():
    msg = db.session.get(Message, 1)
    return jsonify(message=msg.text)