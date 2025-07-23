import os
from flask import Flask, render_template, redirect, url_for, flash, request, Response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from dotenv import load_dotenv
from models import db, User, MonitoredPost, TheftAlert
from forms import RegistrationForm, LoginForm, AddPostForm
import stripe
from io import StringIO
import csv
from datetime import datetime, timedelta, timezone  # Added timezone

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

@app.route('/scan', methods=['GET'])
@login_required
def manual_scan():
    from tasks import run_scans
    run_scans()
    flash('Manual scan completed!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/add_post', methods=['GET', 'POST'])
@login_required
def add_post():
    form = AddPostForm()
    if form.validate_on_submit():
        if current_user.subscription_status == 'free' and len(current_user.posts) >= 2:
            flash('Free users limited to 2 posts. Upgrade for more.', 'warning')
            return redirect(url_for('dashboard'))
        original_text = form.original_text.data
        original_image_hash = ''
        import requests
        from bs4 import BeautifulSoup
        from PIL import Image
        import io
        from imagehash import dhash
        url = form.x_post_link.data
        if url:
            headers = {'User-Agent': 'Mozilla/5.0'}
            try:
                response = requests.get(url, headers=headers)
                soup = BeautifulSoup(response.text, 'html.parser')
                media_elem = soup.find('img', {'alt': 'Image'})
                if media_elem:
                    image_url = media_elem['src']
                    img_response = requests.get(image_url, stream=True)
                    if img_response.status_code == 200:
                        img = Image.open(io.BytesIO(img_response.content))
                        original_image_hash = str(dhash(img))
                        print(f"Image hashed: {original_image_hash}")
            except Exception as e:
                flash(f'Image fetch error: {str(e)}', 'warning')
        post = MonitoredPost(user_id=current_user.id, x_post_link=form.x_post_link.data, original_text=original_text, original_image_hash=original_image_hash)
        db.session.add(post)
        db.session.commit()
        flash('Post added for monitoring!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('add_post.html', form=form)

@app.route('/delete_post/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    post = MonitoredPost.query.filter_by(id=post_id, user_id=current_user.id).first_or_404()
    db.session.delete(post)
    db.session.commit()
    flash('Post deleted successfully.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/scan_post/<int:post_id>', methods=['GET'])
@login_required
def scan_post(post_id):
    from utils import detect_theft
    from tasks import send_alert
    from models import TheftAlert
    from datetime import datetime
    post = MonitoredPost.query.filter_by(id=post_id, user_id=current_user.id).first_or_404()
    candidates = [
        {'link': 'https://x.com/fake/status/123', 'text': post.original_text, 'img_url': ''},
        {'link': 'https://x.com/fake/status/456', 'text': 'Different text', 'img_url': ''}
    ]
    for candidate in candidates:
        score = detect_theft(post.original_text, candidate['text'], post.original_image_hash, candidate['img_url'])
        print(f"Score for candidate {candidate['link']}: {score}")
        if score > 0.8:
            alert = TheftAlert(monitored_post_id=post.id, user_id=current_user.id, matching_post_link=candidate['link'], similarity_score=score, evidence_text=candidate['text'])
            db.session.add(alert)
            db.session.commit()
            print(f"Alert created for post: {post.x_post_link}")
            post.last_scan = datetime.utcnow()
            db.session.commit()
            alert_details = {'link': candidate['link'], 'score': score}
            send_alert(current_user.email, alert_details)
    flash('Scan completed for this post!', 'success')
    return redirect(url_for('dashboard'))

stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

@app.route('/subscribe', methods=['GET'])
@login_required
def subscribe():
    try:
        session = stripe.checkout.Session.create(
            customer_email=current_user.email,
            payment_method_types=['card'],
            line_items=[{
                'price': os.getenv('STRIPE_PRICE_ID'),
                'quantity': 1,
            }],
            mode='subscription',
            success_url=url_for('dashboard', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('dashboard', _external=True),
        )
        return redirect(session.url, code=303)
    except Exception as e:
        flash(f'Subscription error: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    event = None
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv('STRIPE_WEBHOOK_SECRET')
        )
    except ValueError as e:
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError as e:
        return 'Invalid signature', 400
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user = User.query.filter_by(email=session['customer_email']).first()
        if user:
            user.subscription_status = 'paid'
            db.session.commit()
            print(f"Updated user {user.email} to paid.")
    return 'Success', 200

@app.route('/reports', methods=['GET'])
@login_required
def reports():
    one_week_ago = datetime.now(tz=timezone.utc) - timedelta(days=7)
    alerts = TheftAlert.query.filter_by(user_id=current_user.id).filter(TheftAlert.timestamp >= one_week_ago).all()
    summary = f"{len(alerts)} potential thefts detected this week."
    if alerts:
        top_match = max(alerts, key=lambda x: x.similarity_score)
        summary += f" Top match: {top_match.matching_post_link} (Score: {top_match.similarity_score:.2f})"
    if request.args.get('download') == 'csv' and current_user.subscription_status == 'paid':
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Matching Link', 'Similarity Score', 'Date', 'Evidence Text'])
        for alert in alerts:
            writer.writerow([alert.matching_post_link, alert.similarity_score, alert.timestamp, alert.evidence_text])
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=weekly_report.csv'}
        )
    return render_template('reports.html', summary=summary, alerts=alerts)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)