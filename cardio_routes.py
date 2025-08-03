from flask import render_template, request, redirect, flash, url_for
from flask_login import login_required, current_user
from sqlalchemy import func
from datetime import datetime

def register_cardio_routes(app, db, Cardio):
    """Registers all cardio-related routes to keep app.py clean."""

    # ---------------- CARDIO DASHBOARD ----------------
    @app.route('/cardio', methods=['GET', 'POST'])
    @login_required
    def cardio():
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

        selected_activity = request.args.get('activity')
        cardio_data = Cardio.query.filter_by(user_id=current_user.id).order_by(Cardio.date.desc()).all() \
            if not selected_activity else Cardio.query.filter_by(activity=selected_activity, user_id=current_user.id).order_by(Cardio.date.desc()).all()

        activity_types = [a[0] for a in db.session.query(Cardio.activity).filter_by(user_id=current_user.id).distinct().all()]
        pr_duration = db.session.query(Cardio.activity, func.max(Cardio.duration)).filter_by(user_id=current_user.id).group_by(Cardio.activity).all()
        pr_distance = db.session.query(Cardio.activity, func.max(Cardio.distance)).filter(Cardio.user_id == current_user.id, Cardio.distance.isnot(None)).group_by(Cardio.activity).all()

        pr_durations = {a: d for a, d in pr_duration}
        pr_distances = {a: dist for a, dist in pr_distance}

        return render_template('cardio.html',
                               cardio_data=cardio_data,
                               activity_types=activity_types,
                               selected_activity=selected_activity,
                               pr_durations=pr_durations,
                               pr_distances=pr_distances)

    # ---------------- EDIT CARDIO ENTRY ----------------
    @app.route('/edit_cardio/<int:entry_id>', methods=['GET', 'POST'])
    @login_required
    def edit_cardio(entry_id):
        entry = Cardio.query.filter_by(id=entry_id, user_id=current_user.id).first()
        if not entry:
            flash("Entry not found or unauthorized.", "error")
            return redirect(url_for('cardio'))

        if request.method == 'POST':
            entry.activity = request.form['activity']
            entry.duration = float(request.form['duration'])
            entry.distance = float(request.form['distance']) if request.form['distance'] else None
            db.session.commit()
            flash("Cardio entry updated successfully!", "success")
            return redirect(url_for('cardio'))

        return render_template('edit_cardio.html', entry=entry)

    # ---------------- DELETE CARDIO ENTRY ----------------
    @app.route('/delete_cardio/<int:entry_id>', methods=['POST'])
    @login_required
    def delete_cardio(entry_id):
        entry = Cardio.query.filter_by(id=entry_id, user_id=current_user.id).first()
        if entry:
            db.session.delete(entry)
            db.session.commit()
            flash("Cardio entry deleted successfully!", "success")
        else:
            flash("Entry not found or unauthorized.", "error")
        return redirect(url_for('cardio'))
