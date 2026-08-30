from extensions import db, login_manager
from models.user import User
from models.bundle import BundleCollaborator


def bundle_role(bundle, user):
    if bundle.owner_id == user.id:
        return "owner"

    row = BundleCollaborator.query.filter_by(
        bundle_id=bundle.id,
        user_id=user.id,
        status="accepted"
    ).first()

    return row.role if row else None


@login_manager.user_loader
def load_user(user_id):
    # Always had these messages that Query.get is legacy. so I changed it.
    return db.session.get(User, int(user_id))


def connected_login_methods_count(user):
    # used to stop someone from unlinking their LAST way of getting into the account
    return sum([
        1 if user.has_password else 0,
        1 if user.firebase_uid else 0,
        1 if user.hackclub_id else 0,
    ])
