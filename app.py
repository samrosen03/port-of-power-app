from flask import Flask, render_template, request, redirect, flash, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Email, Length
from datetime import datetime
import smtplib
from email.message import EmailMessage
from sqlalchemy import func  # ✅ for PR query

# ---------------- FLASK CONFIG ----------------
app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Replace with env var in production

# ---------------- DATABASE CONFIG ----------------
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///progress.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# ---------------- LOGIN MANAGER ----------------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---------------- FORMS ----------------
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired()])
    password = PasswordField('Password', validators=[InputRequired()])
    submit = SubmitField('Login')

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired(), Length(min=4)])
    email = StringField('Email', validators=[InputRequired(), Email()])
    password = PasswordField('Password', validators=[InputRequired(), Length(min=6)])
    submit = SubmitField('Register')

# ---------------- DATABASE MODELS ----------------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False, unique=True)
    email = db.Column(db.String(150), nullable=False, unique=True)
    password = db.Column(db.String(200), nullable=False)

class Progress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(10))
    exercise = db.Column(db.String(100))
    weight = db.Column(db.Integer)
    reps = db.Column(db.Integer)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# ---------------- ROUTES ----------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        existing_user = User.query.filter(
            (User.username == form.username.data) | (User.email == form.email.data)
        ).first()
        if existing_user:
            flash("Username or email already exists.", "error")
            return redirect(url_for('register'))

        hashed_pw = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password=hashed_pw)
        db.session.add(user)
        db.session.commit()
        flash("Account created! Please log in.", "success")
        return redirect(url_for('login'))

    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user)
            return redirect(url_for('progress'))
        flash('Login failed. Check username/password.', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', user=current_user)

@app.route('/progress', methods=['GET', 'POST'])
@login_required
def progress():
    # ---------------- POST: Add New Entry ----------------
    if request.method == 'POST':
        exercise = request.form['exercise']
        weight = request.form['weight']
        reps = request.form['reps']
        date = datetime.now().strftime("%Y-%m-%d")

        if not exercise or not weight or not reps:
            flash("Please fill out all fields.", "error")
            return redirect(url_for('progress'))

        new_entry = Progress(
            date=date,
            exercise=exercise,
            weight=int(weight),
            reps=int(reps),
            user_id=current_user.id
        )
        db.session.add(new_entry)
        db.session.commit()
        flash("Progress submitted!", "success")
        return redirect(url_for('progress'))

    # ---------------- GET: Fetch Data ----------------
    selected_exercise = request.args.get('exercise')

    if selected_exercise:
        progress_data = Progress.query.filter_by(
            exercise=selected_exercise, user_id=current_user.id
        ).order_by(Progress.date.desc()).all()
    else:
        progress_data = Progress.query.filter_by(
            user_id=current_user.id
        ).order_by(Progress.date.desc()).all()

    # All exercises for dropdown
    all_exercises = db.session.query(Progress.exercise).filter_by(
        user_id=current_user.id
    ).distinct().all()
    all_exercises = [e[0] for e in all_exercises]

    # ✅ PR Query
    pr_data = db.session.query(
        Progress.exercise,
        func.max(Progress.weight)
    ).filter_by(user_id=current_user.id).group_by(Progress.exercise).all()

    # ✅ PR Dictionary
    pr_dict = {exercise: max_weight for exercise, max_weight in pr_data}

    return render_template('progress.html',
                           progress_data=progress_data,
                           all_exercises=all_exercises,
                           selected_exercise=selected_exercise,
                           pr_data=pr_data,
                           pr_dict=pr_dict)

# ---------------- DELETE ENTRY ROUTE ----------------
@app.route('/delete/<int:entry_id>', methods=['POST'])
@login_required
def delete_entry(entry_id):
    entry = Progress.query.filter_by(id=entry_id, user_id=current_user.id).first()
    if entry:
        db.session.delete(entry)
        db.session.commit()
        flash("Entry deleted successfully!", "success")
    else:
        flash("Entry not found or unauthorized.", "error")
    return redirect(url_for('progress'))

@app.route('/contact', methods=['POST'])
def contact():
    name = request.form['name']
    email = request.form['email']
    message = request.form['message']

    try:
        send_email(name, email, message)
        flash("Message sent successfully!", "success")
    except Exception as e:
        print("Email error:", e)
        flash("Message failed to send. Try again later.", "error")

    return redirect(url_for('index'))

# ---------------- EMAIL FUNCTION ----------------
def send_email(name, sender_email, message_body):
    msg = EmailMessage()
    msg.set_content(f"Message from {name} <{sender_email}>:\n\n{message_body}")
    msg['Subject'] = "New Contact Form Submission"
    msg['From'] = "portofpower03@gmail.com"
    msg['To'] = "portofpower03@gmail.com"

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login("portofpower03@gmail.com", "nzhzlzoxwrwwucwd")  # Replace with env var
        smtp.send_message(msg)

# ---------------- RUN APP ----------------
if __name__ == '__main__':
    app.run(debug=True)















