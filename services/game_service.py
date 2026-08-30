from datetime import datetime, timezone
from sqlalchemy import func as _sqlfunc
from extensions import db
from models.game import Game, GameStats
from models.commerce import Purchase, Wishlist


def calculate_game_revenue(game):
    # SQL SUM is orders of magnitude faster than loading every Purchase object into Python.
    # NOTE: purchases where price_paid is NULL (legacy rows) are excluded from the sum;
    # in practice price_paid is always set at purchase time.
    result = db.session.query(_sqlfunc.sum(Purchase.price_paid)).filter(
        Purchase.game_id == game.id,
        Purchase.refunded == False,
        Purchase.price_paid != None,
    ).scalar()
    return result or 0.0


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
    # Use SQL ORDER BY + LIMIT instead of loading all games into Python and sorting there.
    exclude_ids = exclude_ids or set()
    query = (
        db.session.query(Game)
        .outerjoin(Purchase, (Purchase.game_id == Game.id) & (Purchase.refunded == False))
        .group_by(Game.id)
        .order_by(_sqlfunc.count(Purchase.id).desc())
    )
    if exclude_ids:
        query = query.filter(~Game.id.in_(exclude_ids))
    return query.limit(limit).all()


def get_recommended_games(user, limit=6):
    """
    All of this code is fine for a small store, but it's not going to scale well...
    Its because of the Game.query.all() call. If you wanna use this for a large store, you should
    use real tag tables! If you dont then it might become a problem.
    """
    if not user.is_authenticated:
        return []

    my_owned_ids = {
        p.game_id
        for p in Purchase.query.filter_by(user_id=user.id, refunded=False).all()
    }

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
    for game_id, user_id in db.session.query(Wishlist.game_id, Wishlist.user_id).all():
        wishlisters_by_game.setdefault(game_id, set()).add(user_id)

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


_last_sale_check: "datetime | None" = None


def check_sales_expiry():
    global _last_sale_check
    now = datetime.now(timezone.utc)
    # Only run the DB query at most once per minute – no need to check on every home page hit.
    if _last_sale_check is not None and (now - _last_sale_check).total_seconds() < 60:
        return
    _last_sale_check = now

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
