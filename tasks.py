import os
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
        print("Number of posts to scan:", len(posts))
        for post in posts:
            print("Processing post:", post.x_post_link, "with text:", post.original_text[:50])
            candidates = []
            # Real scraping for candidates
            query = post.original_text[:50].replace(' ', '%20')  # URL-encode text snippet
            query_url = f"https://x.com/search?q={query}&src=typed_query&f=live"  # Latest posts
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9',
            }
            try:
                response = requests.get(query_url, headers=headers)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    tweets = soup.find_all('div', {'data-testid': 'tweet'})
                    for tweet in tweets[:10]:  # Limit to 10 recent
                        link_elem = tweet.find('a', href=lambda href: href and '/status/' in href)
                        link = 'https://x.com' + link_elem['href'] if link_elem else ''
                        text_elem = tweet.find('div', {'data-testid': 'tweetText'})
                        text = text_elem.get_text() if text_elem else ''
                        img_elem = tweet.find('img', src=lambda src: src and 'media' in src)
                        img_url = img_elem['src'] if img_elem else ''
                        if link and text:  # Skip self or exact
                            if link != post.x_post_link:
                                candidates.append({'link': link, 'text': text, 'img_url': img_url})
            except Exception as e:
                print(f"Search error: {e}")
            print(f"Found {len(candidates)} candidates")

            if not candidates:
                print("No matching posts found for:", post.x_post_link)
                continue  # No alerts if no candidates

            for candidate in candidates:
                score = detect_theft(post.original_text, candidate['text'], post.original_image_hash, candidate['img_url'])
                print("Score for candidate {}: {}".format(candidate['link'], score))
                if score > 0.8:
                    alert = TheftAlert(monitored_post_id=post.id, user_id=post.user_id, matching_post_link=candidate['link'], similarity_score=score, evidence_text=candidate['text'])
                    db.session.add(alert)
                    db.session.commit()
                    print("Alert created for post:", post.x_post_link)
                    post.last_scan = datetime.utcnow()
                    db.session.commit()
                    user = User.query.get(post.user_id)
                    alert_details = {'link': candidate['link'], 'score': score}
                    send_alert(user.email, alert_details)

def send_alert(user_email, alert_details):
    api_key = os.getenv('SENDGRID_API_KEY')
    if not api_key:
        print("No SendGrid key - email not sent")
        return
    message = {
        'personalizations': [{'to': [{'email': user_email}]}],
        'from': {'email': 'your_email@example.com'},  # Replace with your verified SendGrid sender
        'subject': 'Content Theft Alert!',
        'content': [{'type': 'text/plain', 'value': f"Theft detected! Matching link: {alert_details['link']} Score: {alert_details['score']}"}]
    }
    sg = SendGridAPIClient(api_key)
    response = sg.send(message)
    print("Email response:", response.status_code)