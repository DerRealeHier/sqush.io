import os
import clamd
from werkzeug.utils import secure_filename
from flask import current_app
import config


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in config.ALLOWED_EXTENSIONS


def allowed_game_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in config.ALLOWED_GAME_EXTENSIONS


def save_file(file, folder=None):
    #the save logic is not duplicated anymore
    target_folder = folder or (current_app.config['UPLOAD_FOLDER'] if current_app else config.UPLOAD_FOLDER)
    if file and file.filename:
        filename = secure_filename(file.filename)
        file.save(os.path.join(target_folder, filename))
        relative_folder = os.path.basename(target_folder)
        return f"{relative_folder}/{filename}"
    return None


def get_clamd_client():
    # only one error at a time
    if not config.CLAMAV_ENABLED:
        return None
    try:
        cd = clamd.ClamdNetworkSocket(host=config.CLAMAV_HOST, port=config.CLAMAV_PORT)
        cd.ping()
        return cd
    except Exception as e:
        print(f"DEBUG: Cant reach ClamAV: {e}")
        return None


def scan_filestorage_for_malware(file_storage):

    if not config.CLAMAV_ENABLED:
        print(f"DEBUG: ClamAV deactivated, Scan for {file_storage.filename} skipped")
        return True, "Scan skipped (ClamAV not configured)"

    cd = get_clamd_client()
    if cd is None:
        return False, "Security scanner is currently unavailable, upload rejected"

    try:
        file_storage.stream.seek(0)
        result = cd.instream(file_storage.stream)
        file_storage.stream.seek(0)  # rewind, we still need to file.save() this afterwards xD
    except Exception as e:
        # just so I know if I messed up some configsetting or something.
        print(f"DEBUG: ClamAV instream Fehler: {e}")
        return False, "Security scanner error, upload rejected"

    if not result:
        return True, "Clean"

    status, signature = result.get("stream", (None, None))
    if status == "FOUND":
        return False, f"Malware detected ({signature})"
    return True, "Clean"


def save_game_file(file, folder=None):

    if not file or not file.filename:
        return None, None

    if not allowed_game_file(file.filename):
        return None, "Only .zip or .exe files are allowed here"

    is_clean, message = scan_filestorage_for_malware(file)
    if not is_clean:
        print(f"DEBUG: Upload rejected ({file.filename}): {message}")
        return None, message

    target_folder = folder or (current_app.config['UPLOAD_FOLDER'] if current_app else config.UPLOAD_FOLDER)
    filename = secure_filename(file.filename)
    full_path = os.path.join(target_folder, filename)
    file.save(full_path)

    relative_folder = os.path.basename(target_folder)
    return f"{relative_folder}/{filename}", None
