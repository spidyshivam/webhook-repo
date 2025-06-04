import os
import hmac
import hashlib
from flask import Blueprint, request, jsonify, current_app, abort
from app.extensions import mongo
from datetime import datetime, timezone

webhook_bp = Blueprint('webhook_routes', __name__, url_prefix='/webhook')

# --- Helper Functions ---
def verify_signature(payload_body, signature_header):
    """Verify that the payload was sent from GitHub."""
    secret = current_app.config.get("GITHUB_WEBHOOK_SECRET")
    if not secret:
        current_app.logger.warning("GITHUB_WEBHOOK_SECRET not configured. Skipping signature verification.")
        return not signature_header

    if not signature_header:
        current_app.logger.warning("No X-Hub-Signature-256 header received, but secret is configured.")
        return False

    try:
        hash_object = hmac.new(secret.encode('utf-8'), msg=payload_body, digestmod=hashlib.sha256)
        expected_signature = "sha256=" + hash_object.hexdigest()
        if not hmac.compare_digest(expected_signature, signature_header):
            current_app.logger.error(f"Signature mismatch. Expected: {expected_signature}, Got: {signature_header}")
            return False
        return True
    except Exception as e:
        current_app.logger.error(f"Error during signature verification: {e}")
        return False


def format_timestamp_for_display(dt_string):
    """Formats datetime string to the desired display format for the UI."""
    if not dt_string:
        return "N/A"
    try:
        if isinstance(dt_string, datetime):
            dt_object = dt_string
        elif dt_string.endswith("Z"):
            dt_object = datetime.fromisoformat(dt_string.replace("Z", "+00:00"))
        else:
            dt_object = datetime.fromisoformat(dt_string)

        if dt_object.tzinfo is None:
            dt_object = dt_object.replace(tzinfo=timezone.utc)
        else:
            dt_object = dt_object.astimezone(timezone.utc)

        day = dt_object.day
        suffix = "th"
        if day % 10 == 1 and day != 11:
            suffix = "st"
        elif day % 10 == 2 and day != 12:
            suffix = "nd"
        elif day % 10 == 3 and day != 13:
            suffix = "rd"

        return dt_object.strftime(f"%-d{suffix} %B %Y - %-I:%M %p UTC")
    except ValueError as e:
        current_app.logger.error(f"Timestamp formatting error: {e} for value '{dt_string}'")
        return dt_string

# --- Webhook Receiver ---
@webhook_bp.route('/receiver', methods=['POST'])
def webhook_receiver():
    if not verify_signature(request.data, request.headers.get('X-Hub-Signature-256')):
        current_app.logger.warning("Webhook signature verification failed or GITHUB_WEBHOOK_SECRET is missing while signature is present.")
        abort(403, "Request signature mismatch or configuration error.")

    event_type = request.headers.get('X-GitHub-Event')
    payload = request.json
    event_data = None
    now_utc_iso = datetime.now(timezone.utc).isoformat()

    current_app.logger.info(f"Received event: {event_type}, Action: {payload.get('action', 'N/A')}")

    if event_type == 'push':
        try:
            ref = payload.get('ref', '')
            to_branch = ref.split('/')[-1] if ref.startswith('refs/heads/') else ref
            author = payload.get('pusher', {}).get('name', 'N/A')
            timestamp = payload.get('head_commit', {}).get('timestamp') if payload.get('head_commit') else now_utc_iso
            request_id = payload.get('head_commit', {}).get('id') if payload.get('head_commit') else payload.get('after', 'N/A')

            event_data = {
                'request_id': request_id,
                'author': author,
                'action': 'PUSH',
                'from_branch': None,
                'to_branch': to_branch,
                'timestamp': timestamp
            }
        except Exception as e:
            current_app.logger.error(f"Error processing PUSH event: {e}", exc_info=True)
            return jsonify({'status': 'error', 'message': 'Failed to process PUSH event'}), 500

    elif event_type == 'pull_request':
        pr_action = payload.get('action')
        pull_request = payload.get('pull_request', {})

        if pr_action == 'opened':
            try:
                author = pull_request.get('user', {}).get('login', 'N/A')
                from_branch = pull_request.get('head', {}).get('ref', 'N/A')
                to_branch = pull_request.get('base', {}).get('ref', 'N/A')
                timestamp = pull_request.get('created_at', now_utc_iso)
                request_id = str(pull_request.get('id', 'N/A')) # PR ID

                event_data = {
                    'request_id': request_id,
                    'author': author,
                    'action': 'PULL_REQUEST',
                    'from_branch': from_branch,
                    'to_branch': to_branch,
                    'timestamp': timestamp
                }
            except Exception as e:
                current_app.logger.error(f"Error processing PULL_REQUEST (opened) event: {e}", exc_info=True)
                return jsonify({'status': 'error', 'message': 'Failed to process PULL_REQUEST event'}), 500

        elif pr_action == 'closed' and pull_request.get('merged'):
            try:
                author = pull_request.get('merged_by', {}).get('login') or \
                         pull_request.get('user', {}).get('login', 'N/A')
                from_branch = pull_request.get('head', {}).get('ref', 'N/A')
                to_branch = pull_request.get('base', {}).get('ref', 'N/A')
                timestamp = pull_request.get('merged_at', now_utc_iso)
                request_id = pull_request.get('merge_commit_sha', 'N/A')

                event_data = {
                    'request_id': request_id,
                    'author': author,
                    'action': 'MERGE',
                    'from_branch': from_branch,
                    'to_branch': to_branch,
                    'timestamp': timestamp
                }
            except Exception as e:
                current_app.logger.error(f"Error processing MERGE event (PR closed/merged): {e}", exc_info=True)
                return jsonify({'status': 'error', 'message': 'Failed to process MERGE event'}), 500
        else:
            current_app.logger.info(f"Ignoring pull_request action: {pr_action} for PR #{pull_request.get('number')}")
            return jsonify({'status': 'ignored', 'message': f'Pull request action {pr_action} not handled'}), 200

    elif event_type == 'ping':
        current_app.logger.info("Received ping event from GitHub.")
        return jsonify({'status': 'success', 'message': 'Pong! Webhook is active.'}), 200


    if event_data:
        try:
            document_to_insert = {
                'request_id': event_data['request_id'],
                'author': event_data['author'],
                'action': event_data['action'],
                'from_branch': event_data.get('from_branch'),
                'to_branch': event_data['to_branch'],
                'timestamp': event_data['timestamp']
            }

            if mongo.db is None:
                current_app.logger.error("MongoDB client (mongo.db) is not available. Check MONGO_URI and initialization.")
                return jsonify({'status': 'error', 'message': 'Database not configured'}), 500

            result = mongo.db.events.insert_one(document_to_insert)
            current_app.logger.info(f"Stored event to MongoDB with ID: {result.inserted_id}. Action: {document_to_insert['action']} by {document_to_insert['author']}")
            return jsonify({'status': 'success', 'message': 'Webhook received and processed'}), 200
        except Exception as e:
            current_app.logger.error(f"Error storing event to MongoDB: {e}", exc_info=True)
            return jsonify({'status': 'error', 'message': 'Failed to store event to MongoDB'}), 500

    current_app.logger.info(f"Event type '{event_type}' not explicitly handled or no data extracted from this action.")
    return jsonify({'status': 'ignored', 'message': f"Event type '{event_type}' not handled or no useful data extracted for this action."}), 200

@webhook_bp.route('/events', methods=['GET'])
def get_events_for_ui():
    try:
        if mongo.db is None:
            current_app.logger.error("MongoDB client (mongo.db) is not available for fetching events.")
            return jsonify({"error": "Database not configured", "events": []}), 500

        latest_events_cursor = mongo.db.events.find().sort('timestamp', -1).limit(20)

        formatted_events = []
        for event in latest_events_cursor:
            display_event = {
                '_id': str(event.get('_id')),
                'author': event.get('author', 'N/A'),
                'action': event.get('action', 'N/A'),
                'from_branch': event.get('from_branch'), # Might be None
                'to_branch': event.get('to_branch', 'N/A'),
                'timestamp_formatted': format_timestamp_for_display(event.get('timestamp'))
            }

            message = "Unknown event"
            if display_event['action'] == 'PUSH':
                message = f"{display_event['author']} pushed to {display_event['to_branch']} on {display_event['timestamp_formatted']}"
            elif display_event['action'] == 'PULL_REQUEST':
                message = f"{display_event['author']} submitted a pull request from {display_event['from_branch']} to {display_event['to_branch']} on {display_event['timestamp_formatted']}"
            elif display_event['action'] == 'MERGE':
                message = f"{display_event['author']} merged branch {display_event['from_branch']} to {display_event['to_branch']} on {display_event['timestamp_formatted']}"

            formatted_events.append({'message': message})

        return jsonify(formatted_events)
    except Exception as e:
        current_app.logger.error(f"Error fetching events for UI: {e}", exc_info=True)
        return jsonify({"error": "Failed to retrieve events", "details": str(e)}), 500
