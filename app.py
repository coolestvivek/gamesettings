"""
Mani 272 - UID Management System
Integrated Discord Bot + Web Dashboard
Owner + Reseller system with UID name tracking
Optimized for Azure B1s deployment
"""

import os
import sys
import asyncio
import json
import time
from datetime import datetime, timedelta
from threading import Thread

# Flask imports
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

# Discord imports
import discord
from discord import app_commands
from typing import Literal

# ==================== CONFIGURATION ====================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Discord Authorization - Add authorized Discord user IDs here
AUTHORIZED_DISCORD_IDS = [
    711623890438324296,  # Owner/Admin Discord ID
]

# Flask Configuration
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'cgxregedit-uid-secret-2024')
app.config['SESSION_COOKIE_SECURE'] = False  # Set True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)

# Database
db_dir = os.path.join(BASE_DIR, 'database')
os.makedirs(db_dir, exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(db_dir, "cgxregedit.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Security Headers
@app.after_request
def set_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com;"
    return response

# Discord Config
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN', '')
WEBHOOK_URL = 'https://discord.com/api/webhooks/1443536928174510171/mbFPRlLOtrNLjG_hrb72mULYKBc6QmyNEiTi4inBDAU4NldsnBvGBKgRYQReHPiur3NR'

# Regions
REGIONS = ["IND", "ID", "BR", "ME", "VN", "TH", "CIS", "BD", "PK", "SG", "NA", "SAC", "EU", "TW"]
WHITELIST_DIR = os.path.join(BASE_DIR, "whitelists")
os.makedirs(WHITELIST_DIR, exist_ok=True)

# ==================== DATABASE MODELS ====================

class User(db.Model):
    """User: Owner (unlimited) or Reseller (with credits)"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'owner' or 'reseller'
    credits = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    uids = db.relationship('UIDEntry', backref='owner', lazy='dynamic', foreign_keys='UIDEntry.added_by')
    
    def is_owner(self):
        return self.role == 'owner'
    
    def has_credits(self, amount):
        return self.is_owner() or self.credits >= amount


class UIDEntry(db.Model):
    """UID with name, region, duration"""
    id = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.String(50), nullable=False, index=True)
    uid_name = db.Column(db.String(100), nullable=False)  # Name of UID owner
    region = db.Column(db.String(10), nullable=False)
    
    added_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    added_via = db.Column(db.String(20), default='web')  # 'web' or 'discord'
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    duration_days = db.Column(db.Integer, nullable=False)
    
    is_active = db.Column(db.Boolean, default=True)
    credits_used = db.Column(db.Float, default=0.0)
    
    def days_remaining(self):
        if not self.is_active:
            return 0
        delta = self.expires_at - datetime.utcnow()
        return max(0, delta.days)
    
    def is_expired(self):
        return datetime.utcnow() >= self.expires_at
    
    def extend_duration(self, days):
        """Extend expiry by days"""
        self.expires_at += timedelta(days=days)
        self.duration_days += days
        db.session.commit()
        sync_to_json(self)
    
    def reduce_duration(self, days):
        """Reduce expiry by days"""
        new_expiry = self.expires_at - timedelta(days=days)
        if new_expiry < datetime.utcnow():
            new_expiry = datetime.utcnow() + timedelta(hours=1)
        self.expires_at = new_expiry
        self.duration_days = max(0, self.duration_days - days)
        db.session.commit()
        sync_to_json(self)


class ActivityLog(db.Model):
    """Activity logging"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    action = db.Column(db.String(50), nullable=False)
    details = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='logs')


class Transaction(db.Model):
    """Credit transactions"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    type = db.Column(db.String(20), nullable=False)  # 'credit', 'debit', 'uid_add'
    description = db.Column(db.String(200))
    balance_after = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='transactions')


# ==================== HELPER FUNCTIONS ====================

def calculate_credits(years=0, months=0, days=0, hours=0):
    """Calculate credits from duration"""
    total_days = (years * 365) + (months * 30) + days + (hours / 24)
    
    # Pricing: ₹0.15 per day (simplified)
    return round(total_days * 0.15, 2)


def calculate_expiry(years=0, months=0, days=0, hours=0):
    """Calculate expiry datetime"""
    delta = timedelta(days=years*365 + months*30 + days, hours=hours)
    return datetime.utcnow() + delta


def sync_to_json(uid_entry):
    """Sync UID to JSON whitelist file"""
    try:
        region = uid_entry.region.lower()
        json_file = os.path.join(WHITELIST_DIR, f'whitelist_{region}.json')
        
        print(f"[SYNC] Syncing UID {uid_entry.uid} to {json_file}")
        
        # Load existing
        if os.path.exists(json_file):
            with open(json_file, 'r') as f:
                data = json.load(f)
        else:
            data = {}
            print(f"[SYNC] Creating new JSON file: {json_file}")
        
        # Add/Update
        data[str(uid_entry.uid)] = {
            "expiry": int(uid_entry.expires_at.timestamp()),
            "region": uid_entry.region
        }
        
        # Save
        with open(json_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"[SYNC] Successfully synced UID {uid_entry.uid} - Expiry: {uid_entry.expires_at}")
        return True
    except Exception as e:
        print(f"[SYNC ERROR] Failed to sync UID to JSON: {e}")
        import traceback
        traceback.print_exc()
        return False


def remove_from_json(uid, region):
    """Remove UID from JSON"""
    try:
        json_file = os.path.join(WHITELIST_DIR, f'whitelist_{region.lower()}.json')
        
        print(f"[REMOVE] Removing UID {uid} from {json_file}")
        
        if os.path.exists(json_file):
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            if str(uid) in data:
                del data[str(uid)]
                
                with open(json_file, 'w') as f:
                    json.dump(data, f, indent=2)
                
                print(f"[REMOVE] Successfully removed UID {uid} from JSON")
            else:
                print(f"[REMOVE] UID {uid} not found in JSON file")
        else:
            print(f"[REMOVE] JSON file not found: {json_file}")
        
        return True
    except Exception as e:
        print(f"[REMOVE ERROR] Failed to remove UID from JSON: {e}")
        import traceback
        traceback.print_exc()
        return False


def log_activity(user_id, action, details=None):
    """Log activity"""
    try:
        log = ActivityLog(user_id=user_id, action=action, details=details)
        db.session.add(log)
        db.session.commit()
    except:
        pass


def create_transaction(user_id, amount, trans_type, description=None):
    """Record transaction"""
    try:
        user = User.query.get(user_id)
        trans = Transaction(
            user_id=user_id,
            amount=amount,
            type=trans_type,
            description=description,
            balance_after=user.credits
        )
        db.session.add(trans)
        db.session.commit()
    except:
        pass


# ==================== DECORATORS ====================

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def owner_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        user = User.query.get(session['user_id'])
        if not user or not user.is_owner():
            flash('Owner access required', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


def reseller_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        user = User.query.get(session['user_id'])
        if not user or user.is_owner():
            flash('Reseller access required', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


# ==================== WEB ROUTES ====================

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        try:
            # Input validation and sanitization
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            
            # Basic input validation
            if not username or not password:
                flash('Username and password are required', 'danger')
                return render_template('login.html')
            
            if len(username) > 80 or len(password) > 200:
                flash('Invalid credentials', 'danger')
                return render_template('login.html')
            
            # Rate limiting check (simple)
            time.sleep(0.5)  # Prevent brute force
            
            # Use parameterized query (SQLAlchemy handles SQL injection)
            user = User.query.filter_by(username=username, is_active=True).first()
            
            if user and check_password_hash(user.password, password):
                # Regenerate session to prevent session fixation
                session.clear()
                session['user_id'] = user.id
                session['username'] = user.username
                session['role'] = user.role
                session.permanent = True
                
                log_activity(user.id, 'LOGIN_SUCCESS')
                flash(f'Welcome, {user.username}!', 'success')
                return redirect(url_for('dashboard'))
            else:
                log_activity(None, f'LOGIN_FAILED', f'Username: {username}')
                flash('Invalid username or password', 'danger')
                
        except Exception as e:
            log_activity(None, 'LOGIN_ERROR', str(e))
            flash('An error occurred. Please try again.', 'danger')
    
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    log_activity(session.get('user_id'), 'LOGOUT')
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = User.query.get(session['user_id'])
    
    if request.method == 'POST':
        try:
            action = request.form.get('action')
            
            if action == 'change_username':
                current_password = request.form.get('current_password', '').strip()
                new_username = request.form.get('new_username', '').strip()
                
                # Validation
                if not current_password or not new_username:
                    flash('All fields are required', 'danger')
                elif not check_password_hash(user.password, current_password):
                    flash('Current password is incorrect', 'danger')
                elif len(new_username) < 3:
                    flash('Username must be at least 3 characters', 'danger')
                elif len(new_username) > 80:
                    flash('Username is too long', 'danger')
                elif new_username == user.username:
                    flash('New username must be different from current username', 'warning')
                else:
                    # Check if username already exists
                    existing = User.query.filter_by(username=new_username).first()
                    if existing and existing.id != user.id:
                        flash('Username already exists', 'danger')
                    else:
                        old_username = user.username
                        user.username = new_username
                        db.session.commit()
                        log_activity(user.id, 'CHANGE_USERNAME', f'Changed username from {old_username} to {new_username}')
                        flash('Username changed successfully!', 'success')
                        return redirect(url_for('profile'))
                        
            elif action == 'change_password':
                current_password = request.form.get('current_password_pwd', '').strip()
                new_password = request.form.get('new_password', '').strip()
                confirm_password = request.form.get('confirm_password', '').strip()
                
                # Validation
                if not current_password or not new_password or not confirm_password:
                    flash('All fields are required', 'danger')
                elif not check_password_hash(user.password, current_password):
                    flash('Current password is incorrect', 'danger')
                elif new_password != confirm_password:
                    flash('New passwords do not match', 'danger')
                elif len(new_password) < 6:
                    flash('Password must be at least 6 characters', 'danger')
                elif len(new_password) > 200:
                    flash('Password is too long', 'danger')
                elif current_password == new_password:
                    flash('New password must be different from current password', 'warning')
                else:
                    user.password = generate_password_hash(new_password)
                    db.session.commit()
                    log_activity(user.id, 'CHANGE_PASSWORD', 'Password changed successfully')
                    flash('Password changed successfully!', 'success')
                    return redirect(url_for('profile'))
                    
        except Exception as e:
            log_activity(user.id, 'PROFILE_UPDATE_ERROR', str(e))
            flash('An error occurred. Please try again.', 'danger')
    
    return render_template('profile.html', user=user)


@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    user = User.query.get(session['user_id'])
    
    if request.method == 'POST':
        try:
            current_password = request.form.get('current_password', '').strip()
            new_password = request.form.get('new_password', '').strip()
            confirm_password = request.form.get('confirm_password', '').strip()
            
            # Validation
            if not current_password or not new_password or not confirm_password:
                flash('All fields are required', 'danger')
            elif not check_password_hash(user.password, current_password):
                flash('Current password is incorrect', 'danger')
            elif new_password != confirm_password:
                flash('New passwords do not match', 'danger')
            elif len(new_password) < 6:
                flash('Password must be at least 6 characters', 'danger')
            elif len(new_password) > 200:
                flash('Password is too long', 'danger')
            elif current_password == new_password:
                flash('New password must be different from current password', 'warning')
            else:
                user.password = generate_password_hash(new_password)
                db.session.commit()
                log_activity(user.id, 'CHANGE_PASSWORD', 'Password changed successfully')
                flash('Password changed successfully!', 'success')
                return redirect(url_for('dashboard'))
                
        except Exception as e:
            log_activity(user.id, 'CHANGE_PASSWORD_ERROR', str(e))
            flash('An error occurred. Please try again.', 'danger')
    
    return render_template('change_password.html')


@app.route('/owner/change_credentials/<int:user_id>', methods=['POST'])
@owner_required
def owner_change_credentials(user_id):
    target_user = User.query.get(user_id)
    
    if not target_user:
        flash('User not found', 'error')
        return redirect(url_for('owner_resellers'))
    
    new_username = request.form.get('new_username')
    new_password = request.form.get('new_password')
    
    if new_username:
        # Check if username already exists
        existing = User.query.filter_by(username=new_username).first()
        if existing and existing.id != user_id:
            flash('Username already exists', 'error')
        else:
            old_username = target_user.username
            target_user.username = new_username
            log_activity(session['user_id'], 'CHANGE_USERNAME', f'Changed {old_username} to {new_username}')
    
    if new_password and len(new_password) >= 6:
        target_user.password = generate_password_hash(new_password)
        log_activity(session['user_id'], 'RESET_PASSWORD', f'Reset password for {target_user.username}')
    
    db.session.commit()
    flash(f'Credentials updated for {target_user.username}', 'success')
    return redirect(url_for('owner_resellers'))


@app.route('/dashboard')
@login_required
def dashboard():
    user = User.query.get(session['user_id'])
    
    if user.is_owner():
        # Owner dashboard
        total_resellers = User.query.filter_by(role='reseller', is_active=True).count()
        total_uids = UIDEntry.query.filter_by(is_active=True).count()
        recent_uids = UIDEntry.query.order_by(UIDEntry.created_at.desc()).limit(10).all()
        recent_logs = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).limit(10).all()
        
        return render_template('owner/dashboard.html',
                             total_resellers=total_resellers,
                             total_uids=total_uids,
                             recent_uids=recent_uids,
                             recent_logs=recent_logs)
    else:
        # Reseller dashboard
        my_uids = UIDEntry.query.filter_by(added_by=user.id, is_active=True).all()
        recent_transactions = Transaction.query.filter_by(user_id=user.id).order_by(Transaction.timestamp.desc()).limit(5).all()
        
        return render_template('reseller/dashboard.html',
                             credits=user.credits,
                             my_uids=my_uids,
                             recent_transactions=recent_transactions)


# ==================== OWNER ROUTES ====================

@app.route('/owner/resellers')
@owner_required
def owner_resellers():
    resellers = User.query.filter_by(role='reseller').all()
    return render_template('owner/resellers.html', resellers=resellers)


@app.route('/owner/add_reseller', methods=['POST'])
@owner_required
def owner_add_reseller():
    username = request.form.get('username')
    password = request.form.get('password')
    initial_credits = float(request.form.get('credits', 0))
    
    if User.query.filter_by(username=username).first():
        flash('Username already exists', 'error')
    else:
        reseller = User(
            username=username,
            password=generate_password_hash(password),
            role='reseller',
            credits=initial_credits
        )
        db.session.add(reseller)
        db.session.commit()
        
        log_activity(session['user_id'], 'ADD_RESELLER', f'Added {username}')
        flash(f'Reseller {username} created!', 'success')
    
    return redirect(url_for('owner_resellers'))


@app.route('/owner/add_credits/<int:reseller_id>', methods=['POST'])
@owner_required
def owner_add_credits(reseller_id):
    amount = float(request.form.get('amount', 0))
    reseller = User.query.get(reseller_id)
    
    if reseller and amount > 0:
        reseller.credits += amount
        db.session.commit()
        
        create_transaction(reseller_id, amount, 'credit', f'Credits added by owner')
        log_activity(session['user_id'], 'ADD_CREDITS', f'Added {amount} credits to {reseller.username}')
        flash(f'Added {amount} credits to {reseller.username}', 'success')
    
    return redirect(url_for('owner_resellers'))


@app.route('/owner/delete_reseller/<int:reseller_id>')
@owner_required
def owner_delete_reseller(reseller_id):
    reseller = User.query.get(reseller_id)
    if reseller and reseller.role == 'reseller':
        reseller.is_active = False
        db.session.commit()
        
        log_activity(session['user_id'], 'DELETE_RESELLER', f'Deleted {reseller.username}')
        flash(f'Reseller {reseller.username} deleted', 'success')
    
    return redirect(url_for('owner_resellers'))


@app.route('/owner/all_uids')
@owner_required
def owner_all_uids():
    region_filter = request.args.get('region', '')
    reseller_filter = request.args.get('reseller', '')
    
    query = UIDEntry.query.filter_by(is_active=True)
    
    if region_filter:
        query = query.filter_by(region=region_filter)
    
    if reseller_filter:
        reseller = User.query.filter_by(username=reseller_filter).first()
        if reseller:
            query = query.filter_by(added_by=reseller.id)
    
    uids = query.order_by(UIDEntry.created_at.desc()).all()
    resellers = User.query.filter_by(role='reseller', is_active=True).all()
    
    return render_template('owner/all_uids.html',
                         uids=uids,
                         regions=REGIONS,
                         resellers=resellers,
                         selected_region=region_filter,
                         selected_reseller=reseller_filter)


@app.route('/owner/add_uid', methods=['GET', 'POST'])
@owner_required  
def owner_add_uid():
    if request.method == 'POST':
        uid = request.form.get('uid')
        uid_name = request.form.get('uid_name')
        region = request.form.get('region')
        years = int(request.form.get('years', 0))
        months = int(request.form.get('months', 0))
        days = int(request.form.get('days', 0))
        hours = int(request.form.get('hours', 0))
        
        # Check if UID exists
        existing = UIDEntry.query.filter_by(uid=uid, region=region, is_active=True).first()
        if existing:
            flash('UID already exists in this region', 'error')
            return redirect(url_for('owner_add_uid'))
        
        expiry = calculate_expiry(years, months, days, hours)
        total_days = years*365 + months*30 + days + hours//24
        
        new_uid = UIDEntry(
            uid=uid,
            uid_name=uid_name,
            region=region,
            added_by=session['user_id'],
            added_via='web',
            expires_at=expiry,
            duration_days=total_days,
            credits_used=0
        )
        
        db.session.add(new_uid)
        db.session.commit()
        
        sync_to_json(new_uid)
        log_activity(session['user_id'], 'ADD_UID', f'Added {uid} ({uid_name}) for {total_days} days')
        flash(f'UID {uid} added successfully!', 'success')
        return redirect(url_for('owner_all_uids'))
    
    return render_template('owner/add_uid.html', regions=REGIONS)


@app.route('/owner/extend_uid/<int:uid_id>', methods=['POST'])
@owner_required
def owner_extend_uid(uid_id):
    days = int(request.form.get('days', 0))
    uid_entry = UIDEntry.query.get(uid_id)
    
    if uid_entry and days > 0:
        uid_entry.extend_duration(days)
        sync_to_json(uid_entry)
        log_activity(session['user_id'], 'EXTEND_UID', f'Extended {uid_entry.uid} by {days} days')
        flash(f'Extended {uid_entry.uid} by {days} days', 'success')
    
    return redirect(url_for('owner_all_uids'))


@app.route('/owner/reduce_uid/<int:uid_id>', methods=['POST'])
@owner_required
def owner_reduce_uid(uid_id):
    days = int(request.form.get('days', 0))
    uid_entry = UIDEntry.query.get(uid_id)
    
    if uid_entry and days > 0:
        uid_entry.reduce_duration(days)
        sync_to_json(uid_entry)
        log_activity(session['user_id'], 'REDUCE_UID', f'Reduced {uid_entry.uid} by {days} days')
        flash(f'Reduced {uid_entry.uid} by {days} days', 'success')
    
    return redirect(url_for('owner_all_uids'))


@app.route('/owner/delete_uid/<int:uid_id>')
@owner_required
def owner_delete_uid(uid_id):
    uid_entry = UIDEntry.query.get(uid_id)
    
    if uid_entry:
        uid_entry.is_active = False
        db.session.commit()
        
        remove_from_json(uid_entry.uid, uid_entry.region)
        log_activity(session['user_id'], 'DELETE_UID', f'Deleted {uid_entry.uid}')
        flash(f'UID {uid_entry.uid} deleted', 'success')
    
    return redirect(url_for('owner_all_uids'))


@app.route('/owner/switch_uid/<int:uid_id>', methods=['POST'])
@owner_required
def owner_switch_uid(uid_id):
    new_uid = request.form.get('new_uid')
    uid_entry = UIDEntry.query.get(uid_id)
    
    if uid_entry and new_uid:
        old_uid = uid_entry.uid
        remove_from_json(old_uid, uid_entry.region)
        
        uid_entry.uid = new_uid
        db.session.commit()
        
        sync_to_json(uid_entry)
        log_activity(session['user_id'], 'SWITCH_UID', f'Switched {old_uid} to {new_uid}')
        flash(f'UID switched from {old_uid} to {new_uid}', 'success')
    
    return redirect(url_for('owner_all_uids'))


# ==================== RESELLER ROUTES ====================

@app.route('/reseller/my_uids')
@reseller_required
def reseller_my_uids():
    user_id = session['user_id']
    my_uids = UIDEntry.query.filter_by(added_by=user_id, is_active=True).order_by(UIDEntry.created_at.desc()).all()
    
    return render_template('reseller/my_uids.html', uids=my_uids)


@app.route('/reseller/add_uid', methods=['GET', 'POST'])
@reseller_required
def reseller_add_uid():
    user = User.query.get(session['user_id'])
    
    if request.method == 'POST':
        uid = request.form.get('uid')
        uid_name = request.form.get('uid_name')
        region = request.form.get('region')
        years = int(request.form.get('years', 0))
        months = int(request.form.get('months', 0))
        days = int(request.form.get('days', 0))
        hours = int(request.form.get('hours', 0))
        
        # Calculate credits needed
        credits_needed = calculate_credits(years, months, days, hours)
        
        if not user.has_credits(credits_needed):
            flash(f'Insufficient credits! Need {credits_needed}, have {user.credits}', 'error')
            return redirect(url_for('reseller_add_uid'))
        
        # Check if UID exists
        existing = UIDEntry.query.filter_by(uid=uid, region=region, is_active=True).first()
        if existing:
            flash('UID already exists', 'error')
            return redirect(url_for('reseller_add_uid'))
        
        # Create UID
        expiry = calculate_expiry(years, months, days, hours)
        total_days = years*365 + months*30 + days + hours//24
        
        new_uid = UIDEntry(
            uid=uid,
            uid_name=uid_name,
            region=region,
            added_by=user.id,
            added_via='web',
            expires_at=expiry,
            duration_days=total_days,
            credits_used=credits_needed
        )
        
        # Deduct credits
        user.credits -= credits_needed
        
        db.session.add(new_uid)
        db.session.commit()
        
        sync_to_json(new_uid)
        create_transaction(user.id, -credits_needed, 'uid_add', f'Added UID {uid}')
        log_activity(user.id, 'ADD_UID', f'Added {uid} for {total_days} days')
        
        flash(f'UID {uid} added! Used {credits_needed} credits', 'success')
        return redirect(url_for('reseller_my_uids'))
    
    return render_template('reseller/add_uid.html', regions=REGIONS, credits=user.credits)


# ==================== DISCORD BOT ====================

discord_bot = None
bot_tree = None

async def start_discord_bot():
    global discord_bot, bot_tree
    
    intents = discord.Intents.default()
    discord_bot = discord.Client(intents=intents)
    bot_tree = app_commands.CommandTree(discord_bot)
    
    # ===== WHITELIST COMMAND GROUP =====
    whitelist_group = app_commands.Group(name="whitelist", description="Manage whitelist UIDs")
    
    @whitelist_group.command(name="add", description="Add UID to whitelist")
    @app_commands.describe(
        uid="UID number to add",
        uid_name="Name of UID owner",
        region="Region",
        days="Days",
        hours="Hours"
    )
    async def whitelist_add(
        interaction: discord.Interaction,
        uid: str,
        uid_name: str,
        region: Literal["IND", "ID", "BR", "ME", "VN", "TH", "CIS", "BD", "PK", "SG", "NA", "SAC", "EU", "TW"],
        days: int = 0,
        hours: int = 0
    ):
        await interaction.response.defer()
        
        try:
            discord_id = interaction.user.id
            
            # ONLY allow authorized Discord IDs
            if discord_id not in AUTHORIZED_DISCORD_IDS:
                embed = discord.Embed(
                    title="❌ Not Authorized",
                    description=f"Your Discord ID ({discord_id}) is not authorized to use this bot.\nContact owner for access.",
                    color=0xe74c3c
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            with app.app_context():
                # Get owner account for authorized user
                user = User.query.filter_by(role='owner', is_active=True).first()
                
                if not user:
                    embed = discord.Embed(
                        title="❌ Not Authorized",
                        description=f"No account found for Discord user: {discord_username}\nContact owner to create account.",
                        color=0xe74c3c
                    )
                    await interaction.followup.send(embed=embed)
                    return
                
                if days == 0 and hours == 0:
                    embed = discord.Embed(
                        title="❌ Invalid Duration",
                        description="Please specify at least 1 day or 1 hour",
                        color=0xe74c3c
                    )
                    await interaction.followup.send(embed=embed)
                    return
                
                # Calculate credits
                total_days = days + (hours / 24)
                credits_needed = calculate_credits(0, 0, days, hours)
                
                # Check credits
                if not user.has_credits(credits_needed):
                    embed = discord.Embed(
                        title="❌ Insufficient Credits",
                        description=f"Need: ₹{credits_needed:.2f}\nHave: ₹{user.credits:.2f}\nContact owner to add credits.",
                        color=0xe74c3c
                    )
                    await interaction.followup.send(embed=embed)
                    return
                
                # Check if UID exists
                existing = UIDEntry.query.filter_by(uid=uid, region=region, is_active=True).first()
                if existing:
                    embed = discord.Embed(
                        title="❌ UID Already Exists",
                        description=f"UID {uid} already whitelisted in {region}",
                        color=0xe74c3c
                    )
                    await interaction.followup.send(embed=embed)
                    return
                
                # Create UID
                expiry = calculate_expiry(0, 0, days, hours)
                new_uid = UIDEntry(
                    uid=uid,
                    uid_name=uid_name,
                    region=region,
                    added_by=user.id,
                    added_via='discord',
                    expires_at=expiry,
                    duration_days=int(total_days),
                    credits_used=credits_needed if not user.is_owner() else 0
                )
                
                # Deduct credits if reseller
                if not user.is_owner():
                    user.credits -= credits_needed
                
                db.session.add(new_uid)
                db.session.commit()
                
                sync_to_json(new_uid)
                create_transaction(user.id, -credits_needed, 'uid_add', f'Added UID {uid} via Discord')
                log_activity(user.id, 'ADD_UID_DISCORD', f'Added {uid} ({uid_name}) for {total_days} days')
                
                embed = discord.Embed(
                    title="✅ UID Added Successfully",
                    description=f"**UID:** {uid}\n**Name:** {uid_name}\n**Region:** {region}\n**Duration:** {days}d {hours}h\n**Expires:** {expiry.strftime('%Y-%m-%d %H:%M')}",
                    color=0x2ecc71
                )
                if not user.is_owner():
                    embed.add_field(name="Credits Used", value=f"₹{credits_needed:.2f}", inline=True)
                    embed.add_field(name="Remaining", value=f"₹{user.credits:.2f}", inline=True)
                
                await interaction.followup.send(embed=embed)
        
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to add UID: {str(e)}",
                color=0xe74c3c
            )
            await interaction.followup.send(embed=embed)
    
    @whitelist_group.command(name="remove", description="Remove UID from whitelist")
    @app_commands.describe(uid="UID to remove", region="Region")
    async def whitelist_remove(
        interaction: discord.Interaction,
        uid: str,
        region: Literal["IND", "ID", "BR", "ME", "VN", "TH", "CIS", "BD", "PK", "SG", "NA", "SAC", "EU", "TW"]
    ):
        await interaction.response.defer()
        
        try:
            discord_id = interaction.user.id
            
            # ONLY allow authorized Discord IDs
            if discord_id not in AUTHORIZED_DISCORD_IDS:
                embed = discord.Embed(
                    title="❌ Not Authorized",
                    description=f"Your Discord ID ({discord_id}) is not authorized to use this bot.\nContact owner for access.",
                    color=0xe74c3c
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            with app.app_context():
                # Get owner account for authorized user
                user = User.query.filter_by(role='owner', is_active=True).first()
                
                if not user:
                    embed = discord.Embed(
                        title="❌ Not Authorized",
                        description="No account found",
                        color=0xe74c3c
                    )
                    await interaction.followup.send(embed=embed)
                    return
                
                uid_entry = UIDEntry.query.filter_by(uid=uid, region=region, is_active=True).first()
                
                if not uid_entry:
                    embed = discord.Embed(
                        title="❌ UID Not Found",
                        description=f"UID {uid} not found in {region}",
                        color=0xe74c3c
                    )
                    await interaction.followup.send(embed=embed)
                    return
                
                # Check ownership
                if not user.is_owner() and uid_entry.added_by != user.id:
                    embed = discord.Embed(
                        title="❌ Permission Denied",
                        description="You can only remove your own UIDs",
                        color=0xe74c3c
                    )
                    await interaction.followup.send(embed=embed)
                    return
                
                uid_entry.is_active = False
                db.session.commit()
                
                remove_from_json(uid, region)
                log_activity(user.id, 'REMOVE_UID_DISCORD', f'Removed {uid}')
                
                embed = discord.Embed(
                    title="✅ UID Removed",
                    description=f"**UID:** {uid}\n**Region:** {region}",
                    color=0x2ecc71
                )
                await interaction.followup.send(embed=embed)
        
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to remove UID: {str(e)}",
                color=0xe74c3c
            )
            await interaction.followup.send(embed=embed)
    
    @whitelist_group.command(name="check", description="Check UID status")
    @app_commands.describe(uid="UID to check", region="Region")
    async def whitelist_check(
        interaction: discord.Interaction,
        uid: str,
        region: Literal["IND", "ID", "BR", "ME", "VN", "TH", "CIS", "BD", "PK", "SG", "NA", "SAC", "EU", "TW"]
    ):
        await interaction.response.defer()
        
        try:
            discord_id = interaction.user.id
            
            # ONLY allow authorized Discord IDs
            if discord_id not in AUTHORIZED_DISCORD_IDS:
                embed = discord.Embed(
                    title="❌ Not Authorized",
                    description=f"Your Discord ID ({discord_id}) is not authorized to use this bot.\nContact owner for access.",
                    color=0xe74c3c
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            with app.app_context():
                uid_entry = UIDEntry.query.filter_by(uid=uid, region=region, is_active=True).first()
                
                if uid_entry and not uid_entry.is_expired():
                    embed = discord.Embed(
                        title="✅ UID Active",
                        description=f"**UID:** {uid}\n**Name:** {uid_entry.uid_name}\n**Region:** {region}\n**Days Left:** {uid_entry.days_remaining()}\n**Expires:** {uid_entry.expires_at.strftime('%Y-%m-%d %H:%M')}",
                        color=0x2ecc71
                    )
                else:
                    embed = discord.Embed(
                        title="❌ UID Not Active",
                        description=f"**UID:** {uid}\n**Region:** {region}\n**Status:** Not whitelisted or expired",
                        color=0xe74c3c
                    )
                
                await interaction.followup.send(embed=embed)
        
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to check UID: {str(e)}",
                color=0xe74c3c
            )
            await interaction.followup.send(embed=embed)
    
    @whitelist_group.command(name="list", description="List your UIDs")
    async def whitelist_list(interaction: discord.Interaction):
        await interaction.response.defer()
        
        try:
            discord_id = interaction.user.id
            
            # ONLY allow authorized Discord IDs
            if discord_id not in AUTHORIZED_DISCORD_IDS:
                embed = discord.Embed(
                    title="❌ Not Authorized",
                    description=f"Your Discord ID ({discord_id}) is not authorized to use this bot.\nContact owner for access.",
                    color=0xe74c3c
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            with app.app_context():
                # Get owner account for authorized user
                user = User.query.filter_by(role='owner', is_active=True).first()
                
                if not user:
                    embed = discord.Embed(
                        title="❌ Not Authorized",
                        description="No account found",
                        color=0xe74c3c
                    )
                    await interaction.followup.send(embed=embed)
                    return
                
                if user.is_owner():
                    uids = UIDEntry.query.filter_by(is_active=True).all()
                    title = "📋 All UIDs (Owner View)"
                else:
                    uids = UIDEntry.query.filter_by(added_by=user.id, is_active=True).all()
                    title = "📋 My UIDs"
                
                if not uids:
                    embed = discord.Embed(
                        title=title,
                        description="No active UIDs found",
                        color=0x3498db
                    )
                    await interaction.followup.send(embed=embed)
                    return
                
                # Split into chunks for multiple embeds
                chunks = [uids[i:i+10] for i in range(0, len(uids), 10)]
                
                for i, chunk in enumerate(chunks):
                    desc = ""
                    for uid_entry in chunk:
                        status = "🟢" if not uid_entry.is_expired() else "🔴"
                        desc += f"{status} **{uid_entry.uid}** - {uid_entry.uid_name}\n"
                        desc += f"   Region: {uid_entry.region} | Days: {uid_entry.days_remaining()}\n\n"
                    
                    embed = discord.Embed(
                        title=f"{title} (Page {i+1}/{len(chunks)})",
                        description=desc,
                        color=0x3498db
                    )
                    embed.set_footer(text=f"Total: {len(uids)} UIDs")
                    
                    await interaction.followup.send(embed=embed)
        
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to list UIDs: {str(e)}",
                color=0xe74c3c
            )
            await interaction.followup.send(embed=embed)
    
    # Add whitelist group to tree
    bot_tree.add_command(whitelist_group)
    
    @discord_bot.event
    async def on_ready():
        await bot_tree.sync()
        print(f'✅ Discord Bot logged in as {discord_bot.user}')
        print(f'✅ Commands synced: /whitelist add, remove, check, list')
    
    await discord_bot.start(DISCORD_BOT_TOKEN)


def run_flask():
    """Run Flask in production mode"""
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)


# ==================== MAIN ====================

if __name__ == '__main__':
    print('🚀 Starting Mani 272 UID Management System...')
    print('📁 Initializing database...')
    
    with app.app_context():
        db.create_all()
        
        # Create owner if doesn't exist
        owner = User.query.filter_by(username='Mani').first()
        if not owner:
            owner = User(
                username='Mani',
                password=generate_password_hash('mani123'),
                role='owner',
                credits=999999  # Unlimited
            )
            db.session.add(owner)
            db.session.commit()
            print('✅ Owner created: username=Mani, password=mani123')
        
        print('✅ Database ready')
    
    print('🌐 Starting web server on http://0.0.0.0:5000')
    print('🤖 Starting Discord bot in background...')
    print('=' * 60)
    print('LOGIN CREDENTIALS:')
    print('Username: Mani')
    print('Password: mani123')
    print('=' * 60)
    
    # Start Discord bot in separate thread (only if token is provided)
    if DISCORD_BOT_TOKEN and len(DISCORD_BOT_TOKEN) > 10:
        bot_thread = Thread(target=lambda: asyncio.run(start_discord_bot()), daemon=True)
        bot_thread.start()
    else:
        print('⚠️ Discord bot token not configured - skipping Discord bot')
    
    # Start Flask
    run_flask()
