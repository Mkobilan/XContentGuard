from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Regexp

class RegistrationForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class AddPostForm(FlaskForm):
    x_post_link = StringField('X Post Link', validators=[DataRequired(), Regexp(r'^https://x\.com/.+/status/\d+$', message='Invalid X post link (e.g., https://x.com/user/status/123)')])
    original_text = TextAreaField('Post Text (Paste here for accurate monitoring)', validators=[DataRequired()])
    submit = SubmitField('Add Post')
