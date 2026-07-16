import json
import os
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from werkzeug.security import check_password_hash, generate_password_hash
import stripe #juicy money XD
from dotenv import load_dotenv
from datetime import datetime, timezone
from flask_migrate import Migrate

# Stripe API Keys.
load_dotenv()
app = Flask(__name__)
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
def inject_global_data():
    data = {
        "Screenshot": Screenshot,
        "Video": Video,
        "Friendship": Friendship
    }
    if current_user.is_authenticated:
        try:
            unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
            data["unread_count"] = unread_count
        except Exception as e:
            print(f"DEBUG: Notification Fehler: {e}")
            data["unread_count"] = 0

        try:
            wishlist_ids = {w.game_id for w in Wishlist.query.filter_by(user_id=current_user.id).all()}
            data["wishlist_ids"] = wishlist_ids
        except Exception as e:
            print(f"DEBUG: Wishlist Fehler: {e}")
            data["wishlist_ids"] = set()
    else:
        data["unread_count"] = 0
        data["wishlist_ids"] = set()

    return data


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
    comments_enabled = db.Column(db.Boolean, default=True)# profile owner can turn comments off completely
    followed = db.relationship("User", secondary = Friendship.__table__, #make some friends
                               primaryjoin = (Friendship.sender_id == id),
                               secondaryjoin=(Friendship.receiver_id == id),
                               backref="followers", lazy="dynamic"
                               )
    #linking more than just one game
    games = db.relationship("Game", backref="user", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False) #Who needs Info?
    message = db.Column(db.String(250), nullable=False)
    type = db.Column(db.String(50))
    is_read = db.Column(db.Boolean, default = False)
    # yeah it wasnt aware of time-zones before. Happens xD
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    user = db.relationship("User" , backref="notifications")


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
    description = db.Column(db.Text, nullable = True) #You could just have no description. Tell your Players nothing xD
    download_path = db.Column(db.String(250),nullable = False) #Better be able to find it
    demo_path = db.Column(db.String(250), nullable = True)#optional demo
    is_on_sale = db.Column(db.Boolean, default = False)
    discount_percent = db.Column(db.Integer, default = 0) #Give them those 2%
    sale_end_date = db.Column(db.DateTime, nullable = True) #Can't keep on forever xD
    reviews = db.relationship("Review", backref="game", lazy=True)
    #My Foreign Key (:
    developer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable = False)

class Purchase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    game_id = db.Column(db.Integer, db.ForeignKey("game.id"), nullable=False)
    price_paid = db.Column(db.Float, nullable=True)  # what it actually cost at purchase time
    purchased_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    game = db.relationship("Game", backref="purchases")

class Wishlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    game_id = db.Column(db.Integer, db.ForeignKey("game.id"), nullable=False)
    added_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    game = db.relationship("Game", backref="wishlisted_by")
    user = db.relationship("User", backref="wishlist_entries")
    #one game per user on the wishlist
    __table_args__ = (db.UniqueConstraint('user_id', 'game_id', name='unique_wishlist'),)

class GameStats(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey("game.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    views = db.Column(db.Integer, default=0)
    wishlist_count = db.Column(db.Integer, default=0)
    purchase_count = db.Column(db.Integer, default=0)
    revenue = db.Column(db.Float, default=0.0)  # snapshot of all the revenue for that day

    game = db.relationship("Game", backref="stats_history")
    # one snapshot per game per day(its getting updated not a new datapoint everys day)
    __table_args__ = (db.UniqueConstraint('game_id', 'date', name='unique_game_stat_day'),)

class ProfileComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # whose profile the comment was posted on
    profile_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    # who wrote the comment? It's me xD
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    profile_user = db.relationship("User", foreign_keys=[profile_user_id], backref="profile_comments")
    author = db.relationship("User", foreign_keys=[author_id])


class Screenshot(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    game_id = db.Column(db.Integer, db.ForeignKey("game.id"), nullable = False)
    image_path = db.Column(db.String(250), nullable = False)

class Video(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    game_id = db.Column(db.Integer, db.ForeignKey("game.id"), nullable = False)
    video_path = db.Column(db.String(250), nullable = False)

class Review(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    game_id = db.Column(db.Integer, db.ForeignKey("game.id"), nullable=False)
    is_positive = db.Column(db.Boolean, nullable = False)
    comment = db.Column(db.Text, nullable = True)
    helpful_count = db.Column(db.Integer, default=0)
    funny_count = db.Column(db.Integer, default=0)
    user = db.relationship("User", backref="reviews")
    votes = db.relationship("ReviewVote", backref="review", lazy=True)

class ReviewVote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey("review.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    vote_type = db.Column(db.String(10), nullable=False)  # "helpful" or "funny". SteamLike xD
    __table_args__ = (db.UniqueConstraint('review_id', 'user_id', 'vote_type', name='unique_vote'),)

@login_manager.user_loader
def load_user(user_id):
    # Always had these messages that Query.get is legacy. so I changed it.
    return db.session.get(User, int(user_id))

#initilaize the Database
with app.app_context():
    print("DEBUG: Prüfe Notification Table Spalten")
    db.create_all()

#our lovely routes xD

def save_file(file, folder=None):
    #the save logic is not duplicated anymore
    target_folder = folder or app.config['UPLOAD_FOLDER']
    if file and file.filename:
        filename = secure_filename(file.filename)
        file.save(os.path.join(target_folder, filename))
        relative_folder = os.path.basename(target_folder)
        return f"{relative_folder}/{filename}"
    return None

def calculate_game_revenue(game):
    # yea you aint getting the old money back.
    total = 0
    for p in game.purchases:
        total += p.price_paid if p.price_paid is not None else calculate_display_price(game)
    return total

def calculate_display_price(game):
    #I had this in like all functions. Now I have an own one for it.
    if game.is_on_sale and game.discount_percent > 0:
        return game.price * (1 - game.discount_percent / 100)
    return game.price

#dont wanna end up with doing this several times over the code base
#also we take the length of the review into account. It does not change it that much but you understand?
def calculate_review_score(review):
    text_len = len(review.comment or "")
    length_factor = min(text_len / 200, 1.0)  # ab 200 Zeichen voller Bonus
    return (review.helpful_count * 2) + (review.funny_count * 1) + (length_factor * 3)


def _get_tag_set(game):
    # small helper so we don't repeat all again and again.
    if not game.tags:
        return set()
    return {t.strip().lower() for t in game.tags.split(",") if t.strip()}


def get_popular_games(exclude_ids=None, limit=6):
    # Fallback for empty libraries or when nothing else scores
    exclude_ids = exclude_ids or set()
    query = Game.query
    if exclude_ids:
        query = query.filter(~Game.id.in_(exclude_ids))
    candidates = query.all()
    candidates.sort(key=lambda g: len(g.purchases), reverse=True)
    return candidates[:limit]


def get_recommended_games(user, limit=6):
    """
    All of this code is fine for a small store, but it's not going to scale well...
    Its because of the Game.query.all() call. If you wanna use this for a large store, you should
    use real tag tables! If you dont then it might become a problem.
    """
    if not user.is_authenticated:
        return []

    my_owned_ids = {p.game_id for p in Purchase.query.filter_by(user_id=user.id).all()}

    if not my_owned_ids:
        # Fresh account; I'll recommend the most popular games. xD
        return get_popular_games(exclude_ids=set(), limit=limit)

    all_games = Game.query.all()
    games_by_id = {g.id: g for g in all_games}

    # mmy personal tag cloud build from everything I own ):
    my_tags = set()
    for gid in my_owned_ids:
        game = games_by_id.get(gid)
        if game:
            my_tags |= _get_tag_set(game)

    all_purchases = Purchase.query.all()
    # yea im going into both directions.
    owners_by_game = {}
    games_by_user = {}
    for p in all_purchases:
        owners_by_game.setdefault(p.game_id, set()).add(p.user_id)
        games_by_user.setdefault(p.user_id, set()).add(p.game_id)

    # Who owns at least one game with a same tag as mine?
    tag_similar_user_ids = set()
    if my_tags:
        for uid, gids in games_by_user.items():
            if uid == user.id:
                continue
            for gid in gids:
                owned_game = games_by_id.get(gid)
                if owned_game and (_get_tag_set(owned_game) & my_tags):
                    tag_similar_user_ids.add(uid)
                    break

    # Who shares at least one game with my library?
    similar_library_user_ids = {
        uid for uid, gids in games_by_user.items()
        if uid != user.id and (gids & my_owned_ids)
    }

    wishlisters_by_game = {}
    for w in Wishlist.query.all():
        wishlisters_by_game.setdefault(w.game_id, set()).add(w.user_id)

    scores = {}
    for game in all_games:
        if game.id in my_owned_ids:
            continue  # you already own it, go buy it for your friend. (Just found out that I don't have this feature yet xD)

        owners = owners_by_game.get(game.id, set())
        wishlisters = wishlisters_by_game.get(game.id, set())

        tag_score = len(owners & tag_similar_user_ids)
        popularity_score = len(owners)
        similar_wishlist_score = len(wishlisters & similar_library_user_ids)

        # yeah popularity is the least important factor, but it's still there.'
        total_score = (tag_score * 3) + (similar_wishlist_score * 2) + (popularity_score * 1)

        if total_score > 0:
            scores[game.id] = total_score

    if not scores:
        #nothing matched so its kept empty
        return get_popular_games(exclude_ids=my_owned_ids, limit=limit)

    top_ids = sorted(scores, key=lambda gid: scores[gid], reverse=True)[:limit]
    return [games_by_id[gid] for gid in top_ids]


def update_daily_stats(game):
    # one row per day.
    today = datetime.now(timezone.utc).date()
    entry = GameStats.query.filter_by(game_id=game.id, date=today).first()

    wishlist_count = Wishlist.query.filter_by(game_id=game.id).count()
    purchase_count = Purchase.query.filter_by(game_id=game.id).count()
    revenue = calculate_game_revenue(game)

    if entry:
        entry.views = game.view_count
        entry.wishlist_count = wishlist_count
        entry.purchase_count = purchase_count
        entry.revenue = revenue
    else:
        entry = GameStats(
            game_id=game.id,
            date=today,
            views=game.view_count,
            wishlist_count=wishlist_count,
            purchase_count=purchase_count,
            revenue=revenue
        )
        db.session.add(entry)

    db.session.commit()

def check_sales_expiry():
    now = datetime.now(timezone.utc)
    # only get active sales.
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
    target_user = db.session.get(User, user_id)
    if not existing and target_user:
        req = Friendship(sender_id=current_user.id, receiver_id=user_id, status="pending")
        db.session.add(req)
        #adding those notifications
        notif = Notification(
            user_id=user_id,
            message=f"{current_user.username} wants to be friends (;",
            type="fried_request"
        )
        db.session.add(notif)
        db.session.commit()
    return redirect(url_for("profile", username=target_user.username))

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

@app.route("/rate_game/<int:game_id>", methods = ["POST"])
@login_required
def rate_game(game_id):
    rating = request.form.get("rating") # "1" for good; "0" for bad
    comment = request.form.get("comment")
    existing = Review.query.filter_by(user_id=current_user.id, game_id=game_id).first()

    if existing:
        existing.is_positive = (rating == "1")
        existing.comment = comment #update comment
    else:
        # before it compared a String with an Int so it was always false.
        new_review = Review(user_id=current_user.id, game_id=game_id, is_positive=(rating == "1"),
                            comment=comment)

        db.session.add(new_review)


    db.session.commit()
    return redirect(url_for("game_detail", game_id=game_id))


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


#clicking twice makes the vote disappear. Pretty basic
@app.route("/vote_review/<int:review_id>/<vote_type>", methods=["POST"])
@login_required
def vote_review(review_id, vote_type):
    if vote_type not in ("helpful", "funny"):
        return "Invalid vote type", 400
    review = Review.query.get_or_404(review_id)

    if review.helpful_count is None:
        review.helpful_count = 0
    if review.funny_count is None:
        review.funny_count = 0

    existing = ReviewVote.query.filter_by(
        review_id=review_id, user_id=current_user.id, vote_type=vote_type
    ).first()
    if existing:
        db.session.delete(existing)
        if vote_type == "helpful":
            review.helpful_count -= 1
        else:
            review.funny_count -= 1
    else:
        db.session.add(ReviewVote(review_id=review_id, user_id=current_user.id, vote_type=vote_type))
        if vote_type == "helpful":
            review.helpful_count += 1
        else:
            review.funny_count += 1

    db.session.commit()
    return jsonify({"helpful": review.helpful_count, "funny": review.funny_count})

@app.route("/notification/read/<int:notif_id>")
@login_required
def read_notification(notif_id):
    notif = Notification.query.get_or_404(notif_id)
    #Is it really the notification of the user?
    if notif.user_id == current_user.id:
        notif.is_read = True
        db.session.commit()
    if notif.type == "fried_request":
        sender_name = notif.message.split(" ")[0]
        sender = User.query.filter_by(username=sender_name).first()
        if sender:
            return redirect(url_for('profile', username=sender.username))

    return redirect(url_for("profile", username=current_user.username))



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
    # there was some unique bug
    friend_request = Friendship.query.filter(
        ((Friendship.sender_id == current_user.id) & (Friendship.receiver_id == target_user.id)) |
        ((Friendship.sender_id == target_user.id) & (Friendship.receiver_id == current_user.id))
    ).first()

    # newest comments first. Who comes first is last ;)
    comments = ProfileComment.query.filter_by(profile_user_id=target_user.id) \
        .order_by(ProfileComment.created_at.desc()).all()

    return render_template(
        "profile.html",
        user=target_user,
        friend_request=friend_request,
        comments=comments
    )


@app.route("/profile/<username>/comment", methods=["POST"])
@login_required
def post_profile_comment(username):
    target_user = User.query.filter_by(username=username).first_or_404()

    # respect the owner's setting. We aren't assholes (:
    if not target_user.comments_enabled:
        return "Comments are disabled on this profile", 403

    content = request.form.get("content", "").strip()
    if content:
        new_comment = ProfileComment(
            profile_user_id=target_user.id,
            author_id=current_user.id,
            content=content
        )
        db.session.add(new_comment)

        # notify the profile owner!
        if target_user.id != current_user.id:
            notif = Notification(
                user_id=target_user.id,
                message=f"{current_user.username} commented on your profile",
                type="profile_comment"
            )
            db.session.add(notif)

        db.session.commit()

    return redirect(url_for("profile", username=username))

@app.route("/profile/comment/<int:comment_id>/delete", methods=["POST"])
@login_required
def delete_profile_comment(comment_id):
    comment = ProfileComment.query.get_or_404(comment_id)

    if comment.profile_user_id != current_user.id and comment.author_id != current_user.id:
        return "Access Denied: not your comment or profile", 403

    profile_username = comment.profile_user.username
    db.session.delete(comment)
    db.session.commit()
    return redirect(url_for("profile", username=profile_username))

@app.route("/profile/toggle_comments", methods=["POST"])
@login_required
def toggle_comments():
    current_user.comments_enabled = not current_user.comments_enabled
    db.session.commit()
    return redirect(url_for("profile", username=current_user.username))


@app.route("/increment_view/<int:game_id>", methods = ["POST"])
def increment_view(game_id):
    game = Game.query.get_or_404(game_id)
    game.view_count += 1
    db.session.commit()
    update_daily_stats(game)
    return jsonify({"status": "success", "views": game.view_count})

@app.route("/toggle_wishlist/<int:game_id>", methods=["POST"])
@login_required
def toggle_wishlist(game_id):
    game = Game.query.get_or_404(game_id)

    existing = Wishlist.query.filter_by(user_id=current_user.id, game_id=game.id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        update_daily_stats(game)
        return jsonify({"status": "removed", "on_wishlist": False, "count": len(game.wishlisted_by)})
    else:
        entry = Wishlist(user_id=current_user.id, game_id=game.id)
        db.session.add(entry)
        db.session.commit()
        update_daily_stats(game)
        return jsonify({"status": "added", "on_wishlist": True, "count": len(game.wishlisted_by)})

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
    game = Game.query.get_or_404(game_id)
    new_purchase = Purchase(
        user_id=current_user.id,
        game_id=game_id,
        price_paid=calculate_display_price(game)
    )
    db.session.add(new_purchase)
    db.session.commit()
    return redirect(url_for("library"))

#This is for the home Page.
@app.route("/")
def home():
    check_sales_expiry() #checking
    sale_games = Game.query.filter_by(is_on_sale=True).all()

    for game in sale_games:
        game.display_price = calculate_display_price(game)

    # personalized recommendations, only makes sense for logged in folks
    recommended_games = get_recommended_games(current_user, limit=6)
    for game in recommended_games:
        game.display_price = calculate_display_price(game)
        tags = [t.strip().lower() for t in game.tags.split(",")] if game.tags else []
        game.tags_json = json.dumps(tags)

    return render_template('home.html', sale_games=sale_games, recommended_games=recommended_games)

@app.route("/library")
@login_required
def library():
    #What did the user already buy? Money go brrr xD
    purchases = Purchase.query.filter_by(user_id=current_user.id).all()
    # Optimized it
    game_ids = [p.game_id for p in purchases]
    owned_games = Game.query.filter(Game.id.in_(game_ids)).all()
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
    game.display_price = calculate_display_price(game)
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
        game.display_price = calculate_display_price(game)

        if game.genre not in games_by_genre:
            games_by_genre[game.genre] = []

        games_by_genre[game.genre].append(game)
    return render_template("store.html", genres=games_by_genre)

@app.route("/create-checkout-session/<int:game_id>")
def create_checkout_session(game_id):
    game = Game.query.get_or_404(game_id)
    stripe.api_key = stripe_keys["secret_key"]

    display_price = calculate_display_price(game)
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


@app.route("/wishlist")
@login_required
def wishlist():
    entries = Wishlist.query.filter_by(user_id=current_user.id).order_by(Wishlist.added_at.desc()).all()
    games = []
    for entry in entries:
        game = entry.game
        game.display_price = calculate_display_price(game)
        # same tags logic like in store front
        tags = [t.strip().lower() for t in game.tags.split(",")] if game.tags else []
        game.tags_json = json.dumps(tags)
        games.append(game)
    return render_template("wishlist.html", games=games)


@app.route("/success/<int:game_id>")
@login_required
def success(game_id):
    game = Game.query.get_or_404(game_id)
    if not Purchase.query.filter_by(user_id=current_user.id, game_id=game_id).first():
        new_purchase = Purchase(
            user_id=current_user.id,
            game_id=game_id,
            price_paid=calculate_display_price(game)
        )
        db.session.add(new_purchase)
        db.session.commit()
        update_daily_stats(game)

    return render_template("success.html", game=game)

@app.route("/remove_purchase/<int:game_id>", methods=["POST"])
@login_required
def remove_purchase(game_id):
    #forgot login required
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
    reviews = game.reviews
    total_ratings = len(reviews)

    if total_ratings > 0:
        positive_count = sum(1 for r in reviews if r.is_positive)
        average_score = (positive_count / total_ratings) * 100
    else:
        average_score = 0

    #Lets do Math (:
    game.display_price = calculate_display_price(game)

    return render_template("game_detail.html",game=game, screenshots=screenshots, videos=videos,average_score=average_score,reviews=reviews)

@app.route("/edit_game/<int:game_id>", methods = ["GET", "POST"])
@login_required
def edit_game(game_id):
    #yea for some reason anonymus visitors could just edit any game.
    #should be fixed now.
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

        # only overwrite the demo if the dev actually picked a new file
        demo_file = request.files.get("demo_file")
        if demo_file and demo_file.filename:
            game.demo_path = save_file(demo_file)

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

    if request.method == "POST":
        #merged the block together
        sale_end_date = None
        sale_end_date_str = request.form.get("sale_end_date")
        if sale_end_date_str:
            try:
                sale_end_date = datetime.strptime(sale_end_date_str, "%Y-%m-%dT%H:%M")
            except ValueError:
                sale_end_date = None

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
        demo_file = request.files.get("demo_file")

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
        demo_path = save_file(demo_file) if demo_file and demo_file.filename else None

        new_game = Game(title=title, genre=genre, priority=priority, tags=tags, price=price,
                        image_path=image_path, video_path=video_path, description=description,
                        download_path=download_path, demo_path=demo_path, is_on_sale=is_on_sale, sale_end_date=sale_end_date,
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
        game.display_price = calculate_display_price(game)
    return render_template("admin.html", games=my_games)

@app.route("/dashboard/game/<int:game_id>/stats")
@login_required
def game_stats(game_id):
    game = Game.query.get_or_404(game_id)
    if current_user.role != "dev":
        return "Access Denied. How could you?", 403
    if game.developer_id != current_user.id:
        return "Access Denied: Better Luck next time (:", 403

    # make sure today's data point is up to date before we show it
    update_daily_stats(game)

    history = GameStats.query.filter_by(game_id=game.id).order_by(GameStats.date.asc()).all()

    chart_data = {
        "labels": [h.date.strftime("%d.%m.%Y") for h in history],
        "views": [h.views for h in history],
        "wishlists": [h.wishlist_count for h in history],
        "purchases": [h.purchase_count for h in history],
        "revenue": [h.revenue for h in history]
    }

    current_wishlist_count = Wishlist.query.filter_by(game_id=game.id).count()
    current_purchase_count = Purchase.query.filter_by(game_id=game.id).count()

    return render_template(
        "game_stats.html",
        game=game,
        chart_json=json.dumps(chart_data),
        current_wishlist_count=current_wishlist_count,
        current_purchase_count=current_purchase_count,
        total_revenue=calculate_game_revenue(game)
    )

@app.route("/dashboard/revenue")
@login_required
def developer_revenue():
    if current_user.role != "dev":
        return "Access Denied. How could you?", 403

    my_games = Game.query.filter_by(developer_id=current_user.id).all()

    revenue_data = []
    total_revenue = 0
    for game in my_games:
        game_revenue = calculate_game_revenue(game)
        total_revenue += game_revenue
        revenue_data.append({
            "game": game,
            "revenue": game_revenue,
            "sales_count": len(game.purchases)
        })

    # highest earner first
    revenue_data.sort(key=lambda x: x["revenue"], reverse=True)

    return render_template(
        "developer_revenue.html",
        revenue_data=revenue_data,
        total_revenue=total_revenue
    )


#Yea I need that
migrate = Migrate(app, db)

if __name__ == "__main__":
    app.run(debug = True)
