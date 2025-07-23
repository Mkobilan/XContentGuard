from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    subscription_status = db.Column(db.String(20), default='free')  # 'free' or 'paid'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    posts = db.relationship('MonitoredPost', backref='user', lazy=True)
    alerts = db.relationship('TheftAlert', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class MonitoredPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    x_post_link = db.Column(db.String(200), nullable=False)
    original_text = db.Column(db.Text, nullable=True)
    original_image_hash = db.Column(db.String(64), nullable=True)  # For image matching
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    last_scan = db.Column(db.DateTime, nullable=True)

class TheftAlert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    monitored_post_id = db.Column(db.Integer, db.ForeignKey('monitored_post.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    matching_post_link = db.Column(db.String(200), nullable=False)
    similarity_score = db.Column(db.Float, nullable=False)
    evidence_text = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Add relationships if needed
MonitoredPost.alerts = db.relationship('TheftAlert', backref='monitored_post', lazy=True)