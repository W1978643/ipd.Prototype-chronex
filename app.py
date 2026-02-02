# ==== Imports ====
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta
import os
import logging

# Suppress Flask development server warning
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)


# ==== App Configuration ====
app = Flask(__name__)
app.config['SECRET_KEY'] = 'chronex-lite-secret-key-2026'  # Session encryption key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chronex_lite.db'  # SQLite database file
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Disable for performance

# Initialize Flask extensions
database = SQLAlchemy(app)  # Database ORM
login_manager = LoginManager(app)  # User session management
login_manager.login_view = 'show_landing_page'  # Redirect here if not logged in


# ==== Database Models ====

class User(UserMixin, database.Model):
    """
    User account model - stores credentials and gamification progress.
    UserMixin provides Flask-Login required methods (is_authenticated, get_id, etc.)
    """
    # Primary identification
    id = database.Column(database.Integer, primary_key=True)
    username = database.Column(database.String(50), unique=True, nullable=False)  # Required for login
    email = database.Column(database.String(120), unique=True, nullable=True)  # Optional
    password_hash = database.Column(database.String(200), nullable=False)  # Hashed, never plain text
    
    # Gamification - Focus Farm system
    total_focus_points = database.Column(database.Integer, default=0)  # Cumulative points
    stars_earned = database.Column(database.Integer, default=0)  # Stars from focus sessions
    energy_bank_balance = database.Column(database.Integer, default=0)  # Accumulated energy
    last_energy_collection_time = database.Column(database.DateTime, default=datetime.utcnow)
    
    # Daily focus tracking
    focus_minutes_today = database.Column(database.Integer, default=0)  # Resets daily
    focus_tracking_date = database.Column(database.Date)  # For daily reset check
    
    account_created_at = database.Column(database.DateTime, default=datetime.utcnow)
    
    # Achievement flags - Boolean for each milestone
    achievement_first_login = database.Column(database.Boolean, default=False)
    achievement_first_focus = database.Column(database.Boolean, default=False)
    achievement_first_task = database.Column(database.Boolean, default=False)
    achievement_first_note = database.Column(database.Boolean, default=False)
    achievement_email_added = database.Column(database.Boolean, default=True)
    
    # Savings goal - single target per user
    savings_goal_name = database.Column(database.String(100), nullable=True)
    savings_goal_target = database.Column(database.Float, nullable=True)


class Task(database.Model):
    """Task model - todo items with priority and date range."""
    id = database.Column(database.Integer, primary_key=True)
    user_id = database.Column(database.Integer, database.ForeignKey('user.id'), nullable=False)  # Owner
    task_title = database.Column(database.String(200), nullable=False)
    start_date = database.Column(database.Date, default=date.today)
    deadline_date = database.Column(database.Date, nullable=True)  # Optional deadline
    priority_level = database.Column(database.String(20), default='medium')  # low/medium/high
    is_completed = database.Column(database.Boolean, default=False)
    task_created_at = database.Column(database.DateTime, default=datetime.utcnow)


class Note(database.Model):
    """Note model - personal notes with auto-updating timestamp."""
    id = database.Column(database.Integer, primary_key=True)
    user_id = database.Column(database.Integer, database.ForeignKey('user.id'), nullable=False)
    note_title = database.Column(database.String(200), default='')
    note_content = database.Column(database.Text, nullable=False)
    last_modified_at = database.Column(database.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # Auto-updates


class Transaction(database.Model):
    """Transaction model - income and expense entries for budget tracking."""
    id = database.Column(database.Integer, primary_key=True)
    user_id = database.Column(database.Integer, database.ForeignKey('user.id'), nullable=False)
    transaction_type = database.Column(database.String(20), nullable=False)  # 'income' or 'expense'
    transaction_description = database.Column(database.String(200), nullable=False)
    transaction_amount = database.Column(database.Float, nullable=False)
    transaction_category = database.Column(database.String(50), nullable=False)
    transaction_date = database.Column(database.Date, default=date.today)


@login_manager.user_loader
def load_user_by_id(user_id):
    """Flask-Login callback - loads user from session cookie."""
    return User.query.get(int(user_id))


# ==== Authentication Routes ====

@app.route('/')
def show_landing_page():
    """Landing page - redirects authenticated users to dashboard."""
    if current_user.is_authenticated:
        return redirect(url_for('show_dashboard'))
    return render_template('landing.html')


@app.route('/login', methods=['POST'])
def handle_login():
    """
    Process login form submission.
    Accepts email OR username (case-insensitive).
    """
    login_identifier = request.form.get('email', '').strip().lower()
    password = request.form.get('password')
    
    # Query by email OR username (case-insensitive match)
    found_user = User.query.filter(
        (database.func.lower(User.email) == login_identifier) | 
        (database.func.lower(User.username) == login_identifier)
    ).first()
    
    # Verify password hash
    if found_user and check_password_hash(found_user.password_hash, password):
        login_user(found_user)  # Create session
        
        # Unlock "First Steps" achievement on first login
        if not found_user.achievement_first_login:
            found_user.achievement_first_login = True
            database.session.commit()
            flash('Achievement unlocked: First Steps!', 'success')
        return redirect(url_for('show_dashboard'))
    
    flash('Invalid email/username or password', 'error')
    return redirect(url_for('show_landing_page'))


@app.route('/register', methods=['POST'])
def handle_registration():
    """
    Process registration form.
    Username required, email optional.
    """
    username = request.form.get('username', '').strip().lower()
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')
    
    # Validate password confirmation
    if password != confirm_password:
        flash('Passwords do not match', 'error')
        return redirect(url_for('show_landing_page'))
    
    # Check username availability
    if User.query.filter(database.func.lower(User.username) == username).first():
        flash('Username already taken', 'error')
        return redirect(url_for('show_landing_page'))
    
    # Check email availability (only if provided)
    if email and User.query.filter(database.func.lower(User.email) == email).first():
        flash('Email already registered', 'error')
        return redirect(url_for('show_landing_page'))
    
    # Create new user account
    new_user = User(
        username=username,
        email=email if email else None,  # Store None if empty
        password_hash=generate_password_hash(password),  # Hash password
        achievement_email_added=True if email else False  # Achievement if email provided
    )
    database.session.add(new_user)
    database.session.commit()
    
    flash(f'Account created! Sign in with "{username}"', 'success')
    return redirect(url_for('show_landing_page'))


@app.route('/forgot-password', methods=['POST'])
def handle_forgot_password():
    """Password reset placeholder."""
    flash('Password reset link sent to your email', 'success')
    return redirect(url_for('show_landing_page'))


@app.route('/logout')
@login_required
def handle_logout():
    """Log out current user and clear session."""
    logout_user()
    return redirect(url_for('show_landing_page'))


# ==== Dashboard Route ====

@app.route('/home')
@login_required
def show_dashboard():
    """
    Main dashboard - displays productivity overview.
    Shows: progress bar, task count, focus time, notes, points, budget, achievements.
    """
    today = date.today()
    
    # Reset daily focus counter if new day
    if current_user.focus_tracking_date != today:
        current_user.focus_minutes_today = 0
        current_user.focus_tracking_date = today
        database.session.commit()
    
    # Count user's active tasks and notes
    active_tasks_count = Task.query.filter_by(user_id=current_user.id, is_completed=False).count()
    total_notes_count = Note.query.filter_by(user_id=current_user.id).count()
    
    # Determine daily focus goal based on highest priority task
    # Priority mapping: high=30min, medium=15min, low=10min
    high_priority_task = Task.query.filter_by(user_id=current_user.id, is_completed=False, priority_level='high').first()
    medium_priority_task = Task.query.filter_by(user_id=current_user.id, is_completed=False, priority_level='medium').first()
    low_priority_task = Task.query.filter_by(user_id=current_user.id, is_completed=False, priority_level='low').first()
    
    if high_priority_task:
        daily_focus_goal = 30
        priority_message = "High priority task - Focus 30 min"
    elif medium_priority_task:
        daily_focus_goal = 15
        priority_message = "Medium priority task - Focus 15 min"
    elif low_priority_task:
        daily_focus_goal = 10
        priority_message = "Low priority task - Focus 10 min"
    else:
        daily_focus_goal = 0
        priority_message = "No tasks today - You're all caught up!"
    
    # Calculate progress percentage (capped at 100%)
    if daily_focus_goal > 0:
        progress_percentage = min(100, int((current_user.focus_minutes_today / daily_focus_goal) * 100))
    else:
        progress_percentage = 100  # No tasks = 100% complete
    
    # Calculate budget balance (income - expenses)
    total_income = database.session.query(database.func.sum(Transaction.transaction_amount)).filter_by(
        user_id=current_user.id, transaction_type='income'
    ).scalar() or 0
    
    total_expenses = database.session.query(database.func.sum(Transaction.transaction_amount)).filter_by(
        user_id=current_user.id, transaction_type='expense'
    ).scalar() or 0
    
    # Count unlocked achievements (sum of boolean flags)
    unlocked_achievements_count = sum([
        current_user.achievement_first_login, 
        current_user.achievement_first_focus, 
        current_user.achievement_first_task, 
        current_user.achievement_first_note, 
        current_user.achievement_email_added
    ])
    
    return render_template('home.html',
        active_tasks_count=active_tasks_count,
        focus_minutes_today=current_user.focus_minutes_today,
        daily_focus_goal=daily_focus_goal,
        progress_percentage=progress_percentage,
        priority_message=priority_message,
        total_notes_count=total_notes_count,
        current_balance=round(total_income - total_expenses, 2),
        unlocked_count=unlocked_achievements_count,
        focus_points=current_user.total_focus_points
    )


# ==== Task Routes ====

@app.route('/timetable')
@login_required
def show_tasks_page():
    """
    Tasks page - list view and calendar view.
    Prepares JSON data for calendar JavaScript rendering.
    """
    # Query tasks separated by completion status
    incomplete_tasks = Task.query.filter_by(user_id=current_user.id, is_completed=False).order_by(Task.deadline_date).all()
    finished_tasks = Task.query.filter_by(user_id=current_user.id, is_completed=True).all()
    
    # Build JSON array for calendar rendering in JavaScript
    calendar_tasks_data = []
    for task in incomplete_tasks:
        calendar_tasks_data.append({
            'id': task.id,
            'title': task.task_title,
            'start_date': task.start_date.strftime('%Y-%m-%d') if task.start_date else None,
            'deadline_date': task.deadline_date.strftime('%Y-%m-%d') if task.deadline_date else None,
            'priority': task.priority_level
        })
    
    return render_template('timetable.html', 
        incomplete_tasks=incomplete_tasks, 
        finished_tasks=finished_tasks,
        calendar_tasks_data=calendar_tasks_data,
        current_date=date.today().strftime('%Y-%m-%d')  # For highlighting today
    )


@app.route('/task/add', methods=['POST'])
@login_required
def handle_add_task():
    """Create new task from form data."""
    task_title = request.form.get('title')
    start_date_string = request.form.get('start_date')
    deadline_date_string = request.form.get('deadline_date')
    priority_level = request.form.get('priority', 'medium')
    redirect_destination = request.form.get('redirect', 'timetable')  # Where to redirect after
    
    # Parse date strings to date objects
    start_date = datetime.strptime(start_date_string, '%Y-%m-%d').date() if start_date_string else date.today()
    deadline_date = datetime.strptime(deadline_date_string, '%Y-%m-%d').date() if deadline_date_string else None
    
    # Create and save new task
    new_task = Task(
        user_id=current_user.id,
        task_title=task_title,
        start_date=start_date,
        deadline_date=deadline_date,
        priority_level=priority_level
    )
    database.session.add(new_task)
    
    # Unlock "Task Starter" achievement on first task
    if not current_user.achievement_first_task:
        current_user.achievement_first_task = True
        flash('Achievement unlocked: Task Starter!', 'success')
    
    database.session.commit()
    flash('Task added!', 'success')
    
    # Redirect based on where task was created from
    return redirect(url_for('show_dashboard') if redirect_destination == 'home' else url_for('show_tasks_page'))


@app.route('/task/update', methods=['POST'])
@login_required
def handle_update_task():
    """Update existing task details."""
    task_id = request.form.get('task_id')
    
    # Find task belonging to current user
    found_task = Task.query.filter_by(id=task_id, user_id=current_user.id).first()
    
    if found_task:
        # Update all editable fields
        found_task.task_title = request.form.get('title')
        start_date_string = request.form.get('start_date')
        deadline_date_string = request.form.get('deadline_date')
        found_task.start_date = datetime.strptime(start_date_string, '%Y-%m-%d').date() if start_date_string else date.today()
        found_task.deadline_date = datetime.strptime(deadline_date_string, '%Y-%m-%d').date() if deadline_date_string else None
        found_task.priority_level = request.form.get('priority', 'medium')
        database.session.commit()
        flash('Task updated!', 'success')
    
    return redirect(url_for('show_tasks_page'))


@app.route('/task/toggle')
@login_required
def handle_toggle_task():
    """Toggle task completion status and award points."""
    task_id = request.args.get('id')
    
    found_task = Task.query.filter_by(id=task_id, user_id=current_user.id).first()
    
    if found_task:
        was_completed = found_task.is_completed
        found_task.is_completed = not found_task.is_completed  # Toggle status
        
        # Award points only when marking as complete (not when uncompleting)
        if found_task.is_completed and not was_completed:
            # Points based on priority: high=30, medium=20, low=10
            points_earned = {'high': 30, 'medium': 20, 'low': 10}.get(found_task.priority_level, 10)
            current_user.total_focus_points += points_earned
            flash(f'+{points_earned} points earned!', 'success')
        
        database.session.commit()
    
    return redirect(url_for('show_tasks_page'))


@app.route('/task/delete')
@login_required
def handle_delete_task():
    """Delete task permanently."""
    task_id = request.args.get('id')
    
    found_task = Task.query.filter_by(id=task_id, user_id=current_user.id).first()
    
    if found_task:
        database.session.delete(found_task)
        database.session.commit()
        flash('Task deleted', 'success')
    
    return redirect(url_for('show_tasks_page'))


# ==== Notes Routes ====

@app.route('/mynotes')
@login_required
def show_notes_page():
    """Display all notes sorted by most recently modified."""
    user_notes = Note.query.filter_by(user_id=current_user.id).order_by(Note.last_modified_at.desc()).all()
    return render_template('mynotes.html', user_notes=user_notes)


@app.route('/note/add', methods=['POST'])
@login_required
def handle_add_note():
    """Create new note from form data."""
    note_title = request.form.get('title', '')
    note_content = request.form.get('content', '')
    redirect_destination = request.form.get('redirect', 'mynotes')
    
    # Create and save new note
    new_note = Note(
        user_id=current_user.id,
        note_title=note_title,
        note_content=note_content
    )
    database.session.add(new_note)
    
    # Unlock "Note Taker" achievement on first note
    if not current_user.achievement_first_note:
        current_user.achievement_first_note = True
        flash('Achievement unlocked: Note Taker!', 'success')
    
    database.session.commit()
    flash('Note saved!', 'success')
    
    return redirect(url_for('show_dashboard') if redirect_destination == 'home' else url_for('show_notes_page'))


@app.route('/note/update', methods=['POST'])
@login_required
def handle_update_note():
    """Update existing note content."""
    note_id = request.form.get('note_id')
    
    found_note = Note.query.filter_by(id=note_id, user_id=current_user.id).first()
    
    if found_note:
        found_note.note_title = request.form.get('title', '')
        found_note.note_content = request.form.get('content', '')
        database.session.commit()  # Triggers auto-update of last_modified_at
        flash('Note updated!', 'success')
    
    return redirect(url_for('show_notes_page'))


@app.route('/note/delete')
@login_required
def handle_delete_note():
    """Delete note permanently."""
    note_id = request.args.get('id')
    
    found_note = Note.query.filter_by(id=note_id, user_id=current_user.id).first()
    
    if found_note:
        database.session.delete(found_note)
        database.session.commit()
        flash('Note deleted', 'success')
    
    return redirect(url_for('show_notes_page'))


# ==== Focus Timer Routes ====

@app.route('/focus')
@login_required
def show_focus_page():
    """
    Focus page with timer and Focus Farm gamification.
    
    Focus Farm Mechanic:
    - Complete sessions to earn stars
    - Stars produce energy over time (1 per star per 5 seconds in demo)
    - Collect energy to convert to points
    """
    current_time = datetime.utcnow()
    seconds_since_last_collection = (current_time - current_user.last_energy_collection_time).total_seconds()
    
    # Calculate accumulated energy: 1 energy per star per 5 seconds (demo mode)
    energy_accumulated = int(seconds_since_last_collection / 5) * current_user.stars_earned
    
    # Auto-collect accumulated energy to bank on page load
    if energy_accumulated > 0:
        current_user.energy_bank_balance += energy_accumulated
        current_user.last_energy_collection_time = current_time
        database.session.commit()
    
    return render_template('focus.html', 
        total_focus_points=current_user.total_focus_points,
        stars_earned=current_user.stars_earned,
        energy_bank_balance=current_user.energy_bank_balance
    )


@app.route('/focus/complete-session', methods=['POST'])
@login_required
def handle_session_complete():
    """
    API endpoint - called when focus timer completes.
    Awards: +1 star, +10 points, tracks daily minutes.
    Returns JSON for JavaScript to update UI.
    """
    request_data = request.get_json() or {}
    completed_minutes = request_data.get('minutes', 1)  # Minutes focused
    
    # Award rewards for completing session
    current_user.stars_earned += 1  # +1 star
    current_user.total_focus_points += 10  # +10 points
    current_user.last_energy_collection_time = datetime.utcnow()  # Reset energy timer
    
    # Track daily focus minutes (reset if new day)
    today = date.today()
    if current_user.focus_tracking_date != today:
        current_user.focus_minutes_today = 0
        current_user.focus_tracking_date = today
    current_user.focus_minutes_today += completed_minutes
    
    # Unlock "Focus Master" achievement
    if not current_user.achievement_first_focus:
        current_user.achievement_first_focus = True
    
    database.session.commit()
    
    # Return updated values for JavaScript
    return jsonify({
        'success': True, 
        'stars': current_user.stars_earned, 
        'focus_today': current_user.focus_minutes_today,
        'points': current_user.total_focus_points
    })


@app.route('/focus/add-points', methods=['POST'])
@login_required
def handle_add_focus_points():
    """API endpoint - adds collected energy as points."""
    request_data = request.get_json()
    points_to_add = request_data.get('points', 0)
    
    current_user.total_focus_points += points_to_add
    
    # Unlock achievement if earning points
    if not current_user.achievement_first_focus and points_to_add > 0:
        current_user.achievement_first_focus = True
    
    database.session.commit()
    
    return jsonify({
        'success': True,
        'total_points': current_user.total_focus_points
    })


# ==== Achievements Route ====

@app.route('/achievements')
@login_required
def show_achievements_page():
    """Display achievements with locked/unlocked status."""
    # Build status dictionary for template
    achievements_status = {
        'login': current_user.achievement_first_login,    # First Steps
        'focus': current_user.achievement_first_focus,    # Focus Master
        'task': current_user.achievement_first_task,      # Task Starter
        'note': current_user.achievement_first_note,      # Note Taker
        'email': current_user.achievement_email_added     # Connected
    }
    unlocked_count = sum(achievements_status.values())  # Count True values
    
    return render_template('achievements.html', 
        achievements_status=achievements_status, 
        unlocked_count=unlocked_count
    )


# ==== Budget Routes ====

@app.route('/budget')
@login_required
def show_budget_page():
    """
    Budget overview page.
    Shows: totals, weekly/monthly expenses, transactions list, savings goal.
    """
    # Get all transactions for list display
    recent_transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(
        Transaction.transaction_date.desc()
    ).all()
    
    # Calculate total income
    total_income = database.session.query(database.func.sum(Transaction.transaction_amount)).filter_by(
        user_id=current_user.id, 
        transaction_type='income'
    ).scalar() or 0
    
    # Calculate total expenses
    total_expenses = database.session.query(database.func.sum(Transaction.transaction_amount)).filter_by(
        user_id=current_user.id, 
        transaction_type='expense'
    ).scalar() or 0
    
    # Calculate weekly expenses (last 7 days)
    seven_days_ago = date.today() - timedelta(days=7)
    weekly_expenses = database.session.query(database.func.sum(Transaction.transaction_amount)).filter(
        Transaction.user_id == current_user.id,
        Transaction.transaction_type == 'expense',
        Transaction.transaction_date >= seven_days_ago
    ).scalar() or 0
    
    # Calculate monthly expenses (last 30 days)
    thirty_days_ago = date.today() - timedelta(days=30)
    monthly_expenses = database.session.query(database.func.sum(Transaction.transaction_amount)).filter(
        Transaction.user_id == current_user.id,
        Transaction.transaction_type == 'expense',
        Transaction.transaction_date >= thirty_days_ago
    ).scalar() or 0
    
    # Calculate estimated months to reach goal
    estimated_months_to_goal = None
    current_balance = total_income - total_expenses
    
    if current_user.savings_goal_target and current_balance > 0:
        # Estimate based on average monthly savings rate
        monthly_savings_rate = (total_income - total_expenses) / 12
        remaining_amount = current_user.savings_goal_target - current_balance
        
        if current_balance >= current_user.savings_goal_target:
            estimated_months_to_goal = 0  # Goal already reached
        else:
            estimated_months_to_goal = max(0, round(remaining_amount / max(1, monthly_savings_rate), 1))
    
    return render_template('budget.html',
        recent_transactions=recent_transactions,
        total_income=round(total_income, 2),
        total_expenses=round(total_expenses, 2),
        current_balance=round(current_balance, 2),
        weekly_expenses=round(weekly_expenses, 2),
        monthly_expenses=round(monthly_expenses, 2),
        estimated_months_to_goal=estimated_months_to_goal
    )


@app.route('/transaction/add', methods=['POST'])
@login_required
def handle_add_transaction():
    """Add new income or expense transaction."""
    new_transaction = Transaction(
        user_id=current_user.id,
        transaction_type=request.form.get('type'),  # 'income' or 'expense'
        transaction_description=request.form.get('description'),
        transaction_amount=float(request.form.get('amount')),
        transaction_category=request.form.get('category')
    )
    database.session.add(new_transaction)
    database.session.commit()
    
    flash('Transaction added!', 'success')
    return redirect(url_for('show_budget_page'))


@app.route('/goal/set', methods=['POST'])
@login_required
def handle_set_goal():
    """Set or update savings goal."""
    current_user.savings_goal_name = request.form.get('name')
    current_user.savings_goal_target = float(request.form.get('target'))
    
    database.session.commit()
    flash('Goal saved!', 'success')
    return redirect(url_for('show_budget_page'))


# ==== Settings Routes ====

@app.route('/settings')
@login_required
def show_settings_page():
    """Display settings page with user statistics."""
    # Aggregate user statistics for display
    user_statistics = {
        'tasks': Task.query.filter_by(user_id=current_user.id).count(),
        'notes': Note.query.filter_by(user_id=current_user.id).count(),
        'focus_points': current_user.total_focus_points
    }
    return render_template('settings.html', user_statistics=user_statistics)


@app.route('/settings/profile', methods=['POST'])
@login_required
def handle_update_profile():
    """Update user email address."""
    new_email = request.form.get('email', '').strip().lower()
    
    if new_email:
        # Check if email changed and is available
        if new_email != (current_user.email or '').lower():
            if User.query.filter(database.func.lower(User.email) == new_email).first():
                flash('Email already in use', 'error')
                return redirect(url_for('show_settings_page'))
            current_user.email = new_email
            current_user.achievement_email_added = True  # Unlock achievement
    else:
        current_user.email = None  # Allow removing email
    
    database.session.commit()
    flash('Profile updated!', 'success')
    return redirect(url_for('show_settings_page'))


@app.route('/settings/password', methods=['POST'])
@login_required
def handle_change_password():
    """Change user password with verification."""
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_new_password = request.form.get('confirm_password')
    
    # Verify current password is correct
    if not check_password_hash(current_user.password_hash, current_password):
        flash('Current password is incorrect', 'error')
        return redirect(url_for('show_settings_page'))
    
    # Verify new passwords match
    if new_password != confirm_new_password:
        flash('New passwords do not match', 'error')
        return redirect(url_for('show_settings_page'))
    
    # Update password hash
    current_user.password_hash = generate_password_hash(new_password)
    database.session.commit()
    
    flash('Password changed!', 'success')
    return redirect(url_for('show_settings_page'))


@app.route('/settings/delete', methods=['POST'])
@login_required
def handle_delete_account():
    """Delete user account and all associated data."""
    password = request.form.get('password')
    
    # Verify password before destructive action
    if not check_password_hash(current_user.password_hash, password):
        flash('Incorrect password', 'error')
        return redirect(url_for('show_settings_page'))
    
    # Delete all user data (cascade delete)
    Task.query.filter_by(user_id=current_user.id).delete()
    Note.query.filter_by(user_id=current_user.id).delete()
    Transaction.query.filter_by(user_id=current_user.id).delete()
    database.session.delete(current_user)
    database.session.commit()
    
    logout_user()  # Clear session
    flash('Account deleted', 'success')
    return redirect(url_for('show_landing_page'))


# ==== Initialization ====

def create_demo_account():
    """Create demo user for testing if it doesn't exist."""
    if not User.query.filter_by(username='artur').first():
        demo_user = User(
            username='artur',
            email='artur@demo.com',
            password_hash=generate_password_hash('123'),
            achievement_first_login=True,
            achievement_email_added=True
        )
        database.session.add(demo_user)
        database.session.commit()


# ==== Application Entry Point ====
if __name__ == '__main__':
    with app.app_context():
        database.create_all()
        create_demo_account()
    
    print('')
    print('========================================')
    print('   CHRONEX - Student Productivity App')
    print('========================================')
    print('')
    print('   Demo Account:')
    print('   Username: artur')
    print('   Password: 123')
    print('')
    print('   Open: http://localhost:5000')
    print('========================================')
    print('')
    
    app.run(debug=False, port=5000)
