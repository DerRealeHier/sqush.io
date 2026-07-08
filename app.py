import json
import os
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.testing.pickleable import User
from werkzeug.utils import secure_filename
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user,login_required
from werkzeug.security import check_password_hash, generate_password_hash
import stripe #juicy money XD
from dotenv import load_dotenv
from datetime import datetime, timezone

# Stripe API Keys.
load_dotenv()

app= Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")

stripe_keys = {
    "secret_key": os.environ.get("STRIPE_SECRET_KEY"),
    "publishable_key": os.environ.get("STRIPE_PUBLISHABLE_KEY"),
}

stripe.api_key = stripe_keys["secret_key"]

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.context_processor
def inject_models():
    return dict(Screenshot=Screenshot, Video=Video, Friendship=Friendship)

#secruity first huh? and then the Database
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///db.sqlite3"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

#Directory for Videos , Pictures and REAL GAME FILES. I wouldn't wanna pay for the Server ):
UPLOAD_FOLDER = "static/uploads"
AVATAR_FOLDER = "static/avatars"
app.config['AVATAR_FOLDER'] = AVATAR_FOLDER
os.makedirs(AVATAR_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok = True)
db = SQLAlchemy(app)




#Initiliaze Login
login_manager = LoginManager(app)
login_manager.login_view = "login" #YOU BETTER LOGIN

class Friendship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    status = db.Column(db.String(20), default='pending')

    sender = db.relationship("User", foreign_keys=[sender_id])
    receiver = db.relationship("User", foreign_keys=[receiver_id])

#Database model for my Users <)
class User(UserMixin, db.Model):
    profile_image = db.Column(db.String(250), default = "avatars/default.png")
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), nullable=False, unique=True)
    email = db.Column(db.String(128), nullable=False, unique=True) #trash-mails must be allowed
    password_hash = db.Column(db.String(250), nullable=False) #Quantum Computers shall fall
    role = db.Column(db.String(20), default="user") #you should be the dev
    #onlyfriends
    #followed = db.relationship("User", secondary=friends,
       # primaryjoin=(friends.c.user_id == id),
       # secondaryjoin=(friends.c.friend_id == id),
       # backref=db.backref('followers', lazy='dynamic'), lazy='dynamic'
    #)

    #linking more than just one game
    games = db.relationship("Game", backref="user", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


#Database Model for the games
class Game(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    title = db.Column(db.String(100),nullable = False)
    genre = db.Column(db.String(50),nullable = False)
    priority = db.Column(db.String(20),default = "normal")
    tags = db.Column(db.String(200)) # My lovely Tags. take them apart with: ,    BUT DON'T DO THIS THEY HAVE FAMILY
    price = db.Column (db.Float, nullable = False)
    view_count = db.Column(db.Integer, default=0) #We need the DATA!
    image_path = db.Column(db.String(250))
    video_path = db.Column(db.String(250)) # The link couldn't be that long (:
    #Marketplace Fields.
    description = db.Column(db.Text, nullable = True) #You could just have no description. Tell your Players nothing xD
    download_path = db.Column(db.String(250),nullable = False) #Better be able to find it
    is_on_sale = db.Column(db.Boolean, default = False)
    discount_percent = db.Column(db.Integer, default = 0) #Give them those 2%
    sale_end_date = db.Column(db.DateTime, nullable = True) #Can't keep on forever xD

    #My Foreign Key (:
    developer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable = False)

class Purchase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    game_id = db.Column(db.Integer, db.ForeignKey("game.id"), nullable=False)
    game = db.relationship("Game", backref="purchases")

class Screenshot(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    game_id = db.Column(db.Integer, db.ForeignKey("game.id"), nullable = False)
    image_path = db.Column(db.String(250), nullable = False)

class Video(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    game_id = db.Column(db.Integer, db.ForeignKey("game.id"), nullable = False)
    video_path = db.Column(db.String(250), nullable = False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

#initilaize the Database
with app.app_context():
    db.create_all()

#our lovely routes xD

def save_file(file):
    if file and file.filename:
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return f"uploads/{filename}"
    return None
def check_sales_expiry():
    now = datetime.now(timezone.utc)
    # Hole nur aktive Sales
    sales_to_check = Game.query.filter(Game.is_on_sale == True, Game.sale_end_date != None).all()
    changed = False

    for game in sales_to_check:
        db_date = game.sale_end_date
        if db_date.tzinfo is None:
            db_date = db_date.replace(tzinfo=timezone.utc)
        if db_date < now:
            game.is_on_sale = False
            game.discount_percent = 0
            game.sale_end_date = None
            changed = True
            print(f"DEBUG: Sale for {game.title} expired.")

    if changed:
        db.session.commit()

@app.route("/send_friend_request/<int:user_id>")
@login_required
def send_request(user_id):
    #dont want them to spam friend request
    existing = Friendship.query.filter_by(sender_id=current_user.id, receiver_id=user_id).first()
    if not existing:
        req = Friendship(sender_id=current_user.id, receiver_id=user_id, status="pending")
        db.session.add(req)
        db.session.commit()
    return redirect(url_for("profile", username=User.query.get(user_id).username))

@app.route("/accept_friend_request/<int:request_id>")
@login_required
def accept_request(request_id):
    req = Friendship.query.get_or_404(request_id)
    if req.receiver_id == current_user.id:
        req.status = "accepted"
        db.session.commit()
    return redirect(url_for("profile", username=current_user.username))

#authentication routes.
@app.route("/register", methods = ["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        role = request.form["role"]

        if User.query.filter_by(username=username).first() or User.query.filter_by(email=email).first():
            return "Username or Email exists! Be faster next time xD", 400

        new_user = User(username=username, email=email, role=role)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for("login"))
    return render_template("register.html")

#Lets Lock in
@app.route("/login", methods = ["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            if user.role == "dev":
                return redirect(url_for("developer_dashboard"))
            return redirect(url_for("profile", username=user.username))
        return "Invalid username or password"
    return render_template("login.html")

@app.route("/follow/<username>")
@login_required
def follow(username):
    user = User.query.filter_by(username=username).first()
    if user and user != current_user:
        current_user.followed.append(user)
        db.session.commit()
    return redirect(url_for('profile', username=username))

@app.route('/unfollow/<username>')
@login_required
def unfollow(username):
    user = User.query.filter_by(username=username).first()
    if user:
        #finding if they are even friends. Better be!
        friendship = Friendship.query.filter(
            ((Friendship.sender_id == current_user.id) & (Friendship.receiver_id == user.id)) |
            ((Friendship.sender_id == user.id) & (Friendship.receiver_id == current_user.id))
        ).first()
        if friendship:
            db.session.delete(friendship)
            db.session.commit()
    return redirect(url_for('profile', username=username))
@app.route("/increment_view/<int:game_id>", methods = ["POST"])
def increment_view(game_id):
    game = Game.query.get_or_404(game_id)
    game.view_count += 1
    db.session.commit()
    return jsonify({"status": "success", "views": game.view_count})

@app.route("/update_profile", methods=["POST"])
@login_required
def update_profile():
    file = request.files.get("profile_pic")
    if file and file.filename != "" and allowed_file(file.filename):
        filename = secure_filename(f"user_{current_user.id}_{file.filename}")
        file.save(os.path.join(app.config["AVATAR_FOLDER"], filename))
        current_user.profile_image = f"avatars/{filename}"
        db.session.commit()
    else:
        return "Not allowed. ONLY PICTURES!", 400
    return redirect(url_for("profile", username=current_user.username))

@app.route("/profile/<username>")
@login_required
def profile(username):
    target_user = User.query.filter_by(username=username).first_or_404()
    return render_template("profile.html", user=target_user)
#You shouldn't even wanna do this. 🤬
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))

@app.route("/purchase/<int:game_id>", methods = ["POST"])
@login_required
def purchase(game_id):
    #Rather not buy it twice
    if Purchase.query.filter_by(user_id=current_user.id, game_id=game_id).first():
        return "Brochacho, you already own that", 400
    new_purchase = Purchase(user_id=current_user.id, game_id=game_id)
    db.session.add(new_purchase)
    db.session.commit()
    return redirect(url_for("library"))

#This is for the home Page.
@app.route("/")
def home():
    check_sales_expiry() #checking
    sale_games = Game.query.filter_by(is_on_sale=True).all()

    for game in sale_games:
        game.display_price = game.price * (1 - game.discount_percent / 100)

    return render_template('home.html', sale_games=sale_games)

@app.route("/library")
@login_required
def library():
    #What did the user already buy? Money go brrr xD
    purchases = Purchase.query.filter_by(user_id=current_user.id).all()
    #get those game objects
    owned_games = [Game.query.get(p.game_id) for p in purchases]
    return render_template("library.html", games=owned_games)

@app.route("/community", methods=["GET","POST"])
def community():
    query = request.form.get("search") if request.method == "POST" else None
    if query:
        users = User.query.filter(User.username.ilike(f"%{query}%")).all()
    else:
        users = User.query.all()

    return render_template("community.html", users=users)


@app.route("/buy/<int:game_id>", methods = ["GET", "POST"])
def buy(game_id):
    game = Game.query.get_or_404(game_id)
    if game.is_on_sale and game.discount_percent > 0:
        game.display_price = game.price * (1 - game.discount_percent / 100)
    else:
        game.display_price = game.price
    return render_template("buy.html", game=game)

#Store Page
@app.route("/store")
def store_front():
    all_games = Game.query.all()
    #Sorting them after their genre.
    games_by_genre = {}
    for game in all_games: #while true loop would be great here (; The performance would go crazy
        tags = [t.strip().lower() for t in game.tags.split(",")] if game.tags else []
        game.tags_json = json.dumps(tags)
        if game.is_on_sale == True and game.discount_percent > 0:
            game.display_price = game.price * (1 - game.discount_percent / 100)
        else:
            game.display_price = game.price

        if game.genre not in games_by_genre:
            games_by_genre[game.genre] = []

        games_by_genre[game.genre].append(game)
    return render_template("store.html", genres=games_by_genre)

@app.route("/create-checkout-session/<int:game_id>")
def create_checkout_session(game_id):
    game = Game.query.get_or_404(game_id)
    stripe.api_key = stripe_keys["secret_key"]

    display_price = game.price * (1 - game.discount_percent / 100) if game.is_on_sale else game.price
    unit_amount = int(display_price * 100)

    try:
        checkout_session = stripe.checkout.Session.create(
            success_url=url_for("success", game_id=game.id, _external=True),
            cancel_url=url_for("game_detail", game_id=game.id, _external=True),
            payment_method_types=["card"],
            mode="payment",
            line_items=[
                {
                    "price_data": {

                        "currency": "eur",
                        "product_data": {
                            "name": game.title,
                        },
                        "unit_amount": unit_amount,
                    },
                    "quantity": 1,
                }
            ]
        )
        return jsonify({"sessionId": checkout_session["id"]})
    except Exception as e:
        return jsonify(error=str(e)), 403

@app.route("/success/<int:game_id>")
@login_required
def success(game_id):
    if not Purchase.query.filter_by(user_id=current_user.id, game_id=game_id).first():
        new_purchase = Purchase(user_id=current_user.id, game_id=game_id)
        db.session.add(new_purchase)
        db.session.commit()

    game= Game.query.get_or_404(game_id)
    return render_template("success.html", game=game)

@app.route("/remove_purchase/<int:game_id>", methods=["POST"])
def remove_purchase(game_id):
    purchase = Purchase.query.filter_by(user_id=current_user.id, game_id=game_id).first()

    if purchase:
        db.session.delete(purchase)
        db.session.commit()

    return redirect(url_for("library"))

#This Server would cry
@app.route("/game/<int:game_id>")
def game_detail(game_id):
    game = Game.query.get_or_404(game_id)
    screenshots = Screenshot.query.filter_by(game_id=game.id).all()
    videos = Video.query.filter_by(game_id=game.id).all()
    #Lets do Math (:
    if game.is_on_sale and game.discount_percent > 0:
        game.display_price = game.price * (1 - game.discount_percent / 100)
    else:
        game.display_price = game.price

    return render_template("game_detail.html",game=game, screenshots=screenshots, videos=videos)

@app.route("/edit_game/<int:game_id>", methods = ["GET", "POST"])
def edit_game(game_id):
    game = Game.query.get_or_404(game_id)
    if current_user.role != "dev":
        return "Access Denied. How could you?", 403
    if game.developer_id != current_user.id:
        return "Access Denied: Better Luck next time (:", 403

    if request.method == "POST":
        game.title = request.form["title"]
        game.price = float(request.form["price"])
        game.description = request.form.get("description")
        game.is_on_sale = "is_on_sale" in request.form
        game.discount_percent = int(request.form.get("discount_percent", 0))

        files = request.files.getlist("screenshots")
        for f in files:
            if f and f.filename:
                path = save_file(f)
                db.session.add(Screenshot(game_id=game.id,image_path=path))

        video_files = request.files.getlist("videos")
        for v in video_files:
            path = save_file(v)
            if path:
                db.session.add(Video(game_id=game.id,video_path=path))


        db.session.commit()
        return redirect(url_for("developer_dashboard"))
    return render_template("edit_game.html",game=game)
@app.route("/config")
def get_publishable_key():
    stripe_config = {"publicKey": stripe_keys["publishable_key"]}
    return jsonify(stripe_config)
#It's a dev panel now ):
@app.route("/dashboard", methods=["GET" , "POST"])
@login_required
def developer_dashboard():
    if current_user.role != "dev":
        return "Access Denied: Better Luck next time (:", 403

    sale_end_date = None
    if request.method == "POST":#
        sale_end_date_str = request.form.get("sale_end_date")
        if sale_end_date_str:
            try:
                sale_end_date = datetime.strptime(sale_end_date_str, "%Y-%m-%dT%H:%M")
            except ValueError:
                sale_end_date = None


    if request.method == "POST":
        title = request.form["title"]
        genre = request.form["genre"]
        priority = request.form.get("priority", "normal")
        tags = request.form["tags"]
        price = float(request.form["price"])
        description = request.form.get("description")
        is_on_sale = "is_on_sale" in request.form
        discount_percent = int(request.form.get("discount_percent", 0))

        image_file = request.files.get("image")
        uploaded_video = request.files.get("video_file")
        video_youtube = request.form.get("video_youtube", "").strip()
        game_file = request.files.get("game_file")

        image_path = save_file(image_file) if image_file else ""

        if uploaded_video and uploaded_video.filename:
            video_path = save_file(uploaded_video)
        elif video_youtube:
            if "v=" in video_youtube:
                yt_id = video_youtube.split("v=")[1].split("&")[0]
            elif "youtu.be/" in video_youtube:
                yt_id = video_youtube.split("youtu.be/")[1].split("?")[0]
            else:
                yt_id = video_youtube
            video_path = f"youtube:{yt_id}"
        else:
            video_path = "https://www.youtube.com/watch?v=E4WlUXrJgy4"

        download_path = save_file(game_file) if game_file else ""

        new_game = Game(title=title, genre=genre, priority=priority, tags=tags, price=price,
                        image_path=image_path, video_path=video_path, description=description,
                        download_path=download_path, is_on_sale=is_on_sale, sale_end_date=sale_end_date,
                        discount_percent=discount_percent, developer_id=current_user.id)

        db.session.add(new_game)
        db.session.commit()

        files = request.files.getlist("screenshots")
        for f in files:
            path = save_file(f)
            if path:
                db.session.add(Screenshot(game_id=new_game.id, image_path=path))

        db.session.commit()
        return redirect(url_for("store_front"))

    my_games = Game.query.filter_by(developer_id=current_user.id).all()
    for game in my_games:
        game.display_price = game.price * (1 - game.discount_percent / 100) if game.is_on_sale else game.price
    return render_template("admin.html", games=my_games)

if __name__ == "__main__":
    app.run(debug = True)