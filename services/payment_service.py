import json
import stripe
from flask import url_for, has_request_context
from extensions import db
from models.user import User, Notification
from models.game import Game
from models.commerce import Purchase, Gift
from models.bundle import Bundle
from services.game_service import calculate_display_price, update_daily_stats
from services.mail_service import send_email, _comic_email_shell
import config


def _extract_metadata(obj):
    if not obj:
        return {}
    meta = getattr(obj, "metadata", None)
    if meta is None and isinstance(obj, dict):
        meta = obj.get("metadata")
    if not meta:
        return {}
    if hasattr(meta, "to_dict"):
        return meta.to_dict()
    if isinstance(meta, dict):
        return meta
    return dict(getattr(meta, "_data", {}))


def fulfill_checkout(checkout_session_id):
    # Create the local Purchase only after Stripe confirms payment.
    stripe.api_key = config.stripe_keys["secret_key"]
    checkout_session = stripe.checkout.Session.retrieve(checkout_session_id)
    if checkout_session.payment_status != "paid":
        return False
    metadata = _extract_metadata(checkout_session)

    try:
        user_id = int(metadata["user_id"])
    except (KeyError, TypeError, ValueError):
        return False

    user = db.session.get(User, user_id)
    if not user:
        return False

    # When bundle
    if "bundle_id" in metadata:
        bundle = db.session.get(Bundle, int(metadata["bundle_id"]))
        if not bundle:
            return False

        # Split the price
        price_per_game = bundle.display_price / len(bundle.games) if bundle.games else 0

        for bg in bundle.games:
            game = bg.game
            # We dont want it to crash
            unique_session_id = f"{checkout_session.id}|{game.id}"

            existing = Purchase.query.filter_by(stripe_checkout_session_id=unique_session_id).first()
            if not existing:
                p = Purchase(
                    user_id=user.id,
                    game_id=game.id,
                    price_paid=price_per_game,
                    stripe_checkout_session_id=unique_session_id,
                    stripe_payment_intent_id=f"{checkout_session.payment_intent}|{game.id}",
                    refunded=False,
                )
                db.session.add(p)
                update_daily_stats(game)
        db.session.commit()
        return True

    # When its a single game
    elif "game_id" in metadata:
        game_id = int(metadata["game_id"])

        # Webhooks can be delivered more than once. Do not create duplicate purchases. please
        existing_purchase = Purchase.query.filter_by(stripe_checkout_session_id=checkout_session.id).first()
        if existing_purchase:
            return True

        game = db.session.get(Game, game_id)
        if not game:
            return False

        # a user should not own the same game twice. (Like DONT GIVE ME ALL YOUR MONEY, give me your entire house instead)
        existing_purchase = Purchase.query.filter_by(user_id=user.id, game_id=game_id).first()
        if existing_purchase and not existing_purchase.refunded:
            if not existing_purchase.stripe_checkout_session_id:
                existing_purchase.stripe_checkout_session_id = checkout_session.id
            if not existing_purchase.stripe_payment_intent_id:
                existing_purchase.stripe_payment_intent_id = checkout_session.payment_intent
            db.session.commit()
            return True

        purchase = Purchase(
            user_id=user.id,
            game_id=game_id,
            price_paid=calculate_display_price(game),
            stripe_checkout_session_id=checkout_session.id,
            stripe_payment_intent_id=checkout_session.payment_intent,
            refunded=False,
        )
        db.session.add(purchase)
        db.session.commit()
        update_daily_stats(game)
        return True

    # When its a cart (multiple individual games in one session)
    elif "cart_game_ids" in metadata:
        try:
            cart_ids = json.loads(metadata["cart_game_ids"])
        except (ValueError, TypeError):
            return False

        for game_id in cart_ids:
            game = db.session.get(Game, int(game_id))
            if not game:
                continue
            unique_session_id = f"{checkout_session.id}|{game.id}"
            existing = Purchase.query.filter_by(stripe_checkout_session_id=unique_session_id).first()
            if not existing:
                p = Purchase(
                    user_id=user.id,
                    game_id=game.id,
                    price_paid=calculate_display_price(game),
                    stripe_checkout_session_id=unique_session_id,
                    stripe_payment_intent_id=f"{checkout_session.payment_intent}|{game.id}",
                    refunded=False,
                )
                db.session.add(p)
                update_daily_stats(game)
        db.session.commit()
        return True

    return False


def fulfill_gift(checkout_session_id):
    # that thing is called by the stripe webhook after a succesfull payment.
    # It creates the purchase on the Recipients account and stores a gift row (so we know THAT I SEND IT) and it sends the recipient an email
    # fully independent here
    stripe.api_key = config.stripe_keys["secret_key"]
    cs = stripe.checkout.Session.retrieve(checkout_session_id)
    if cs.payment_status != "paid":
        return False

    metadata = _extract_metadata(cs)
    if metadata.get("purchase_type") != "gift":
        return False

    try:
        sender_id = int(metadata["user_id"])
        recipient_id = int(metadata["recipient_id"])
        game_id = int(metadata["game_id"])
    except (KeyError, TypeError, ValueError):
        return False

    gift_message = metadata.get("gift_message", "")

    # Idempotency guard: Gift row already exists for this session?
    existing_gift = Gift.query.filter_by(
        stripe_checkout_session_id=checkout_session_id
    ).first()
    if existing_gift:
        return True

    game = db.session.get(Game, game_id)
    if not game:
        return False

    # Book the purchase on the RECIPIENT (not the sender who paid)
    existing_purchase = Purchase.query.filter_by(
        user_id=recipient_id, game_id=game_id, refunded=False
    ).first()
    if not existing_purchase:
        p = Purchase(
            user_id=recipient_id,
            game_id=game_id,
            price_paid=calculate_display_price(game),
            stripe_checkout_session_id=checkout_session_id,
            stripe_payment_intent_id=cs.payment_intent,
            refunded=False,
        )
        db.session.add(p)
        update_daily_stats(game)

    # Create the Gift record so we always know who the sender was
    gift = Gift(
        sender_id=sender_id,
        recipient_id=recipient_id,
        game_id=game_id,
        stripe_checkout_session_id=checkout_session_id,
        stripe_payment_intent_id=cs.payment_intent,
        message=gift_message,
    )
    db.session.add(gift)

    # Notify the recipient
    sender = db.session.get(User, sender_id)
    sender_name = sender.username if sender else "Someone"
    notif_msg = f"{sender_name} gifted you '{game.title}'!"
    if gift_message:
        notif_msg += f' "{gift_message[:100]}"'
    db.session.add(Notification(
        user_id=recipient_id,
        message=notif_msg,
        type="gift_received",
    ))

    recipient = db.session.get(User, recipient_id)
    if recipient and recipient.email:
        try:
            lib_url = url_for("library", _external=True) if has_request_context() else "/library"
        except Exception:
            lib_url = "/library"

        email_body = f"""
          <p>Hey {recipient.username},</p>
          <p><strong>{sender_name}</strong> just gifted you <strong>{game.title}</strong> on Sqush!</p>
          {f'<p style="background:#222;padding:12px;border-left:4px solid #ffe14d;color:#eee;">"{gift_message}"</p>' if gift_message else ''}
          <p style="text-align:center;margin:28px 0;">
            <a href="{lib_url}"
               style="background:#33d17a;color:#000;font-weight:bold;text-decoration:none;
                      padding:12px 24px;border:3px solid #000;display:inline-block;">
              GO TO YOUR LIBRARY
            </a>
          </p>
        """
        send_email(recipient.email, f"{sender_name} gifted you {game.title}!", _comic_email_shell("You received a gift!", email_body))

    db.session.commit()
    return True
