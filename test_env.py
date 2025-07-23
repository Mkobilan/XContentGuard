import os
from dotenv import load_dotenv

load_dotenv()
print(os.getenv('SECRET_KEY'))  # Should print your generated key