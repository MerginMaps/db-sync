"""
Flask application entry point for mergin-db-sync web interface.
"""

import json
import time
from flask import Flask, render_template, request, jsonify, Response, redirect, url_for

from . import mergin_api
from . import db_api
from . import config_manager
from .sync_manager import get_sync_manager


app = Flask(__name__)


# ============================================================================
# Page Routes
# ============================================================================

@app.route("/")
def index():
    """Landing page - redirect to wizard or dashboard based on config state."""
    if config_manager.config_exists():
        return redirect(url_for("dashboard"))
    return redirect(url_for("wizard"))


@app.route("/wizard")
def wizard():
    """Configuration wizard page."""
    return render_template("wizard.html")


@app.route("/dashboard")
def dashboard():
    """Status dashboard page."""
    config = config_manager.get_config_for_display()
    return render_template("dashboard.html", config=config)


# ============================================================================
# Wizard API Endpoints
# ============================================================================

@app.route("/api/wizard/validate-mergin", methods=["POST"])
def api_validate_mergin():
    """Validate Mergin credentials."""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    url = data.get("url", "https://app.merginmaps.com")
    username = data.get("username", "")
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"success": False, "error": "Username and password are required"}), 400

    result = mergin_api.validate_credentials(url, username, password)
    return jsonify(result)


@app.route("/api/wizard/list-projects", methods=["POST"])
def api_list_projects():
    """List user's Mergin projects."""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    url = data.get("url", "https://app.merginmaps.com")
    username = data.get("username", "")
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"success": False, "error": "Username and password are required"}), 400

    result = mergin_api.list_projects(url, username, password)
    return jsonify(result)


@app.route("/api/wizard/project-files", methods=["POST"])
def api_project_files():
    """List GeoPackage files in a project."""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    url = data.get("url", "https://app.merginmaps.com")
    username = data.get("username", "")
    password = data.get("password", "")
    project = data.get("project", "")

    if not username or not password:
        return jsonify({"success": False, "error": "Username and password are required"}), 400
    if not project:
        return jsonify({"success": False, "error": "Project name is required"}), 400

    result = mergin_api.list_gpkg_files(url, username, password, project)
    return jsonify(result)


@app.route("/api/wizard/test-postgres", methods=["POST"])
def api_test_postgres():
    """Test PostgreSQL connection."""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    conn_info = data.get("conn_info", "")
    if not conn_info:
        return jsonify({"success": False, "error": "Connection string is required"}), 400

    result = db_api.test_connection(conn_info)
    return jsonify(result)


@app.route("/api/wizard/save-config", methods=["POST"])
def api_save_config():
    """Save complete configuration to YAML file."""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    result = config_manager.save_config(data)
    return jsonify(result)


@app.route("/api/wizard/load-config", methods=["GET"])
def api_load_config():
    """Load existing configuration."""
    try:
        config = config_manager.load_config()
        return jsonify({"success": True, "config": config})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ============================================================================
# Sync Control API Endpoints
# ============================================================================

@app.route("/api/sync/start", methods=["POST"])
def api_sync_start():
    """Start sync daemon subprocess."""
    data = request.get_json() or {}
    force_init = data.get("force_init", False)

    manager = get_sync_manager()
    result = manager.start(force_init=force_init)
    return jsonify(result)


@app.route("/api/sync/stop", methods=["POST"])
def api_sync_stop():
    """Stop sync daemon subprocess."""
    manager = get_sync_manager()
    result = manager.stop()
    return jsonify(result)


@app.route("/api/sync/status", methods=["GET"])
def api_sync_status():
    """Get current sync status."""
    manager = get_sync_manager()
    result = manager.get_status()
    return jsonify(result)


# ============================================================================
# Log Streaming API Endpoints
# ============================================================================

@app.route("/api/logs/stream")
def api_logs_stream():
    """Server-Sent Events endpoint for real-time logs."""
    def generate():
        manager = get_sync_manager()
        last_index = 0

        # Send initial logs
        result = manager.get_new_logs_since(0)
        if result["logs"]:
            data = json.dumps({"logs": result["logs"], "index": result["next_index"]})
            yield f"data: {data}\n\n"
            last_index = result["next_index"]

        # Stream new logs
        while True:
            result = manager.get_new_logs_since(last_index)
            if result["logs"]:
                data = json.dumps({"logs": result["logs"], "index": result["next_index"]})
                yield f"data: {data}\n\n"
                last_index = result["next_index"]

            # Also send status updates
            status = manager.get_status()
            yield f"event: status\ndata: {json.dumps(status)}\n\n"

            time.sleep(1)

    return Response(generate(), mimetype="text/event-stream")


@app.route("/api/logs/recent", methods=["GET"])
def api_logs_recent():
    """Get recent logs (non-streaming)."""
    manager = get_sync_manager()
    last_n = request.args.get("n", 100, type=int)
    logs = manager.get_logs(last_n)
    return jsonify({"success": True, "logs": logs})


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Run the Flask development server."""
    print("Starting Mergin DB Sync Web Interface...")
    print("Open http://localhost:5000 in your browser")
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)


if __name__ == "__main__":
    main()
