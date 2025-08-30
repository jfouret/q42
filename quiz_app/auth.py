from flask import Blueprint, request, jsonify, render_template, redirect, url_for, current_app
from flask_jwt_extended import create_access_token, set_access_cookies, unset_jwt_cookies

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == current_app.config['AUTH_PASSWORD']:
            access_token = create_access_token(identity="user", expires_delta=False)
            response = redirect(url_for('main.index'))
            set_access_cookies(response, access_token)
            return response
        else:
            return render_template('login.html', error='Invalid password')
    return render_template('login.html')

@auth_bp.route('/logout', methods=['POST'])
def logout():
    response = redirect(url_for('auth.login'))
    unset_jwt_cookies(response)
    return response
