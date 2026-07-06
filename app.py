#I'm not forgetting comments this time
import os
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user,login_required
from werkzeug.security import check_password_hash, generate_password_hash

app= Flask(__name__)

@app.context_processor
def inject_models():
    return dict(Screenshot=Screenshot, Video=Video)

#secruity first huh? and then the Database
app.config["SECRET_KEY"] = "super-secret-sqush-key-change-this-later" # Great Name isn't it xD
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///db.sqlite3"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

#Directory for Videos , Pictures and REAL GAME FILES. I wouldn't wanna pay for the Server ):
UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok = True)
db = SQLAlchemy(app)

#Initiliaze Login
login_manager = LoginManager(app)
login_manager.login_view = "login" #YOU BETTER LOGIN

#Database model for my Users <)
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), nullable=False, unique=True)
    email = db.Column(db.String(128), nullable=False, unique=True) #trash-mails must be allowed
    password_hash = db.Column(db.String(250), nullable=False) #Quantum Computers shall fall
    role = db.Column(db.String(20), default="user") #you should be the dev

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
    image_path = db.Column(db.String(250))
    video_path = db.Column(db.String(250)) # The link couldn't be that long (:
    #Marketplace Fields.
    description = db.Column(db.Text, nullable = True) #You could just have no description. Tell your Players nothing xD
    download_path = db.Column(db.String(250),nullable = False) #Better be able to find it
    is_on_sale = db.Column(db.Boolean, default = False)
    discount_percent = db.Column(db.Integer, default = 0) #Give them those 2%

    #My Foreign Key (:
    developer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable = False)
class Purchase(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable = False)
    game_id = db.Column(db.Integer, db.ForeignKey("game.id"), nullable = False)
    #For Later
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

#authentication routes. That will be work
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
            return redirect(url_for("home"))
        return "Invalid username or password"
    return render_template("login.html")

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
    sale_games = Game.query.filter_by(is_on_sale=True).all()

    for game in sale_games:
        game.tag_list = [t.strip() for t in game.tags.split(",")] if game.tags else []

        if game.is_on_sale == True and game.discount_percent > 0:
            game.display_price = game.price * (1 - game.discount_percent / 100)
        else:
            game.display_price = game.price

    return render_template('home.html', sale_games=sale_games)

@app.route("/library")
@login_required
def library():
    #What did the user already buy? Money go brrr xD
    purchases = Purchase.query.filter_by(user_id=current_user.id).all()
    #get those game objects
    owned_games = [Game.query.get(p.game_id) for p in purchases]
    return render_template("library.html", games=owned_games)

#Store Page
@app.route("/store")
def store_front():
    all_games = Game.query.all()
    #Sorting them after their genre.
    games_by_genre = {}
    for game in all_games: #while true loop would be great here (; The performance would go crazy
        game.tag_list = [t.strip() for t in game.tags.split(",")] if game.tags else []

        if game.is_on_sale == True and game.discount_percent > 0:
            game.display_price = game.price * (1 - game.discount_percent / 100)
        else:
            game.display_price = game.price

        if game.genre not in games_by_genre:
            games_by_genre[game.genre] = []

        games_by_genre[game.genre].append(game)
    return render_template("store.html", genres=games_by_genre)

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
    game = Game.query.get_or_404(game_id)
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
#It's a dev panel now ):
@app.route("/dashboard", methods=["GET" , "POST"])
@login_required
def developer_dashboard():
    if current_user.role != "dev":
        return "Access Denied: Better Luck next time (:", 403

    if request.method == "POST":
        title = request.form["title"]
        genre = request.form["genre"]
        priority = request.form["priority"]
        tags = request.form["tags"]
        price = float(request.form["price"])
        description = request.form.get("description")
        is_on_sale = "is_on_sale" in request.form
        discount_percent = int(request.form.get("discount_percent", 0))

        image_file = request.files["image"]
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
                        download_path=download_path, is_on_sale=is_on_sale,
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