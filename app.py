from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
from datetime import datetime
import razorpay

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///odbyte.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Fix for PostgreSQL URI
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)

db = SQLAlchemy(app)

# Razorpay Configuration
RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', 'rzp_test_your_key_id')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', 'your_key_secret')
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    plan = db.Column(db.String(20), default='free')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    prompts = db.relationship('Prompt', backref='author', lazy=True, cascade='all, delete-orphan')
    favorites = db.relationship('Favorite', backref='user', lazy=True, cascade='all, delete-orphan')

class Prompt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    content = db.Column(db.Text, nullable=False)
    tags = db.Column(db.String(500))
    category = db.Column(db.String(100))
    ai_model = db.Column(db.String(100))
    visibility = db.Column(db.String(20), default='private')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    favorites = db.relationship('Favorite', backref='prompt', lazy=True, cascade='all, delete-orphan')

class Favorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    prompt_id = db.Column(db.Integer, db.ForeignKey('prompt.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.String(200), nullable=False)
    order_id = db.Column(db.String(200))
    amount = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(10), default='INR')
    status = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered!', 'error')
            return redirect(url_for('signup'))
        
        hashed_password = generate_password_hash(password)
        new_user = User(name=name, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Account created successfully! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['user_name'] = user.name
            session['user_plan'] = user.plan
            flash(f'Welcome back, {user.name}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password!', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        flash('Session expired. Please login again.', 'error')
        return redirect(url_for('login'))
    
    prompts = Prompt.query.filter_by(user_id=user.id).order_by(Prompt.created_at.desc()).all()
    prompt_count = len(prompts)
    return render_template('dashboard.html', user=user, prompts=prompts, prompt_count=prompt_count)

@app.route('/prompt/new', methods=['GET', 'POST'])
@login_required
def new_prompt():
    user = User.query.get(session['user_id'])
    
    if request.method == 'POST':
        if user.plan == 'free':
            prompt_count = Prompt.query.filter_by(user_id=user.id).count()
            if prompt_count >= 10:
                flash('Free plan limit reached! Upgrade to Premium for unlimited prompts.', 'error')
                return redirect(url_for('dashboard'))
        
        title = request.form.get('title')
        description = request.form.get('description')
        content = request.form.get('content')
        tags = request.form.get('tags')
        category = request.form.get('category')
        ai_model = request.form.get('ai_model')
        visibility = request.form.get('visibility', 'private')
        
        new_prompt = Prompt(
            title=title,
            description=description,
            content=content,
            tags=tags,
            category=category,
            ai_model=ai_model,
            visibility=visibility,
            user_id=user.id
        )
        
        db.session.add(new_prompt)
        db.session.commit()
        
        flash('Prompt saved successfully!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('new_prompt.html', user=user)

@app.route('/prompt/<int:id>')
def view_prompt(id):
    prompt = Prompt.query.get_or_404(id)
    
    if prompt.visibility == 'private':
        if 'user_id' not in session or session['user_id'] != prompt.user_id:
            flash('This prompt is private!', 'error')
            return redirect(url_for('explore'))
    
    is_favorited = False
    if 'user_id' in session:
        is_favorited = Favorite.query.filter_by(user_id=session['user_id'], prompt_id=id).first() is not None
    
    return render_template('view_prompt.html', prompt=prompt, is_favorited=is_favorited)

@app.route('/prompt/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_prompt(id):
    prompt = Prompt.query.get_or_404(id)
    
    if prompt.user_id != session['user_id']:
        flash('Unauthorized access!', 'error')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        prompt.title = request.form.get('title')
        prompt.description = request.form.get('description')
        prompt.content = request.form.get('content')
        prompt.tags = request.form.get('tags')
        prompt.category = request.form.get('category')
        prompt.ai_model = request.form.get('ai_model')
        prompt.visibility = request.form.get('visibility', 'private')
        
        db.session.commit()
        flash('Prompt updated successfully!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('edit_prompt.html', prompt=prompt)

@app.route('/prompt/<int:id>/delete', methods=['POST'])
@login_required
def delete_prompt(id):
    prompt = Prompt.query.get_or_404(id)
    
    if prompt.user_id != session['user_id']:
        flash('Unauthorized access!', 'error')
        return redirect(url_for('dashboard'))
    
    db.session.delete(prompt)
    db.session.commit()
    flash('Prompt deleted successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/explore')
def explore():
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    ai_model = request.args.get('ai_model', '')
    
    query = Prompt.query.filter_by(visibility='public')
    
    if search:
        query = query.filter(
            (Prompt.title.contains(search)) | 
            (Prompt.description.contains(search)) |
            (Prompt.tags.contains(search))
        )
    
    if category:
        query = query.filter_by(category=category)
    
    if ai_model:
        query = query.filter_by(ai_model=ai_model)
    
    prompts = query.order_by(Prompt.created_at.desc()).all()
    
    categories = db.session.query(Prompt.category).filter_by(visibility='public').distinct().all()
    ai_models = db.session.query(Prompt.ai_model).filter_by(visibility='public').distinct().all()
    
    return render_template('explore.html', 
                         prompts=prompts, 
                         categories=[c[0] for c in categories if c[0]], 
                         ai_models=[m[0] for m in ai_models if m[0]])

@app.route('/favorites')
@login_required
def favorites():
    user_favorites = Favorite.query.filter_by(user_id=session['user_id']).all()
    favorite_prompts = [fav.prompt for fav in user_favorites]
    return render_template('favorites.html', prompts=favorite_prompts)

@app.route('/favorite/<int:prompt_id>', methods=['POST'])
@login_required
def toggle_favorite(prompt_id):
    existing = Favorite.query.filter_by(user_id=session['user_id'], prompt_id=prompt_id).first()
    
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({'status': 'removed', 'message': 'Removed from favorites'})
    else:
        new_favorite = Favorite(user_id=session['user_id'], prompt_id=prompt_id)
        db.session.add(new_favorite)
        db.session.commit()
        return jsonify({'status': 'added', 'message': 'Added to favorites'})

@app.route('/upgrade')
@login_required
def upgrade():
    user = User.query.get(session['user_id'])
    if user.plan == 'premium':
        flash('You are already a Premium user!', 'info')
        return redirect(url_for('dashboard'))
    return render_template('upgrade.html', razorpay_key=RAZORPAY_KEY_ID)

@app.route('/create-order', methods=['POST'])
@login_required
def create_order():
    amount = 49900
    
    order_data = {
        'amount': amount,
        'currency': 'INR',
        'payment_capture': 1
    }
    
    order = razorpay_client.order.create(data=order_data)
    
    return jsonify({
        'order_id': order['id'],
        'amount': amount,
        'currency': 'INR',
        'key': RAZORPAY_KEY_ID
    })

@app.route('/payment-success', methods=['POST'])
@login_required
def payment_success():
    payment_id = request.form.get('razorpay_payment_id')
    order_id = request.form.get('razorpay_order_id')
    signature = request.form.get('razorpay_signature')
    
    try:
        razorpay_client.utility.verify_payment_signature({
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature
        })
        
        user = User.query.get(session['user_id'])
        user.plan = 'premium'
        
        payment = Payment(
            payment_id=payment_id,
            order_id=order_id,
            amount=49900,
            status='success',
            user_id=user.id
        )
        
        db.session.add(payment)
        db.session.commit()
        
        session['user_plan'] = 'premium'
        flash('Payment successful! Welcome to Premium!', 'success')
        return redirect(url_for('payment_success_page'))
    
    except:
        flash('Payment verification failed!', 'error')
        return redirect(url_for('upgrade'))

@app.route('/success')
@login_required
def payment_success_page():
    return render_template('success.html')

# Initialize database tables on startup
def init_db():
    with app.app_context():
        try:
            db.create_all()
            print("=" * 50)
            print("✅ Database tables created successfully!")
            print("=" * 50)
        except Exception as e:
            print("=" * 50)
            print(f"❌ Error creating database tables: {e}")
            print("=" * 50)

# Run initialization
init_db()

# Add these new routes to your app.py

# Add this near the top with other imports
from datetime import datetime

# Add these routes BEFORE the "if __name__ == '__main__':" line

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy_policy.html')

@app.route('/terms-of-service')
def terms_of_service():
    return render_template('terms_of_service.html')


@app.route('/newsletter')
def newsletter():
    return render_template('newsletter.html')
    
    @app.route('/pricing')
def pricing():
    return render_template('pricing.html')

@app.route('/newsletter/subscribe', methods=['POST'])
def newsletter_subscribe():
    email = request.form.get('email')
    # Here you can add logic to save email to database
    # For now, just flash a success message
    flash('Thanks for subscribing! Check your inbox for confirmation.', 'success')
    return redirect(url_for('newsletter'))

@app.route('/blog')
def blog():
    # For now, empty posts list. You can add posts later in database
    posts = []
    return render_template('blog.html', posts=posts)

@app.route('/blog/<slug>')
def blog_post(slug):
    # Sample structure - you'll add actual posts to database later
    flash('Blog post coming soon!', 'info')
    return redirect(url_for('blog'))

if __name__ == '__main__':
    app.run(debug=True)
    
