from flask import Blueprint, jsonify

router = Blueprint("health", __name__)

@router.get("/health")
def health():
    return jsonify(status="ok")