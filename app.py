from flask import Flask, render_template, request, redirect, flash, url_for
import smtplib
from email.message import EmailMessage
import csv
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy  # NEW

# ---------------- FLASK CONFIG ----------------
app = Flask(__name__)
app.secret_key = 'supersecretkey'  # change this in production

# ---------------- DATABASE CONFIG ----------------
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///progress.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ---------------- DATABASE MODEL ----------------
class Progress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(10))
    exercise = db.Column(db.String(100))
    weight = db.Column(db.Integer)
    reps = db.Column(db.Integer)

# ---------------- HOME ----------------
@app.route('/')
def index():
    return render_template('index.html')

# ---------------- PROGRESS ----------------
@app.route('/progress', methods=['GET', 'POST'])
def progress():
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
            reps=int(reps)
        )
        db.session.add(new_entry)
        db.session.commit()

        flash("Progress submitted!", "success")
        return redirect(url_for('progress'))

    # ✅ Handle filter on GET
    selected_exercise = request.args.get('exercise')

    if selected_exercise:
        progress_data = Progress.query.filter_by(exercise=selected_exercise).order_by(Progress.date.desc()).all()
    else:
        progress_data = Progress.query.order_by(Progress.date.desc()).all()

    # ✅ Get list of all exercises for dropdown
    all_exercises = db.session.query(Progress.exercise).distinct().all()
    all_exercises = [e[0] for e in all_exercises]

    return render_template('progress.html',
                           progress_data=progress_data,
                           all_exercises=all_exercises,
                           selected_exercise=selected_exercise)


# ---------------- CONTACT ----------------
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

# ---------------- SEND EMAIL FUNCTION ----------------
def send_email(name, sender_email, message_body):
    msg = EmailMessage()
    msg.set_content(f"Message from {name} <{sender_email}>:\n\n{message_body}")
    msg['Subject'] = "New Contact Form Submission"
    msg['From'] = "portofpower03@gmail.com"
    msg['To'] = "portofpower03@gmail.com"

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login("portofpower03@gmail.com", "nzhzlzoxwrwwucwd")  # Use env vars in production
        smtp.send_message(msg)

# ---------------- RUN APP ----------------
if __name__ == '__main__':
    app.run(debug=True)








