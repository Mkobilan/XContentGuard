from app import app, db
from models import MonitoredPost
with app.app_context():
    posts = MonitoredPost.query.all()
    for post in posts:
        post.original_text = "Test text for similarity detection on X"
        db.session.commit()
print("Posts updated with test text.")