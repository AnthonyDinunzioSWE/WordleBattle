from ..Instances.instances import db, login_manager
from flask_login import UserMixin
import uuid

@login_manager.user_loader
def load_user(user_id):
    print(f"Loading user with ID: {user_id} (type: {type(user_id)})")
    try:
        user_id = uuid.UUID(user_id)
        return User.query.get(user_id)
    except (ValueError, TypeError):
        return None

class User(db.Model, UserMixin):
    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = db.Column(db.String(150), nullable=False, unique=True)
    email = db.Column(db.String(150), nullable=False, unique=True)
    profile_picture = db.Column(db.String(200), nullable=True, default='default.jpg')
    password_hash = db.Column(db.String(256))
    google_id = db.Column(db.String(200), unique=True)
    elo_rating = db.Column(db.Integer, default=1000)
    wins = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)
    games_played = db.Column(db.Integer, default=0)
    draws = db.Column(db.Integer, default=0)
    streak = db.Column(db.Integer, default=0)
    highest_streak = db.Column(db.Integer, default=0)
    points = db.Column(db.Integer, default=0)
    rank = db.Column(db.String(50), default='Silver')
    rank_image = db.Column(db.String(200), default='silver.png')
    rank_color = db.Column(db.String(50), default='silver')

    def update_rank(self):
        if self.elo_rating < 700:
            self.rank = 'Bronze'
        elif 700 <= self.elo_rating < 1200:
            self.rank = 'Silver'
        elif 1200 <= self.elo_rating < 1600:
            self.rank = 'Gold'
        elif 1600 <= self.elo_rating < 2100:
            self.rank = 'Platinum'
        else:
            self.rank = 'Diamond'