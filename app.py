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
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this to a secure secret key
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# MySQL Configuration
import mysql.connector

conn = mysql.connector.connect(
    host='sql12.freesqldatabase.com',
    user='sql12788853',
    password='LqPq3FNXYT',
    database='sql12788853',
    port=3306
)
cursor = conn.cursor(dictionary=True)


def send_email_otp(to_email, otp):
    from_email = 'seriate001archana@gmail.com'  # Replace with yours
    from_password = 'wyyf gduw ulql vpqz '  # Use Gmail App Password

    msg = MIMEText(f"Your OTP for admin login is: {otp}")
    msg['Subject'] = 'Admin OTP Verification'
    msg['From'] = from_email
    msg['To'] = to_email

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(from_email, from_password)
        server.send_message(msg)
        server.quit()
        print("✅ OTP sent to email.")
    except Exception as e:
        print("❌ Failed to send OTP email:", e)

def send_attendance_report_email(data, filters):
    """Send attendance report as Excel attachment via email"""
    from_email = 'seriate001archana@gmail.com'
    from_password = 'wyyf gduw ulql vpqz '
    to_email = 'seriate001archana@gmail.com'  # Send to the same email
    
    try:
        # Create Excel file in memory
        excel_data = []
        for record in data:
            excel_data.append({
                'Name': record['name'],
                'Email': record['email'],
                'Entry Time': record['entry_time'].strftime('%Y-%m-%d %H:%M') if record['entry_time'] else 'N/A',
                'Exit Time': record['exit_time'].strftime('%Y-%m-%d %H:%M') if record['exit_time'] else 'N/A',
                'Hours Worked': record['hours_worked'] if record['hours_worked'] is not None else 'N/A',
                'Entry Photo': record['entry_photo'] if record['entry_photo'] else 'N/A',
                'Exit Photo': record['exit_photo'] if record['exit_photo'] else 'N/A',
                'Entry Location': f"{record['entry_latitude']},{record['entry_longitude']}" if record['entry_latitude'] and record['entry_longitude'] else 'N/A',
                'Exit Location': f"{record['exit_latitude']},{record['exit_longitude']}" if record['exit_latitude'] and record['exit_longitude'] else 'N/A'
            })
        
        df = pd.DataFrame(excel_data)
        excel_buffer = BytesIO()
        df.to_excel(excel_buffer, index=False, sheet_name='Attendance Report')
        excel_buffer.seek(0)
        
        # Create email message
        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Subject'] = f'Attendance Report - {datetime.now().strftime("%Y-%m-%d %H:%M")}'
        
        # Email body
        filter_info = []
        if filters.get('name'):
            filter_info.append(f"Name: {filters['name']}")
        if filters.get('month'):
            filter_info.append(f"Month: {filters['month']}")
        if filters.get('day'):
            filter_info.append(f"Day: {filters['day']}")
        if filters.get('start_date'):
            filter_info.append(f"Start Date: {filters['start_date']}")
        if filters.get('end_date'):
            filter_info.append(f"End Date: {filters['end_date']}")
        
        filter_text = "\n".join(filter_info) if filter_info else "No filters applied"
        
        body = f"""
        Dear Admin,

        Please find attached the attendance report generated on {datetime.now().strftime('%Y-%m-%d at %H:%M')}.

        Report Details:
        - Total Records: {len(data)}
        - Filters Applied:
        {filter_text}

        The report contains the following information:
        - Employee names and emails
        - Entry and exit times
        - Hours worked
        - Photo references
        - Location coordinates

        Best regards,
        Attendance Management System
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Attach Excel file
        filename = f"attendance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(excel_buffer.getvalue())
        encoders.encode_base64(part)
        part.add_header(
            'Content-Disposition',
            f'attachment; filename= {filename}'
        )
        msg.attach(part)
        
        # Send email
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(from_email, from_password)
        text = msg.as_string()
        server.sendmail(from_email, to_email, text)
        server.quit()
        
        return True, f"Report sent successfully to {to_email}"
        
    except Exception as e:
        print(f"❌ Failed to send attendance report email: {e}")
        return False, f"Failed to send report: {str(e)}"

# Function to calculate storage statistics
def calculate_storage_stats():
    try:
        # Get all entry photos from database
        cursor.execute("SELECT photo FROM attendance_entry WHERE photo IS NOT NULL AND photo != ''")
        entry_photos = cursor.fetchall()
        
        # Get all exit photos from database
        cursor.execute("SELECT photo FROM attendance_exit WHERE photo IS NOT NULL AND photo != ''")
        exit_photos = cursor.fetchall()
        
        entry_count = len(entry_photos)
        exit_count = len(exit_photos)
        total_files = entry_count + exit_count
        
        # Calculate total file size
        total_size = 0
        upload_folder = app.config['UPLOAD_FOLDER']
        
        # Calculate size of entry photos
        for photo in entry_photos:
            file_path = os.path.join(upload_folder, photo['photo'])
            if os.path.exists(file_path):
                total_size += os.path.getsize(file_path)
        
        # Calculate size of exit photos  
        for photo in exit_photos:
            file_path = os.path.join(upload_folder, photo['photo'])
            if os.path.exists(file_path):
                total_size += os.path.getsize(file_path)
        
        # Convert bytes to MB
        total_size_mb = round(total_size / (1024 * 1024), 2)
        
        return {
            'total_files': total_files,
            'total_size_mb': total_size_mb,
            'entry_files': entry_count,
            'exit_files': exit_count
        }
    except Exception as e:
        print(f"Error calculating storage stats: {e}")
        return {
            'total_files': 0,
            'total_size_mb': 0,
            'entry_files': 0,
            'exit_files': 0
        }

# Create admin table if not exists
cursor.execute("""
CREATE TABLE IF NOT EXISTS admins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    email VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()


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
    filename = secure_filename(f"{name}_entry_{timestamp.strftime('%Y-%m-%d_%H-%M-%S')}.jpg")
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

# ================== EXIT FORM ==================
@app.route('/submit-exit', methods=['POST'])
def submit_exit():
    name = request.form['name']
    email = request.form['email']
    latitude = request.form.get('latitude', '')
    longitude = request.form.get('longitude', '')
    timestamp = datetime.now()

    image = request.files['photo']
    filename = secure_filename(f"{name}_exit_{timestamp.strftime('%Y-%m-%d_%H-%M-%S')}.jpg")
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

# ================== EMAIL REPORT ENDPOINT ==================
@app.route('/admin/email-report', methods=['POST'])
def email_report():
    if 'admin_logged_in' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'})
    
    try:
        # Get filter parameters from request
        data = request.json
        filters = {
            'name': data.get('name', ''),
            'month': data.get('month', ''),
            'day': data.get('day', ''),
            'start_date': data.get('start_date', ''),
            'end_date': data.get('end_date', '')
        }
        
        # Build the same query as dashboard
        query = """
            SELECT 
                e.name,
                e.email,
                e.timestamp AS entry_time,
                x.timestamp AS exit_time,
                TIMESTAMPDIFF(HOUR, e.timestamp, x.timestamp) AS hours_worked,
                e.latitude AS entry_latitude,
                e.longitude AS entry_longitude,
                x.latitude AS exit_latitude,
                x.longitude AS exit_longitude,
                e.photo AS entry_photo,
                x.photo AS exit_photo
            FROM attendance_entry e
            LEFT JOIN attendance_exit x ON 
                e.name = x.name AND 
                DATE(e.timestamp) = DATE(x.timestamp)
        """
        
        conditions = []
        params = []
        
        if filters['name']:
            conditions.append("e.name LIKE %s")
            params.append(f"%{filters['name']}%")
        if filters['month']:
            conditions.append("DATE_FORMAT(e.timestamp, '%Y-%m') = %s")
            params.append(filters['month'])
        if filters['day']:
            conditions.append("DATE(e.timestamp) = %s")
            params.append(filters['day'])
        if filters['start_date']:
            conditions.append("DATE(e.timestamp) >= %s")
            params.append(filters['start_date'])
        if filters['end_date']:
            conditions.append("DATE(e.timestamp) <= %s")
            params.append(filters['end_date'])
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY e.timestamp DESC"
        cursor.execute(query, params)
        filtered_data = cursor.fetchall()
        
        # Send email with report
        success, message = send_attendance_report_email(filtered_data, filters)
        
        return jsonify({
            'success': success,
            'message': message,
            'records_count': len(filtered_data)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error sending email report: {str(e)}'
        })

# ================== STORAGE STATS API ==================
@app.route('/admin/storage-stats')
def storage_stats():
    if 'admin_logged_in' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'})
    
    try:
        stats = calculate_storage_stats()
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })

# ================== DELETE SINGLE IMAGE ==================
@app.route('/admin/delete-image', methods=['POST'])
def delete_image():
    if 'admin_logged_in' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'})
    
    try:
        data = request.json
        filename = data.get('filename')
        image_type = data.get('type')  # 'entry' or 'exit'
        employee_name = data.get('employee_name')
        entry_date = data.get('entry_date')
        
        # Delete from filesystem
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # Update database to remove photo reference
        if image_type == 'entry':
            cursor.execute("""
                UPDATE attendance_entry 
                SET photo = NULL 
                WHERE photo = %s AND name = %s AND DATE(timestamp) = %s
            """, (filename, employee_name, entry_date))
        else:  # exit
            cursor.execute("""
                UPDATE attendance_exit 
                SET photo = NULL 
                WHERE photo = %s AND name = %s AND DATE(timestamp) = %s
            """, (filename, employee_name, entry_date))
        
        db.commit()
        
        return jsonify({
            'success': True,
            'message': f'{image_type.capitalize()} photo deleted successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })

# ================== BULK DELETE IMAGES ==================
@app.route('/admin/bulk-delete-images', methods=['POST'])
def bulk_delete_images():
    if 'admin_logged_in' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'})
    
    try:
        data = request.json
        delete_type = data.get('delete_type')  # 'entry', 'exit', or 'both'
        
        deleted_count = 0
        
        if delete_type == 'entry' or delete_type == 'both':
            # Get all entry photos
            cursor.execute("SELECT photo FROM attendance_entry WHERE photo IS NOT NULL AND photo != ''")
            entry_photos = cursor.fetchall()
            
            for photo in entry_photos:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], photo['photo'])
                if os.path.exists(file_path):
                    os.remove(file_path)
                    deleted_count += 1
            
            # Update database
            cursor.execute("UPDATE attendance_entry SET photo = NULL WHERE photo IS NOT NULL")
        
        if delete_type == 'exit' or delete_type == 'both':
            # Get all exit photos
            cursor.execute("SELECT photo FROM attendance_exit WHERE photo IS NOT NULL AND photo != ''")
            exit_photos = cursor.fetchall()
            
            for photo in exit_photos:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], photo['photo'])
                if os.path.exists(file_path):
                    os.remove(file_path)
                    deleted_count += 1
            
            # Update database
            cursor.execute("UPDATE attendance_exit SET photo = NULL WHERE photo IS NOT NULL")
        
        db.commit()
        
        return jsonify({
            'success': True,
            'message': f'Successfully deleted {deleted_count} images'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })

# ================== EXPORT DATA AS CSV ==================
@app.route('/admin/export-attendance')
def export_attendance():
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin_login'))

    # Get the same filter parameters as the dashboard
    name = request.args.get('name', '').strip()
    month = request.args.get('month', '')
    day = request.args.get('day', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    # Updated query to include separate entry and exit locations
    query = """
        SELECT 
            e.name,
            e.email,
            e.timestamp AS entry_time,
            x.timestamp AS exit_time,
            TIMESTAMPDIFF(HOUR, e.timestamp, x.timestamp) AS hours_worked,
            e.latitude AS entry_latitude,
            e.longitude AS entry_longitude,
            x.latitude AS exit_latitude,
            x.longitude AS exit_longitude,
            e.photo AS entry_photo,
            x.photo AS exit_photo
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
    if start_date:
        conditions.append("DATE(e.timestamp) >= %s")
        params.append(start_date)
    if end_date:
        conditions.append("DATE(e.timestamp) <= %s")
        params.append(end_date)

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
            'Entry Photo': record['entry_photo'] if record['entry_photo'] else 'N/A',
            'Exit Photo': record['exit_photo'] if record['exit_photo'] else 'N/A',
            'Entry Location': f"{record['entry_latitude']},{record['entry_longitude']}" if record['entry_latitude'] and record['entry_longitude'] else 'N/A',
            'Exit Location': f"{record['exit_latitude']},{record['exit_longitude']}" if record['exit_latitude'] and record['exit_longitude'] else 'N/A'
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

# ================== ADMIN LOGIN (OTP FLOW) ==================
@app.route('/admin')
def admin_login():
    return render_template('admin_login.html')

@app.route('/admin/verify-credentials', methods=['POST'])
def verify_credentials():
    username = request.form['username']
    password = request.form['password']
    email = request.form['email']
    cursor.execute("SELECT * FROM admins WHERE username = %s AND email = %s", (username, email))

    admin = cursor.fetchone()

    if not admin:
        return jsonify({'success': False, 'message': 'Invalid credentials'})
    if password != admin['password']:
        return jsonify({'success': False, 'message': 'Invalid password'})

    otp = ''.join(random.choices(string.digits, k=6))
    otp_storage[str(admin['id'])] = {
        'otp': otp,
        'timestamp': time.time()
    }

    send_email_otp(email, otp)
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
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    # Updated query to include separate entry and exit locations
    query = """
        SELECT 
            e.name,
            e.email,
            e.timestamp AS entry_time,
            x.timestamp AS exit_time,
            TIMESTAMPDIFF(HOUR, e.timestamp, x.timestamp) AS hours_worked,
            e.latitude AS entry_latitude,
            e.longitude AS entry_longitude,
            x.latitude AS exit_latitude,
            x.longitude AS exit_longitude,
            e.photo AS entry_photo,
            x.photo AS exit_photo
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
    if start_date:
        conditions.append("DATE(e.timestamp) >= %s")
        params.append(start_date)
    if end_date:
        conditions.append("DATE(e.timestamp) <= %s")
        params.append(end_date)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY e.timestamp DESC"
    cursor.execute(query, params)
    data = cursor.fetchall()

    # Calculate storage statistics
    storage_stats = calculate_storage_stats()

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
                         storage_stats=storage_stats,
                         search_name=name,
                         search_month=month,
                         search_day=day,
                         search_start_date=start_date,
                         search_end_date=end_date)

# ================== MAIN ==================
if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=True)