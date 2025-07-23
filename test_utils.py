from utils import detect_theft
score = detect_theft("Hello world this is a test", "Hi globe this is similar test", None, None)
print(score)  # Should print something like 0.632 (based on word overlap)