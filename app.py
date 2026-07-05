#I'm not forgetting comments this time
import os
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user,login_required
from werkzeug.security import check_password_hash, generate_password_hash

app= Flask(__name__)

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

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

#initilaize the Database
with app.app_context():
    db.create_all()

#our lovely routes xD

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


#This is for the home Page.
@app.route("/")
def home():
    sale_games = Game.query.filter((Game.priority == "high") | (Game.is_on_sale == True)).limit(3).all()

    for game in sale_games:
        game.tag_list = [t.strip() for t in game.tags.split(",")] if game.tags else []

        if game.is_on_sale == True and game.discount_percent > 0:
            game.display_price = game.price * (1 - game.discount_percent / 100)
        else:
            game.display_price = game.price

    return render_template("home.html", games=sale_games)

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
        description = request.form.get("description") # When using get I just try to get around performance issues
        #Juicy 1 % Sale
        is_on_sale = "is_on_sale" in request.form
        discount_percent = int(request.form.get("discount_percent", 0))

        image_file = request.files["image"]
        uploaded_video = request.files.get("video_file")
        video_youtube = request.files.get("video_youtube","").strip()
        game_file = request.files.get("game_file") #Please not over 1GB
        image_path = ""
        video_path = ""
        download_path = ""

        if image_file:
            img_filename = secure_filename(image_file.filename)
            image_file.save(os.path.join(app.config["UPLOAD_FOLDER"], img_filename))
            image_path = f"uploads/{img_filename}"

        if uploaded_video and uploaded_video.filename != "":
            #local
            vid_filename = secure_filename(uploaded_video.filename)
            uploaded_video.save(os.path.join(app.config["UPLOAD_FOLDER"], vid_filename))
            video_path = f"uploads/{vid_filename}"
        elif video_youtube:
            #Crawling monster gets ID
            if "v=" in video_youtube:
                yt_id = video_youtube.split("v=")[1].split("&")[0]
            elif "youtu.be" in video_youtube:
                yt_id = video_youtube.split("youtu.be=")[1].split("?")[0]
            else:
                yt_id = video_youtube
            video_path = f"youtube:{yt_id}" #The Template needs to know his name :X

        else:
            video_path = "youtube:dQw4w9WgXcQ"


        if game_file and game_file.filename != "":
            game_filename = secure_filename(game_file.filename)
            game_file.save(os.path.join(app.config ["UPLOAD_FOLDER"], game_filename))
            download_path = f"uploads/{game_filename}"


        new_game = Game(title=title, genre=genre,priority=priority, tags=tags, price=price,image_path=image_path,video_path=video_path,
                        description=description, download_path=download_path, is_on_sale=is_on_sale, discount_percent=discount_percent,
                        developer_id=current_user.id
                        )
        db.session.add(new_game)
        db.session.commit()


        return redirect(url_for("store_front"))
    my_games = Game.query.filter_by(developer_id=current_user.id).all()
    for game in my_games:
        if game.is_on_sale and game.discount_percent > 0:
            game.display_price = game.price * (1 - game.discount_percent / 100)
        else:
            game.display_price = game.price
    return render_template("admin.html", games=my_games)
if __name__ == "__main__":
    app.run(debug = True)