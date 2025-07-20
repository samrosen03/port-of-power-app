from flask import Flask, render_template, request, redirect, flash, url_for
import smtplib
from email.message import EmailMessage
import csv
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # change this in production

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

        # Save to CSV
        with open('progress_log.csv', 'a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([date, exercise, weight, reps])

        flash("Progress submitted!", "success")
        return redirect(url_for('progress'))

    # ------- GET method: show existing data -------
    progress_data = []
    try:
        with open('progress_log.csv', 'r') as file:
            reader = csv.reader(file)
            next(reader)  # Skip the header row
            progress_data = list(reader)
    except FileNotFoundError:
        pass

    return render_template('progress.html', progress_data=progress_data)

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
        smtp.login("portofpower03@gmail.com", "nzhzlzoxwrwwucwd")  # Replace with env var in production
        smtp.send_message(msg)

# ---------------- RUN APP ----------------
if __name__ == '__main__':
    app.run(debug=True)







