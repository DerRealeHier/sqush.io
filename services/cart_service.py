import hmac as _hmac
import hashlib as _hashlib
from flask import session, current_app
from extensions import db
from models.game import Game
from models.commerce import Purchase, CartItem
from models.bundle import Bundle
from services.game_service import calculate_display_price
import config


def _generate_cart_token():
    secret = current_app.config.get("SECRET_KEY", config.SECRET_KEY) if current_app else config.SECRET_KEY
    raw = _hmac.new(
        secret.encode(),
        b"cart-token-v1",
        _hashlib.sha256,
    ).hexdigest()[:24]
    return raw


def _valid_cart_token(req):
    expected = _generate_cart_token()
    provided = req.headers.get("X-Cart-Token", "")
    return _hmac.compare_digest(expected, provided)


def _merge_guest_cart(user):
    """Move any game IDs sitting in the guest session cart into CartItem rows."""
    guest_ids = session.pop("guest_cart", [])
    for gid in guest_ids:
        game = db.session.get(Game, gid)
        if not game:
            continue
        already_owns = Purchase.query.filter_by(
            user_id=user.id, game_id=gid, refunded=False
        ).first()
        if already_owns:
            continue
        existing = CartItem.query.filter_by(user_id=user.id, game_id=gid).first()
        if not existing:
            db.session.add(CartItem(user_id=user.id, game_id=gid))
    db.session.commit()


def _compute_bundle_alerts(cart_game_ids, owned_game_ids):
    # alerts when a bundle is cheaper then the game.
    alerts = []
    bundles = Bundle.query.filter_by(is_published=True).all()
    for bundle in bundles:
        bundle_game_ids = {bg.game_id for bg in bundle.games}
        overlap_ids = bundle_game_ids & set(cart_game_ids)
        if not overlap_ids:
            continue
        overlap_ids -= owned_game_ids
        if not overlap_ids:
            continue
        overlap_games = [db.session.get(Game, gid) for gid in overlap_ids]
        overlap_games = [g for g in overlap_games if g]
        individual_total = sum(calculate_display_price(g) for g in overlap_games)
        if bundle.display_price < individual_total:
            savings = round(individual_total - bundle.display_price, 2)
            alerts.append({
                "bundle": bundle,
                "overlap_games": overlap_games,
                "individual_total": round(individual_total, 2),
                "savings": savings,
            })
    return alerts
