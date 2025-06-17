from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, abort, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

app = Flask(__name__)
import os
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'a-very-long-random-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

from enum import Enum
from sqlalchemy import Enum as SqlEnum

class GenderEnum(Enum):
    MALE = 'male'
    FEMALE = 'female'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    middle_name = db.Column(db.String(50), nullable=False)
    birth_date = db.Column(db.String(10), nullable=False)
    telegram = db.Column(db.String(100))
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    ticket_status = db.Column(db.String(50), default="not_paid")
    is_admin = db.Column(db.Boolean, default=False)
    gender = db.Column(SqlEnum(GenderEnum), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admins')
def admins():
    return render_template('admins.html')

@app.route('/become_sponsor')
def become_sponsor():
    return render_template('become_sponsor.html')
@app.route('/contacts')
def contacts():
    return render_template('contacts.html')
@app.route('/merch')
def merch():
    return render_template('merch.html')
@app.route('/no_event')
def no_event():
    return render_template('no_event.html')

@app.route('/event/')
def event_page():
    return render_template('event/event_page.html')

@app.route('/event/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        middle_name = request.form['middle_name']
        birth_date = request.form['birth_date']
        telegram = request.form['telegram']
        username = request.form['username']
        gender_value = request.form['gender']
        raw_password = request.form['password']

        if len(username) < 6:
            flash("Логин должен быть не короче 6 символов")
            return redirect(url_for('register'))

        if len(raw_password) < 8:
            flash("Пароль должен быть не короче 8 символов")
            return redirect(url_for('register'))

            # ✅ Преобразуем строку в Enum
        try:
            gender = GenderEnum(gender_value)
        except ValueError:
            flash("Неверно выбран пол")
            return redirect(url_for('register'))

        password = generate_password_hash(request.form['password'], method='pbkdf2:sha256')
        new_user = User(
            first_name=first_name,
            last_name=last_name,
            middle_name=middle_name,
            birth_date=birth_date,
            telegram=telegram,
            username=username,
            password=password,
            gender=gender,
        )

        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('login'))

    return render_template('event/register.html')


@app.route('/event/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            error = "Неверное имя пользователя или пароль"
            return render_template('event/login.html', error=error)
    return render_template('event/login.html')

@app.route('/event/dashboard')
@login_required
def dashboard():
    return render_template('event/dashboard.html')

import qrcode
import os

from datetime import datetime

def calculate_age(birth_date_str):
    try:
        birth_date = datetime.strptime(birth_date_str, "%Y-%m-%d")
    except ValueError:
        return 0  # если дата записана неверно
    today = datetime.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

@app.route('/event/buy_ticket')
@login_required
def buy_ticket():
    age = calculate_age(current_user.birth_date)
    if age < 18 or age > 30:
        return render_template("event/underage.html", age=age)

    if current_user.ticket_status == 'paid':
        return "Билет уже куплен."

    qr_dir = os.path.join('static', 'qrcodes')
    os.makedirs(qr_dir, exist_ok=True)

    qr_data = f"https://sueta-taiq.onrender.com/ticket_status/{current_user.id}"
    img = qrcode.make(qr_data)
    qr_path = os.path.join(qr_dir, f"user_{current_user.id}.png")
    img.save(qr_path)

    return render_template("event/buy_ticket.html",
                           tg="@Alyaskablya",  # замени на свой Telegram
                           amount="25 AZN",
                           qr_image=url_for('static', filename=f'qrcodes/user_{current_user.id}.png'))

@app.route('/event/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('event_page'))

@app.route('/event/ticket_status/<int:user_id>')
@admin_required
def ticket_status(user_id):
    user = User.query.get(user_id)
    if not user:
        return "Пользователь не найден"

    return render_template("event/admin/ticket_status.html", user=user)

@app.route('/event/confirm_payment/<int:user_id>', methods=['POST'])
@admin_required
def confirm_payment(user_id):
    user = User.query.get(user_id)
    if user:
        user.ticket_status = 'paid'
        db.session.commit()
    return redirect(url_for('ticket_status', user_id=user_id))

@app.route('/event/reject_payment/<int:user_id>', methods=['POST'])
@admin_required
def reject_payment(user_id):
    user = User.query.get(user_id)
    if user:
        user.ticket_status = 'rejected'
        db.session.commit()
    return redirect(url_for('ticket_status', user_id=user_id))


@app.route('/event/admin/users')
@admin_required
def admin_user_list():
    status_filter = request.args.get('status')

    if status_filter:
        users = User.query.filter_by(ticket_status=status_filter).all()
    else:
        users = User.query.all()

    return render_template('event/admin/admin_users.html', users=users, status_filter=status_filter)

@app.route('/event/party_menu')
def party_menu():
    return render_template('/event/party_menu.html')
@app.route('/event/party_menu/food')
def food():
    return render_template('/event/menu/food.html')
@app.route('/event/party_menu/drink')
def drink():
    return render_template('/event/menu/drink.html')
@app.route('/event/party_menu/snack')
def snack():
    return render_template('/event/menu/snack.html')
@app.route('/event/party_menu/alcohol')
def alcohol():
    return render_template('/event/menu/alcohol.html')
@app.route('/event/party_menu/sous')
def sous():
    return render_template('/event/menu/sous.html')
@app.route('/event/party_menu/shisha')
def shisha():
    return render_template('/event/menu/shisha.html')
@app.route('/event/party_menu/sets')
def sets():
    return render_template('/event/menu/sets.html')
@app.route('/event/terms')
def terms():
    return render_template('/event/terms.html')

@app.errorhandler(403)
def forbidden(e):
    return render_template('/event/403.html'), 403

@app.errorhandler(404)
def notfound(e):
    return render_template('404.html'), 404

from flask import send_file, request
import io
from openpyxl import Workbook


@app.route('/export_excel')
@admin_required
def export_excel():
    status_filter = request.args.get('status', '')

    # Получаем пользователей с нужным фильтром (в вашем случае, например, из базы)
    if status_filter == 'paid':
        users = User.query.filter_by(ticket_status='paid').all()
    elif status_filter == 'not_paid':
        users = User.query.filter_by(ticket_status='not_paid').all()
    elif status_filter == 'rejected':
        users = User.query.filter_by(ticket_status='rejected').all()
    else:
        users = User.query.all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Пользователи"

    # Заголовки
    headers = ["ID", "ФИО", "Дата рождения", "Telegram", "Статус"]
    ws.append(headers)

    # Данные пользователей
    for user in users:
        full_name = f"{user.last_name} {user.first_name} {user.middle_name}"
        status_text = {
            'paid': 'Оплачен',
            'not_paid': 'Не оплачен',
            'rejected': 'Отклонён'
        }.get(user.ticket_status, '-')
        ws.append([user.id, full_name, str(user.birth_date), user.telegram or '-', status_text])

    # Внизу добавляем общую сумму
    # Считаем количество оплаченных пользователей
    paid_count = sum(1 for user in users if user.ticket_status == 'paid')
    total_money = paid_count * 25  # 25 манат с пользователя

    ws.append([])  # пустая строка
    ws.append(["", "", "", "Итого заработано (манат):", total_money])

    # Сохраняем в буфер
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="users.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=False, host='0.0.0.0')

