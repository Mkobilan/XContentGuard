import os  # New import to fix the error
from models import db, MonitoredPost, TheftAlert
from utils import detect_theft
from app import app  # To use app context
import schedule
import time
from bs4 import BeautifulSoup
import requests
from sendgrid import SendGridAPIClient
from datetime import datetime
from models import User

def run_scans():
    with app.app_context():
        posts = MonitoredPost.query.all()
        print("Number of posts to scan:", len(posts))  # Debug: See if posts exist
        for post in posts:
            print("Processing post:", post.x_post_link, "with text:", post.original_text[:50])  # Debug post info
            # Simulate candidates for testing (exact and low match)
            candidates = [
                {'link': 'https://x.com/fake/status/123', 'text': post.original_text, 'img_url': ''},  # Exact match for test
                {'link': 'https://x.com/fake/status/456', 'text': 'Different text', 'img_url': ''}  # Low match
            ]  # Simulate candidates; in real, use scraping or API

            # Optional real scraping (uncomment if needed, but may require login/auth)
            # query_url = f"https://x.com/search?q={post.original_text[:50]}"  # Basic search
            # headers = {'User-Agent': 'Mozilla/5.0'}
            # response = requests.get(query_url, headers=headers)
            # soup = BeautifulSoup(response.text, 'html.parser')
            # for tweet in soup.find_all('div', {'data-testid': 'tweet'}):
            #     link = 'https://x.com' + tweet.find('a')['href'] if tweet.find('a') else ''
            #     text = tweet.find('div', {'data-testid': 'tweetText'}).get_text() if tweet.find('div', {'data-testid': 'tweetText'}) else ''
            #     img_url = tweet.find('img')['src'] if tweet.find('img') else ''
            #     candidates.append({'link': link, 'text': text, 'img_url': img_url})

            for candidate in candidates[:10]:  # Limit to 10
                score = detect_theft(post.original_text, candidate['text'], post.original_image_hash, candidate['img_url'])
                print("Score for candidate {}: {}".format(candidate['link'], score))  # Debug in console
                if score > 0.8:  # Threshold for theft
                    alert = TheftAlert(monitored_post_id=post.id, user_id=post.user_id, matching_post_link=candidate['link'], similarity_score=score, evidence_text=candidate['text'])
                    db.session.add(alert)
                    db.session.commit()
                    print("Alert created for post:", post.x_post_link)  # Debug alert creation
                    # New additions start here
                    post.last_scan = datetime.utcnow()
                    db.session.commit()
                    user = User.query.get(post.user_id)
                    alert_details = {'link': candidate['link'], 'score': score}
                    send_alert(user.email, alert_details)  # Will print if no key
                    # New additions end here

def send_alert(user_email, alert_details):
    api_key = os.getenv('SENDGRID_API_KEY')
    if not api_key:
        print("No SendGrid key - email not sent")
        return
    message = {
        'personalizations': [{'to': [{'email': user_email}]}],
        'from': {'email': 'info@matthewkobilan.com'},  # Replace with your verified SendGrid sender
        'subject': 'Content Theft Alert!',
        'content': [{'type': 'text/plain', 'value': f"Theft detected! Matching link: {alert_details['link']} Score: {alert_details['score']}"}]
    }
    sg = SendGridAPIClient(api_key)
    response = sg.send(message)
    print("Email response:", response.status_code)