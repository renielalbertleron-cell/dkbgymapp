from flask import (
    Flask, g, render_template, request, redirect,
    url_for, send_from_directory, Response
)
from werkzeug.utils import secure_filename
from datetime import datetime, date, timedelta
import sqlite3
import os
import csv
from io import StringIO
from flask import send_file
import pandas as pd
from io import BytesIO
from flask import request, jsonify
import sqlite3, json


# Setup
app = Flask(__name__)
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
DB = 'gym.db'

# Database Connection
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exc=None):
    db = g.pop('db', None)
    if db: db.close()

# Filters
@app.template_filter('to_date')
def to_date(val):
    if isinstance(val, str):
        return datetime.fromisoformat(val).date()
    elif isinstance(val, datetime):
        return val.date()
    elif isinstance(val, date):
        return val
    return date.today()

@app.template_filter('days_left')
def days_left(exp):
    d = to_date(exp)
    return max((d - date.today()).days, 0)

# Routes
from datetime import timedelta

# import necessary at top

@app.route('/')
def home():
    db = get_db()
    # date ranges
    today = date.today()
    week_ago = (today - timedelta(days=7)).isoformat()
    month_ago = (today - timedelta(days=30)).isoformat()
    today_iso = today.isoformat()
    
    # overall counts
    total_members = db.execute('SELECT COUNT(*) FROM members').fetchone()[0]
    active_memberships = db.execute(
        'SELECT COUNT(*) FROM members WHERE membership_expiration >= ?', (today_iso,)
    ).fetchone()[0]
    
    # sales breakdown
    def sum_sales(date_from):
        row = db.execute(
            'SELECT buyer_type, SUM(total) AS sum_total FROM sales WHERE date >= ? GROUP BY buyer_type',
            (date_from,)
        ).fetchall()
        return {r['buyer_type']: r['sum_total'] or 0 for r in row}
    
    daily = sum_sales(today_iso)
    weekly = sum_sales(week_ago)
    monthly = sum_sales(month_ago)
    
    product_sales = db.execute(
        'SELECT p.name, SUM(s.qty) AS sold, SUM(s.total) AS revenue '
        'FROM sales s JOIN products p ON s.product_id=p.id WHERE s.date >= ? '
        'GROUP BY p.id',
        (week_ago,)
    ).fetchall()
    
    return render_template('home.html',
                           total_members=total_members,
                           active_memberships=active_memberships,
                           daily=daily,
                           weekly=weekly,
                           monthly=monthly,
                           product_sales=product_sales,
                           today=today_iso)

@app.route('/members')
def members():
    rows = get_db().execute('SELECT * FROM members').fetchall()
    return render_template('members.html', members=rows)

@app.route('/process_rfid', methods=['POST'])
def process_rfid():
    db = get_db()
    data = request.get_json()
    rfid = data.get('rfid')
    if not rfid:
        return jsonify({ 'message': '🚫 No RFID provided' }), 400

    member = db.execute('SELECT * FROM members WHERE rfid = ?', (rfid,)).fetchone()
    if not member:
        return jsonify({ 'message': f'❌ Unknown RFID: {rfid}. Access denied.' }), 404

    name = f"{member['first_name']} {member['last_name']}"
    today = datetime.now().date().isoformat()
    record = db.execute('''
        SELECT * FROM attendance 
        WHERE rfid = ? AND date(login_time) = ?
        ORDER BY login_time DESC
        LIMIT 1
    ''', (rfid, today)).fetchone()

    now = datetime.now().isoformat(timespec='seconds')
    msg = ""

    if not record:
        db.execute('INSERT INTO attendance (rfid, login_time) VALUES (?, ?)', (rfid, now))
        msg = f'✅ Login recorded for {name}'
    else:
        login = datetime.fromisoformat(record['login_time'])
        if record['logout_time'] is None and (datetime.now() - login).total_seconds() >= 3600:
            db.execute('UPDATE attendance SET logout_time = ? WHERE id = ?', (now, record['id']))
            msg = f'✅ Logout recorded for {name}'
        else:
            msg = f'⚠ Duplicate tap ignored'

    db.commit()
    return jsonify({ 'message': msg })

@app.route('/attendance_report')
def attendance_report():
    db = get_db()
    rows = db.execute('''
        SELECT a.rfid, m.first_name || ' ' || m.last_name AS name,
               a.login_time, a.logout_time
        FROM attendance a
        LEFT JOIN members m ON m.rfid = a.rfid
        ORDER BY a.login_time DESC
    ''').fetchall()
    return render_template('attendance_report.html', attendance=rows)


@app.route('/export_attendance')
def export_attendance():
    db = get_db()
    rows = db.execute('''
        SELECT a.rfid, m.first_name || ' ' || m.last_name AS name,
               a.login_time, a.logout_time
        FROM attendance a
        LEFT JOIN members m ON m.rfid = a.rfid
        ORDER BY a.login_time DESC
    ''').fetchall()
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['RFID', 'Name', 'Login Time', 'Logout Time'])
    for r in rows:
        cw.writerow([r['rfid'], r['name'], r['login_time'], r['logout_time'] or '-'])
    return Response(si.getvalue(), mimetype='text/csv',
                    headers={"Content-Disposition": "attachment;filename=attendance.csv"})

@app.route('/erase_attendance_today', methods=['POST'])
def erase_attendance_today():
    db = get_db()
    today = date.today().isoformat()
    db.execute("DELETE FROM attendance WHERE date(login_time) = ?", (today,))
    db.commit()
    return redirect(url_for('attendance_report'))


@app.route('/membership_purchases', methods=['GET', 'POST'])
def membership_purchases():
    db = get_db()
    members = db.execute('SELECT * FROM members').fetchall()
    selected = None
    message = None
    today = date.today().isoformat()

    if request.method == 'POST':
        # Case: selecting from dropdown
        if 'rfid_select' in request.form and request.form['rfid_select']:
            selected = db.execute('SELECT * FROM members WHERE rfid = ?', (request.form['rfid_select'],)).fetchone()
            return render_template('membership_purchases.html', members=members, selected=selected, today=today)

        # Case: processing purchase
        rfid = (request.form.get('rfid_manual') or '').strip()
        plan = request.form['plan']
        payment = request.form['payment_method']
        start = datetime.fromisoformat(request.form['start_date']).date()
        durations = {'weekly': 7, 'monthly': 30, 'yearly': 365}
        exp = start + timedelta(days=durations[plan])

        member = db.execute('SELECT * FROM members WHERE rfid = ?', (rfid,)).fetchone()
        if not member:
            message = f'❌ No member found with RFID {rfid}'
        else:
            db.execute('''
                UPDATE members
                SET membership_expiration = ?, membership_status = ?
                WHERE rfid = ?
            ''', (exp.isoformat(), 'Active', rfid))
            db.commit()
            message = f'✅ Membership for {member["first_name"]} expires on {exp.isoformat()}'

        return render_template('membership_purchases.html', members=members, selected=member, message=message, today=today)

    return render_template('membership_purchases.html', members=members, today=today)

@app.route('/products')
def products():
    rows = get_db().execute('SELECT * FROM products').fetchall()
    return render_template('products.html', products=rows)

@app.route('/sales', methods=['GET'])
def sales():
    db = get_db()
    products = db.execute('SELECT * FROM products').fetchall()
    return render_template('sales.html', products=products)

@app.route('/complete_sale', methods=['POST'])
def complete_sale():
    db = get_db()
    cart = json.loads(request.form['cart_data'])

    # Get buyer type (either 'walk-in', 'member', etc), default is 'walk-in'
    buyer = request.form.get('buyer_type', 'walk-in').strip().lower()
    today = date.today().isoformat()

    sale_ids = []
    for item in cart:
        db.execute(
            '''
            INSERT INTO sales (product_id, qty, total, date, buyer_type)
            VALUES (?, ?, ?, ?, ?)
            ''',
            (item['id'], item['qty'], item['sub'], today, buyer)
        )
        sale_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        sale_ids.append(str(sale_id))

        db.execute(
            'UPDATE products SET stock = stock - ? WHERE id = ?',
            (item['qty'], item['id'])
        )

    db.commit()
    return redirect(url_for('receipt', ids=",".join(sale_ids)))

@app.route('/receipt/<ids>')
def receipt(ids):
    db = get_db()
    sale_ids = [int(x) for x in ids.split(',')]
    placeholder = ",".join("?" for _ in sale_ids)

    sales = db.execute(f'''
        SELECT s.id, s.qty, s.total, s.date, p.name as product_name
        FROM sales s
        JOIN products p ON s.product_id = p.id
        WHERE s.id IN ({placeholder})
        ORDER BY s.id
    ''', sale_ids).fetchall()

    if not sales:
        return "❌ No sales found.", 404

    total_sum = sum([s['total'] for s in sales])
    tx_date = sales[0]['date']

    return render_template('receipt.html', sales=sales, total=total_sum, date=tx_date)

@app.route('/sales_records')
def sales_records():
    rows = get_db().execute('''
        SELECT s.id, p.name, s.qty, s.total, s.date
        FROM sales s
        JOIN products p ON p.id = s.product_id
    ''').fetchall()
    return render_template('sales_records.html', sales_records=rows)

@app.route('/inventory')
def inventory():
    rows = get_db().execute('SELECT name, stock, 5 as reorder FROM products').fetchall()
    return render_template('inventory.html', inventory=rows)



@app.route('/sales_report')
def sales_report():
    return render_template('sales_report.html')

# Members Management
@app.route('/add_member', methods=['GET', 'POST'])
def add_member():
    db = get_db()
    if request.method == 'POST':
        data = request.form
        db.execute('''
            INSERT INTO members (rfid, first_name, middle_name, last_name, birthday, last_visit)
            VALUES (?, ?, ?, ?, ?, NULL)
        ''', (
            data['rfid'],
            data['first_name'],
            data.get('middle_name', ''),
            data['last_name'],
            data['birthday']
        ))
        db.commit()

        # Handle photo upload if provided
        photo = request.files.get('photo')
        if photo and photo.filename:
            filename = secure_filename(photo.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            photo.save(filepath)
            db.execute('UPDATE members SET picture = ? WHERE rfid = ?', (filename, data['rfid']))
            db.commit()

        return redirect(url_for('members'))

    return render_template('add_member.html')

@app.route('/upload_photo/<rfid>', methods=['POST'])
def upload_photo(rfid):
    file = request.files['photo']
    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        db = get_db()
        db.execute('UPDATE members SET picture = ? WHERE rfid = ?', (filename, rfid))
        db.commit()
    return redirect(url_for('members'))

@app.route('/export_members')
def export_members():
    db = get_db()
    members = db.execute('SELECT * FROM members').fetchall()
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(members[0].keys())  # headers
    for m in members:
        cw.writerow([m[k] for k in m.keys()])
    return Response(si.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=members.csv"})

@app.route('/uploaded/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/view_member/<rfid>')
def view_member(rfid):
    m = get_db().execute('SELECT * FROM members WHERE rfid = ?', (rfid,)).fetchone()
    return render_template('view_member.html', m=m)

@app.route('/edit_member/<rfid>', methods=['GET', 'POST'])
def edit_member(rfid):
    db = get_db()
    if request.method == 'POST':
        data = request.form
        db.execute('''
            UPDATE members
            SET first_name=?, middle_name=?, last_name=?, birthday=?
            WHERE rfid=?
        ''', (
            data['first_name'],
            data.get('middle_name', ''),
            data['last_name'],
            data['birthday'],
            rfid
        ))
        db.commit()
        return redirect(url_for('members'))

    m = db.execute('SELECT * FROM members WHERE rfid = ?', (rfid,)).fetchone()
    return render_template('edit_member.html', m=m)

@app.route('/delete_member/<rfid>', methods=['POST'])
def delete_member(rfid):
    db = get_db()
    db.execute('DELETE FROM members WHERE rfid = ?', (rfid,))
    db.commit()
    return redirect(url_for('members'))

# Edit single product
@app.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    db = get_db()
    if request.method == 'POST':
        data = request.form
        db.execute('UPDATE products SET name=?, price=?, stock=? WHERE id=?',
                   (data['name'], float(data['price']), int(data['stock']), product_id))
        db.commit()
        return redirect(url_for('products'))

    p = db.execute('SELECT * FROM products WHERE id=?', (product_id,)).fetchone()
    return render_template('edit_product.html', p=p)

# Download Excel template
@app.route('/download_product_template')
def download_product_template():
    df = pd.DataFrame(columns=['name', 'price', 'stock'])
    bio = BytesIO()
    df.to_excel(bio, index=False)
    bio.seek(0)
    return send_file(bio, download_name='product_template.xlsx', as_attachment=True)

# Import batch products
@app.route('/import_products', methods=['POST'])
def import_products():
    file = request.files.get('file')
    if not file:
        return redirect(url_for('products'))

    df = pd.read_excel(file)
    db = get_db()
    for index, row in df.iterrows():
        name, price, stock = row['name'], float(row['price']), int(row['stock'])
        db.execute('''
            INSERT INTO products (name, price, stock)
            VALUES (?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET price=excluded.price, stock=excluded.stock
        ''', (name, price, stock))
    db.commit()
    return redirect(url_for('products'))




# App Runner
if __name__ == '__main__':
    app.run(debug=True)
