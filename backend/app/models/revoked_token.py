from app.extensions import db
from app.timeutils import utcnow


class RevokedToken(db.Model):
    """Отозванные JWT (logout). Храним jti до истечения срока токена."""

    __tablename__ = "revoked_tokens"

    jti = db.Column(db.String(64), primary_key=True)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    revoked_at = db.Column(db.DateTime, nullable=False, default=utcnow)
