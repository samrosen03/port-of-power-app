from flask import Flask, render_template, request, redirect, url_for
import csv
from datetime import datetime

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/progress', methods=['GET', 'POST'])
def progress():
    if request.method == 'POST':
        exercise = request.form['exercise']
        weight = request.form['weight']
        reps = request.form['reps']
        date = datetime.now().strftime("%Y-%m-%d")

        with open('progress_log.csv', 'a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([date, exercise, weight, reps])

        return redirect(url_for('progress'))

    # Read CSV and show entries
    entries = []
    try:
        with open('progress_log.csv', 'r') as file:
            reader = csv.reader(file)
            entries = list(reader)[1:]  # Skip header
            print("ENTRIES FROM CSV:", entries)
    except FileNotFoundError:
        entries = []

    return render_template('progress.html', progress_data=entries)

if __name__ == '__main__':
    app.run(debug=True)





