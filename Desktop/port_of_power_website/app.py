from flask import Flask, render_template, request, redirect, url_for
import csv

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

        with open('progress_log.csv', 'a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([exercise, weight, reps])

        return redirect(url_for('progress'))

    # NEW: read the CSV file and pass it to the template
    entries = []
    try:
        with open('progress_log.csv', 'r') as file:
            reader = csv.reader(file)
            entries = list(reader)
    except FileNotFoundError:
        pass

    return render_template('progress.html', entries=entries)

if __name__ == '__main__':
    app.run(debug=True)
