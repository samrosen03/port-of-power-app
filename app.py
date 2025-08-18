from flask import Flask, render_template, request, redirect, flash, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Email, Length
from datetime import datetime, timedelta
import smtplib
from email.message import EmailMessage
from sqlalchemy import func
from dotenv import load_dotenv
load_dotenv()

# ---------------- FLASK CONFIG ----------------
import os
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret")
# ---------------- DATABASE CONFIG ----------------
db_url = os.getenv("DATABASE_URL")

# Normalize old scheme some providers use
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

# Require SSL for managed Postgres (Render)
if db_url and "sslmode=" not in db_url:
    db_url += ("&" if "?" in db_url else "?") + "sslmode=require"

app.config["SQLALCHEMY_DATABASE_URI"] = db_url or "sqlite:///progress.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
from flask_migrate import Migrate
migrate = Migrate(app, db)


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
    __tablename__ = "users"  # not the reserved keyword "user"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False, unique=True)
    email = db.Column(db.String(150), nullable=False, unique=True)
    password = db.Column(db.String(200), nullable=False)

class Progress(db.Model):
    __tablename__ = "progress"
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(10))
    exercise = db.Column(db.String(100))
    weight = db.Column(db.Integer)
    reps = db.Column(db.Integer)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

class Cardio(db.Model):
    __tablename__ = "cardio"
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(10))
    activity = db.Column(db.String(100))
    duration = db.Column(db.Float)   # minutes
    distance = db.Column(db.Float)   # optional
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)


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

# ---------------- PROGRESS ROUTE ----------------
@app.route('/progress', methods=['GET', 'POST'])
@login_required
def progress():
    # ✅ POST: Add new progress entry
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

    # ✅ GET: Load progress data
    selected_exercise = request.args.get('exercise')

    if selected_exercise:
        progress_data = Progress.query.filter_by(
            exercise=selected_exercise, user_id=current_user.id
        ).order_by(Progress.date.desc()).all()
    else:
        progress_data = Progress.query.filter_by(
            user_id=current_user.id
        ).order_by(Progress.date.desc()).all()

    # ✅ Total workouts count
    workout_count = len(progress_data)

    # ✅ Personal Records
    all_exercises = db.session.query(Progress.exercise).filter_by(
        user_id=current_user.id
    ).distinct().all()
    all_exercises = [e[0] for e in all_exercises]

    pr_data = db.session.query(
        Progress.exercise,
        func.max(Progress.weight)
    ).filter_by(user_id=current_user.id).group_by(Progress.exercise).all()

    pr_dict = {exercise: max_weight for exercise, max_weight in pr_data}

    # ✅ Percent change for each PR
    percent_changes = {}
    for exercise in all_exercises:
        first_entry = Progress.query.filter_by(user_id=current_user.id, exercise=exercise).order_by(Progress.date.asc()).first()
        if first_entry and pr_dict.get(exercise):
            start_weight = first_entry.weight
            pr_weight = pr_dict[exercise]
            if start_weight > 0:
                percent_changes[exercise] = round(((pr_weight - start_weight) / start_weight) * 100, 1)

    # ✅ Last Workout Date + Warning if >7 days
    last_workout_date = None
    show_warning = False
    if progress_data:
        last_workout_date = progress_data[0].date
        try:
            last_date_obj = datetime.strptime(last_workout_date, "%Y-%m-%d")
            if datetime.now() - last_date_obj > timedelta(days=7):
                show_warning = True
        except:
            pass

    return render_template('progress.html',
                           progress_data=progress_data,
                           all_exercises=all_exercises,
                           selected_exercise=selected_exercise,
                           pr_data=pr_data,
                           pr_dict=pr_dict,
                           workout_count=workout_count,
                           last_workout_date=last_workout_date,
                           show_warning=show_warning,
                           percent_changes=percent_changes)
# ---------------- CARDIO ROUTE ----------------
@app.route('/cardio', methods=['GET', 'POST'])
@login_required
def cardio():
    # ✅ POST: Add new cardio entry
    if request.method == 'POST':
        activity = request.form['activity']
        duration = request.form['duration']
        distance = request.form['distance']
        date = datetime.now().strftime("%Y-%m-%d")

        if not activity or not duration:
            flash("Please fill out at least activity and duration.", "error")
            return redirect(url_for('cardio'))

        new_entry = Cardio(
            date=date,
            activity=activity,
            duration=float(duration),
            distance=float(distance) if distance else None,
            user_id=current_user.id
        )
        db.session.add(new_entry)
        db.session.commit()
        flash("Cardio entry submitted!", "success")
        return redirect(url_for('cardio'))

    # ✅ GET: Load cardio data
    selected_activity = request.args.get('activity')
    if selected_activity:
        cardio_data = Cardio.query.filter_by(
            activity=selected_activity, user_id=current_user.id
        ).order_by(Cardio.date.desc()).all()
    else:
        cardio_data = Cardio.query.filter_by(
            user_id=current_user.id
        ).order_by(Cardio.date.desc()).all()

    # ✅ Activity list
    all_activities = db.session.query(Cardio.activity).filter_by(
        user_id=current_user.id
    ).distinct().all()
    all_activities = [a[0] for a in all_activities]

    # ✅ Personal Records: best duration and longest distance
    pr_durations = db.session.query(Cardio.activity, func.max(Cardio.duration)).filter_by(user_id=current_user.id).group_by(Cardio.activity).all()
    pr_distances = db.session.query(Cardio.activity, func.max(Cardio.distance)).filter(Cardio.user_id == current_user.id, Cardio.distance.isnot(None)).group_by(Cardio.activity).all()
    pr_duration_dict = {a: d for a, d in pr_durations}
    pr_distance_dict = {a: dist for a, dist in pr_distances}

    return render_template('cardio.html',
                           cardio_data=cardio_data,
                           all_activities=all_activities,
                           selected_activity=selected_activity,
                           pr_duration_dict=pr_duration_dict,
                           pr_distance_dict=pr_distance_dict)
# ---------------- EDIT STRENGTH ENTRY ROUTE ----------------
@app.route('/edit/<int:entry_id>', methods=['GET', 'POST'], endpoint='edit_entry')
@login_required
def edit_entry(entry_id):
    entry = Progress.query.filter_by(id=entry_id, user_id=current_user.id).first()
    if not entry:
        flash("Strength entry not found or unauthorized.", "error")
        return redirect(url_for('progress'))

    if request.method == 'POST':
        entry.exercise = request.form['exercise']
        entry.weight = int(request.form['weight'])
        entry.reps = int(request.form['reps'])
        db.session.commit()
        flash("Strength entry updated successfully!", "success")
        return redirect(url_for('progress'))

    return render_template('edit.html', entry=entry)

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

# ---------------- DELETE CARDIO ENTRY ROUTE ----------------
@app.route('/delete_cardio/<int:entry_id>', methods=['POST'])
@login_required
def delete_cardio(entry_id):
    entry = Cardio.query.filter_by(id=entry_id, user_id=current_user.id).first()
    if entry:
        db.session.delete(entry)
        db.session.commit()
        flash("Cardio entry deleted successfully!", "success")
    else:
        flash("Cardio entry not found or unauthorized.", "error")
    return redirect(url_for('cardio'))


# ---------------- EDIT CARDIO ENTRY ROUTE ----------------
@app.route('/edit_cardio/<int:entry_id>', methods=['GET', 'POST'], endpoint='edit_cardio')
@login_required
def edit_cardio(entry_id):
    entry = Cardio.query.filter_by(id=entry_id, user_id=current_user.id).first()
    if not entry:
        flash("Cardio entry not found or unauthorized.", "error")
        return redirect(url_for('cardio'))

    if request.method == 'POST':
        entry.activity = request.form['activity']
        entry.duration = float(request.form['duration'])
        entry.distance = float(request.form['distance']) if request.form['distance'] else None
        db.session.commit()
        flash("Cardio entry updated successfully!", "success")
        return redirect(url_for('cardio'))

    return render_template('edit_cardio.html', entry=entry)




# ---------------- CONTACT ROUTE ----------------
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
    msg['From'] = os.getenv("MAIL_FROM")
    msg['To'] = os.getenv("MAIL_TO")

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(os.getenv("MAIL_USER"), os.getenv("MAIL_PASS"))
        smtp.send_message(msg)


# ---------------- RUN APP ----------------
if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))



















