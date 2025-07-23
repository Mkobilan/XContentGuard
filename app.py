import os
from flask import Flask, render_template, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from dotenv import load_dotenv
from models import db, User
from forms import RegistrationForm, LoginForm
from forms import AddPostForm
from models import MonitoredPost

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URI')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))  # Updated to avoid deprecation warning

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user:
            flash('Email already registered.', 'danger')
            return redirect(url_for('register'))
        user = User(email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/add_post', methods=['GET', 'POST'])
@login_required
def add_post():
    form = AddPostForm()
    if form.validate_on_submit():
        if current_user.subscription_status == 'free' and len(current_user.posts) >= 2:
            flash('Free users limited to 2 posts. Upgrade for more.', 'warning')
            return redirect(url_for('dashboard'))
        # Fetch X post content via scraping
        import requests
        from bs4 import BeautifulSoup
        url = form.x_post_link.data
        headers = {'User-Agent': 'Mozilla/5.0'}  # To mimic browser
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        # Extract text (find the post text div - adjust selector if needed based on X HTML)
        original_text = ''
        text_elem = soup.find('div', {'data-testid': 'tweetText'})
        if text_elem:
            original_text = text_elem.get_text(strip=True)
        # Extract image URL (first image in media)
        image_url = ''
        media_elem = soup.find('img', {'alt': 'Image'})
        if media_elem:
            image_url = media_elem['src']
        # Compute hash if image
        original_image_hash = ''
        if image_url:
            from PIL import Image
            from imagehash import dhash
            img_response = requests.get(image_url, stream=True)
            if img_response.status_code == 200:
                img = Image.open(img_response.raw)
                original_image_hash = str(dhash(img))
        post = MonitoredPost(user_id=current_user.id, x_post_link=form.x_post_link.data, original_text=original_text, original_image_hash=original_image_hash)
        db.session.add(post)
        db.session.commit()
        flash('Post added for monitoring!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('add_post.html', form=form)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)