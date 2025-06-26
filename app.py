from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import os
from datetime import datetime
from werkzeug.utils import secure_filename
import mysql.connector
import random
import string
import time
import requests
from io import BytesIO
import pandas as pd
from flask import make_response

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this to a secure secret key
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# MySQL Configuration
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="sheetal",
    database="seriate_attend"
)
cursor = db.cursor(dictionary=True)

# Create admin table if not exists
cursor.execute("""
CREATE TABLE IF NOT EXISTS admins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    phone VARCHAR(15) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
db.commit()

# Temporary OTP storage
otp_storage = {}

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/user')
def user():
    return render_template('user.html')

@app.route('/entry')
def entry():
    return render_template('entry.html')

@app.route('/exit')
def exit():
    return render_template('exit.html')

# ================== ENTRY FORM ==================
@app.route('/submit', methods=['POST'])
def submit():
    name = request.form['name']
    email = request.form['email']
    latitude = request.form.get('latitude', '')
    longitude = request.form.get('longitude', '')
    timestamp = datetime.now()

    image = request.files['photo']
    filename = secure_filename(f"{name}_{timestamp.strftime('%Y-%m-%d_%H-%M-%S')}.jpg")
    image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    image.save(image_path)

    query = """
        INSERT INTO attendance_entry (name, email, timestamp, latitude, longitude, photo)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    values = (name, email, timestamp, latitude, longitude, filename)
    cursor.execute(query, values)
    db.commit()

    return '''
    <div style="text-align:center; margin-top:50px;">
        <h3>✅ Thank you! Your entry has been recorded.</h3>
        <p>Have a great day ahead!</p>
    </div>
    '''
# ================== EXPORT DATA AS CSV ==================
@app.route('/admin/export-attendance')
def export_attendance():
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin_login'))

    # Get the same filter parameters as the dashboard
    name = request.args.get('name', '').strip()
    month = request.args.get('month', '')
    day = request.args.get('day', '')

    # Same query as the dashboard
    query = """
        SELECT 
            e.name,
            e.email,
            e.timestamp AS entry_time,
            x.timestamp AS exit_time,
            TIMESTAMPDIFF(HOUR, e.timestamp, x.timestamp) AS hours_worked,
            e.latitude,
            e.longitude,
            e.photo
        FROM attendance_entry e
        LEFT JOIN attendance_exit x ON 
            e.name = x.name AND 
            DATE(e.timestamp) = DATE(x.timestamp)
    """

    conditions = []
    params = []

    if name:
        conditions.append("e.name LIKE %s")
        params.append(f"%{name}%")
    if month:
        conditions.append("DATE_FORMAT(e.timestamp, '%Y-%m') = %s")
        params.append(month)
    if day:
        conditions.append("DATE(e.timestamp) = %s")
        params.append(day)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY e.timestamp DESC"
    cursor.execute(query, params)
    data = cursor.fetchall()

    # Prepare data for Excel
    excel_data = []
    for record in data:
        excel_data.append({
            'Name': record['name'],
            'Email': record['email'],
            'Entry Time': record['entry_time'].strftime('%Y-%m-%d %H:%M') if record['entry_time'] else 'N/A',
            'Exit Time': record['exit_time'].strftime('%Y-%m-%d %H:%M') if record['exit_time'] else 'N/A',
            'Hours Worked': record['hours_worked'] if record['hours_worked'] is not None else 'N/A',
            'Photo': record['photo'] if record['photo'] else 'N/A',
            'Location': f"{record['latitude']},{record['longitude']}" if record['latitude'] and record['longitude'] else 'N/A'
        })

    # Create Excel file in memory
    df = pd.DataFrame(excel_data)
    output = BytesIO()
    df.to_excel(output, index=False, sheet_name='Attendance')
    output.seek(0)

    # Create response
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    filename = f"attendance_{name or 'all'}_{month or datetime.now().strftime('%Y-%m')}.xlsx"
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    
    return response


# ================== EXIT FORM ==================
@app.route('/submit-exit', methods=['POST'])
def submit_exit():
    name = request.form['name']
    email = request.form['email']
    latitude = request.form.get('latitude', '')
    longitude = request.form.get('longitude', '')
    timestamp = datetime.now()

    image = request.files['photo']
    filename = secure_filename(f"{name}_{timestamp.strftime('%Y-%m-%d_%H-%M-%S')}.jpg")
    image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    image.save(image_path)

    query = """
        INSERT INTO attendance_exit (name, email, timestamp, latitude, longitude, photo)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    values = (name, email, timestamp, latitude, longitude, filename)
    cursor.execute(query, values)
    db.commit()

    return '''
    <div style="text-align:center; margin-top:50px;">
        <h3>✅ Thank you! Your exit has been recorded.</h3>
        <p>Good Night</p>
    </div>
    '''

# ================== ADMIN LOGIN (OTP FLOW) ==================
@app.route('/admin')
def admin_login():
    return render_template('admin_login.html')

@app.route('/admin/verify-credentials', methods=['POST'])
def verify_credentials():
    username = request.form['username']
    password = request.form['password']
    phone = request.form['phone']

    cursor.execute("SELECT * FROM admins WHERE username = %s AND phone = %s", (username, phone))
    admin = cursor.fetchone()

    if not admin:
        return jsonify({'success': False, 'message': 'Invalid credentials'})
    if password != admin['password']:
        return jsonify({'success': False, 'message': 'Invalid password'})

    otp = ''.join(random.choices(string.digits, k=6))
    otp_storage[str(admin['id'])] = {
        'otp': otp,
        'timestamp': time.time(),
        'phone': phone
    }

    print(f"OTP for admin {admin['id']}: {otp}")

    return jsonify({
        'success': True,
        'admin_id': admin['id'],
        'message': 'OTP sent to registered number'
    })

@app.route('/admin/verify-otp', methods=['POST'])
def verify_otp():
    otp = request.form['otp']
    admin_id = request.form['admin_id']

    if admin_id not in otp_storage:
        return jsonify({'success': False, 'message': 'OTP expired or invalid'})

    otp_data = otp_storage[admin_id]

    if time.time() - otp_data['timestamp'] > 300:
        del otp_storage[admin_id]
        return jsonify({'success': False, 'message': 'OTP expired'})

    if otp != otp_data['otp']:
        return jsonify({'success': False, 'message': 'Invalid OTP'})

    session['admin_logged_in'] = True
    session['admin_id'] = admin_id
    del otp_storage[admin_id]

    return jsonify({'success': True, 'redirect': url_for('admin_dashboard')})

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))

# ================== ADMIN DASHBOARD ==================
@app.route('/admin/dashboard')
def admin_dashboard():
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin_login'))

    name = request.args.get('name', '').strip()
    month = request.args.get('month', '')
    day = request.args.get('day', '')

    query = """
        SELECT 
            e.name,
            e.email,
            e.timestamp AS entry_time,
            x.timestamp AS exit_time,
            TIMESTAMPDIFF(HOUR, e.timestamp, x.timestamp) AS hours_worked,
            e.latitude,
            e.longitude,
            e.photo
        FROM attendance_entry e
        LEFT JOIN attendance_exit x ON 
            e.name = x.name AND 
            DATE(e.timestamp) = DATE(x.timestamp)
    """

    conditions = []
    params = []

    if name:
        conditions.append("e.name LIKE %s")
        params.append(f"%{name}%")
    if month:
        conditions.append("DATE_FORMAT(e.timestamp, '%Y-%m') = %s")
        params.append(month)
    if day:
        conditions.append("DATE(e.timestamp) = %s")
        params.append(day)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY e.timestamp DESC"
    cursor.execute(query, params)
    data = cursor.fetchall()

    summary = None
    if name or month:
        summary_query = """
            SELECT 
                e.name,
                DATE_FORMAT(e.timestamp, '%Y-%m') AS month,
                COUNT(DISTINCT DATE(e.timestamp)) AS days_present,
                SUM(CASE WHEN TIMESTAMPDIFF(HOUR, e.timestamp, x.timestamp) >= 8 THEN 1 ELSE 0 END) AS full_days,
                AVG(TIMESTAMPDIFF(HOUR, e.timestamp, x.timestamp)) AS avg_hours
            FROM attendance_entry e
            LEFT JOIN attendance_exit x ON 
                e.name = x.name AND 
                DATE(e.timestamp) = DATE(x.timestamp)
        """
        summary_conditions = []
        summary_params = []

        if name:
            summary_conditions.append("e.name LIKE %s")
            summary_params.append(f"%{name}%")
        if month:
            summary_conditions.append("DATE_FORMAT(e.timestamp, '%Y-%m') = %s")
            summary_params.append(month)

        if summary_conditions:
            summary_query += " WHERE " + " AND ".join(summary_conditions)

        summary_query += " GROUP BY e.name, DATE_FORMAT(e.timestamp, '%Y-%m')"
        cursor.execute(summary_query, summary_params)
        summary = cursor.fetchall()

    return render_template('admin_dashboard.html', 
                         data=data, 
                         summary=summary,
                         search_name=name,
                         search_month=month,
                         search_day=day)

# ================== MAIN ==================
if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=True)
	