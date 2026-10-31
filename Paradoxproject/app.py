import logging
from datetime import datetime
from decimal import Decimal
from flask import Flask, render_template, jsonify, request
import mysql.connector
from database import get_connection
from services.gemini_service import (
    generate_ai_response,
    GeminiConfigError,
    GeminiAPIError
)
from services.exa_service import (
    search_web,
    ExaConfigError,
    ExaAPIError
)
from services.fact_check_service import (
    verify_article,
    FactCheckError,
)

app = Flask(__name__)

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def format_timestamp(ts):
    """Safely format MySQL datetime objects to ISO-style strings."""
    if ts is not None and hasattr(ts, "strftime"):
        return ts.strftime("%Y-%m-%d %H:%M:%S")
    return ts

def serialize_conversation(conv):
    """Serialize conversation dictionary fields."""
    if not conv:
        return conv
    conv["created_at"] = format_timestamp(conv.get("created_at"))
    conv["updated_at"] = format_timestamp(conv.get("updated_at"))
    return conv

def serialize_message(msg):
    """Serialize message dictionary fields."""
    if not msg:
        return msg
    msg["created_at"] = format_timestamp(msg.get("created_at"))
    return msg

def serialize_claim(claim):
    """Serialize claim dictionary fields."""
    if not claim:
        return claim
    claim["created_at"] = format_timestamp(claim.get("created_at"))
    if isinstance(claim.get("confidence"), Decimal):
        claim["confidence"] = float(claim["confidence"])
    return claim

def serialize_evidence(ev):
    """Serialize evidence dictionary fields."""
    if not ev:
        return ev
    ev["retrieved_at"] = format_timestamp(ev.get("retrieved_at"))
    return ev


# =====================================================================
# Existing Baseline Routes (Preserved)
# =====================================================================

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/message")
def message():
    return jsonify({
        "message": "Hello from Python Flask!",
        "team": "Paradox"
    })

@app.route("/api/db-test")
def db_test():
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM tasks")
        result = cursor.fetchall()
        return jsonify(result)
    except mysql.connector.Error as err:
        logger.error(f"Database error in /api/db-test: {err}")
        return jsonify({"success": False, "error": "Database error occurred."}), 500
    except Exception as err:
        logger.error(f"Unexpected error in /api/db-test: {err}")
        return jsonify({"success": False, "error": "Internal server error."}), 500
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if connection:
            try:
                connection.close()
            except Exception:
                pass


# =====================================================================
# VERITAS AI: Conversation Management Endpoints
# =====================================================================

@app.route("/api/conversations", methods=["POST"])
def create_conversation():
    """Create a new conversation session."""
    data = request.get_json(silent=True)
    if data is None:
        data = {}

    title = data.get("title")
    if title is None or not str(title).strip():
        title = "New Conversation"
    elif not isinstance(title, str):
        return jsonify({"success": False, "error": "Title must be a text string."}), 400
    else:
        title = title.strip()[:255]

    mode = data.get("mode", "research")
    if mode not in ("research", "fact_check"):
        return jsonify({
            "success": False,
            "error": "Invalid mode. Allowed modes are 'research' or 'fact_check'."
        }), 400

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        query = "INSERT INTO conversations (title, mode) VALUES (%s, %s)"
        cursor.execute(query, (title, mode))
        conv_id = cursor.lastrowid
        conn.commit()

        cursor.execute(
            "SELECT id, title, mode, created_at, updated_at FROM conversations WHERE id = %s",
            (conv_id,)
        )
        new_conv = cursor.fetchone()

        return jsonify({
            "success": True,
            "conversation": serialize_conversation(new_conv)
        }), 201

    except mysql.connector.Error as err:
        logger.error(f"Database error in create_conversation: {err}")
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": "Failed to create conversation due to a database error."}), 500
    except Exception as err:
        logger.error(f"Unexpected error in create_conversation: {err}")
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": "An internal server error occurred."}), 500
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@app.route("/api/conversations", methods=["GET"])
def list_conversations():
    """List conversations, with optional title search."""
    search_query = request.args.get("search", "").strip()

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        if search_query:
            query = """
                SELECT id, title, mode, created_at, updated_at
                FROM conversations
                WHERE title LIKE %s
                ORDER BY updated_at DESC
            """
            cursor.execute(query, (f"%{search_query}%",))
        else:
            query = """
                SELECT id, title, mode, created_at, updated_at
                FROM conversations
                ORDER BY updated_at DESC
            """
            cursor.execute(query)

        rows = cursor.fetchall()
        conversations = [serialize_conversation(row) for row in rows]

        return jsonify({
            "success": True,
            "conversations": conversations
        }), 200

    except mysql.connector.Error as err:
        logger.error(f"Database error in list_conversations: {err}")
        return jsonify({"success": False, "error": "Failed to retrieve conversations due to a database error."}), 500
    except Exception as err:
        logger.error(f"Unexpected error in list_conversations: {err}")
        return jsonify({"success": False, "error": "An internal server error occurred."}), 500
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@app.route("/api/conversations/<int:conversation_id>", methods=["GET"])
def get_conversation(conversation_id):
    """
    Retrieve a conversation and its messages, including all claims and evidence
    structured hierarchically: conversation -> messages -> claims -> evidence.
    """
    if conversation_id <= 0:
        return jsonify({"success": False, "error": "Invalid conversation ID."}), 400

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # 1. Fetch conversation
        cursor.execute(
            "SELECT id, title, mode, created_at, updated_at FROM conversations WHERE id = %s",
            (conversation_id,)
        )
        conv = cursor.fetchone()
        if not conv:
            return jsonify({"success": False, "error": "Conversation not found."}), 404

        # 2. Fetch all messages for this conversation
        cursor.execute(
            """
            SELECT id, conversation_id, role, content, created_at
            FROM messages
            WHERE conversation_id = %s
            ORDER BY created_at ASC, id ASC
            """,
            (conversation_id,)
        )
        messages = cursor.fetchall()

        # Build mapping of message_id -> message object
        message_map = {}
        for msg in messages:
            msg_serialized = serialize_message(msg)
            msg_serialized["claims"] = []
            message_map[msg["id"]] = msg_serialized

        # 3. If messages exist, fetch claims
        if message_map:
            msg_ids = list(message_map.keys())
            placeholders = ",".join(["%s"] * len(msg_ids))
            claims_query = f"""
                SELECT id, message_id, claim_text, verdict, confidence, explanation, created_at
                FROM claims
                WHERE message_id IN ({placeholders})
                ORDER BY created_at ASC, id ASC
            """
            cursor.execute(claims_query, tuple(msg_ids))
            claims = cursor.fetchall()

            claim_map = {}
            for claim in claims:
                claim_serialized = serialize_claim(claim)
                claim_serialized["evidence"] = []
                claim_map[claim["id"]] = claim_serialized
                if claim["message_id"] in message_map:
                    message_map[claim["message_id"]]["claims"].append(claim_serialized)

            # 4. If claims exist, fetch evidence
            if claim_map:
                claim_ids = list(claim_map.keys())
                ev_placeholders = ",".join(["%s"] * len(claim_ids))
                evidence_query = f"""
                    SELECT id, claim_id, source_title, source_url, evidence_snippet, evidence_stance, retrieved_at
                    FROM evidence
                    WHERE claim_id IN ({ev_placeholders})
                    ORDER BY retrieved_at ASC, id ASC
                """
                cursor.execute(evidence_query, tuple(claim_ids))
                evidence_list = cursor.fetchall()

                for ev in evidence_list:
                    ev_serialized = serialize_evidence(ev)
                    if ev["claim_id"] in claim_map:
                        claim_map[ev["claim_id"]]["evidence"].append(ev_serialized)

        conv_serialized = serialize_conversation(conv)
        conv_serialized["messages"] = list(message_map.values())

        return jsonify({
            "success": True,
            "conversation": conv_serialized
        }), 200

    except mysql.connector.Error as err:
        logger.error(f"Database error in get_conversation: {err}")
        return jsonify({"success": False, "error": "Failed to retrieve conversation details due to a database error."}), 500
    except Exception as err:
        logger.error(f"Unexpected error in get_conversation: {err}")
        return jsonify({"success": False, "error": "An internal server error occurred."}), 500
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@app.route("/api/conversations/<int:conversation_id>", methods=["DELETE"])
def delete_conversation(conversation_id):
    """Delete a conversation and all cascading dependent records."""
    if conversation_id <= 0:
        return jsonify({"success": False, "error": "Invalid conversation ID."}), 400

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM conversations WHERE id = %s", (conversation_id,))
        if cursor.rowcount == 0:
            conn.rollback()
            return jsonify({"success": False, "error": "Conversation not found."}), 404

        conn.commit()
        return jsonify({
            "success": True,
            "message": "Conversation and associated data deleted successfully."
        }), 200

    except mysql.connector.Error as err:
        logger.error(f"Database error in delete_conversation: {err}")
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": "Failed to delete conversation due to a database error."}), 500
    except Exception as err:
        logger.error(f"Unexpected error in delete_conversation: {err}")
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": "An internal server error occurred."}), 500
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@app.route("/api/conversations/<int:conversation_id>/messages", methods=["POST"])
def add_message(conversation_id):
    """
    Save a user or assistant message and update the conversation timestamp
    within a single atomic database transaction.
    """
    if conversation_id <= 0:
        return jsonify({"success": False, "error": "Invalid conversation ID."}), 400

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"success": False, "error": "Request body must be valid JSON."}), 400

    role = data.get("role")
    if role not in ("user", "assistant"):
        return jsonify({
            "success": False,
            "error": "Invalid role. Message role must be 'user' or 'assistant'."
        }), 400

    content = data.get("content")
    if content is None or not isinstance(content, str) or not content.strip():
        return jsonify({"success": False, "error": "Message content cannot be empty."}), 400

    content = content.strip()

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # 1. Verify conversation exists
        cursor.execute("SELECT id FROM conversations WHERE id = %s", (conversation_id,))
        if not cursor.fetchone():
            conn.rollback()
            return jsonify({"success": False, "error": "Conversation not found."}), 404

        # 2. Insert message
        insert_msg_query = """
            INSERT INTO messages (conversation_id, role, content)
            VALUES (%s, %s, %s)
        """
        cursor.execute(insert_msg_query, (conversation_id, role, content))
        msg_id = cursor.lastrowid

        # 3. Update conversation updated_at in the same transaction
        update_conv_query = """
            UPDATE conversations
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """
        cursor.execute(update_conv_query, (conversation_id,))

        # Commit both operations together
        conn.commit()

        # 4. Fetch the created message
        cursor.execute(
            "SELECT id, conversation_id, role, content, created_at FROM messages WHERE id = %s",
            (msg_id,)
        )
        saved_msg = cursor.fetchone()
        saved_msg_serialized = serialize_message(saved_msg)
        saved_msg_serialized["claims"] = []

        return jsonify({
            "success": True,
            "message": saved_msg_serialized
        }), 201

    except mysql.connector.Error as err:
        logger.error(f"Database error in add_message: {err}")
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": "Failed to save message due to a database error."}), 500
    except Exception as err:
        logger.error(f"Unexpected error in add_message: {err}")
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": "An internal server error occurred."}), 500
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass


# =====================================================================
# VERITAS AI: Gemini Integration Test Endpoint
# =====================================================================

@app.route("/api/ai-test", methods=["POST"])
def ai_test():
    """
    Test endpoint for Gemini AI response generation.
    Expects JSON: {"prompt": "..."}
    Returns JSON: {"success": true, "response": "..."}
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"success": False, "error": "Request body must be valid JSON."}), 400

    prompt = data.get("prompt")
    if prompt is None or not isinstance(prompt, str) or not prompt.strip():
        return jsonify({"success": False, "error": "Prompt must be a non-empty text string."}), 400

    prompt = prompt.strip()
    max_prompt_length = 10000
    if len(prompt) > max_prompt_length:
        return jsonify({
            "success": False,
            "error": f"Prompt exceeds maximum allowed length of {max_prompt_length} characters."
        }), 400

    try:
        ai_response = generate_ai_response(prompt)
        return jsonify({
            "success": True,
            "response": ai_response
        }), 200

    except GeminiConfigError:
        return jsonify({
            "success": False,
            "error": "AI service is not configured. Missing GEMINI_API_KEY in environment."
        }), 500

    except GeminiAPIError as gemini_err:
        return jsonify({
            "success": False,
            "error": str(gemini_err) or "Failed to communicate with AI service. Please try again shortly."
        }), 502

    except Exception as err:
        logger.error(f"Unexpected error in /api/ai-test: {err}")
        return jsonify({
            "success": False,
            "error": "An internal server error occurred while processing the AI request."
        }), 500


# =====================================================================
# VERITAS AI: Research Mode Chat Endpoint
# =====================================================================

@app.route("/api/chat", methods=["POST"])
def chat():
    """
    Process chat interaction in Research Mode.
    1. Validates input JSON, conversation_id, and prompt.
    2. Confirms conversation exists and is configured for 'research' mode.
    3. Saves user's prompt to the messages table and commits.
    4. Invokes Gemini AI generation via generate_ai_response().
    5. Saves assistant response to the messages table and updates conversation timestamp.
    6. Returns user_message and assistant_message JSON.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"success": False, "error": "Request body must be valid JSON."}), 400

    # 1. Validate conversation_id
    raw_cid = data.get("conversation_id")
    if raw_cid is None:
        return jsonify({"success": False, "error": "Missing conversation_id."}), 400
    try:
        conversation_id = int(raw_cid)
        if conversation_id <= 0:
            raise ValueError()
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "conversation_id must be a positive integer."}), 400

    # 2. Validate prompt
    prompt = data.get("prompt")
    if prompt is None or not isinstance(prompt, str) or not prompt.strip():
        return jsonify({"success": False, "error": "Prompt must be a non-empty text string."}), 400

    prompt = prompt.strip()
    max_prompt_length = 10000
    if len(prompt) > max_prompt_length:
        return jsonify({
            "success": False,
            "error": f"Prompt exceeds maximum allowed length of {max_prompt_length} characters."
        }), 400

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # 3. Confirm conversation exists and verify mode is 'research'
        cursor.execute(
            "SELECT id, title, mode FROM conversations WHERE id = %s",
            (conversation_id,)
        )
        conv = cursor.fetchone()
        if not conv:
            return jsonify({"success": False, "error": "Conversation not found."}), 404

        if conv.get("mode") != "research":
            return jsonify({
                "success": False,
                "error": f"Conversation is in '{conv.get('mode')}' mode. /api/chat currently supports 'research' mode only."
            }), 400

        # 4. Save user message and update updated_at
        cursor.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (%s, %s, %s)",
            (conversation_id, "user", prompt)
        )
        user_msg_id = cursor.lastrowid

        cursor.execute(
            "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (conversation_id,)
        )
        conn.commit()

        # Retrieve saved user message record
        cursor.execute(
            "SELECT id, conversation_id, role, content, created_at FROM messages WHERE id = %s",
            (user_msg_id,)
        )
        user_msg = cursor.fetchone()
        user_msg_serialized = serialize_message(user_msg)
        user_msg_serialized["claims"] = []

    except mysql.connector.Error as err:
        logger.error(f"Database error saving user message in /api/chat: {err}")
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": "Failed to record message due to a database error."}), 500
    except Exception as err:
        logger.error(f"Unexpected error saving user message in /api/chat: {err}")
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": "An internal server error occurred."}), 500
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass

    # 5. Send prompt to Gemini AI
    try:
        ai_response_text = generate_ai_response(prompt)
    except GeminiConfigError:
        return jsonify({
            "success": False,
            "error": "AI service is not configured. Missing GEMINI_API_KEY in environment."
        }), 500
    except GeminiAPIError as gemini_err:
        return jsonify({
            "success": False,
            "error": str(gemini_err) or "Failed to communicate with AI service. Please try again shortly."
        }), 502
    except Exception as err:
        logger.error(f"Unexpected error invoking Gemini in /api/chat: {err}")
        return jsonify({
            "success": False,
            "error": "An internal server error occurred while processing the AI request."
        }), 500

    # 6. Save assistant response to MySQL
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (%s, %s, %s)",
            (conversation_id, "assistant", ai_response_text)
        )
        assistant_msg_id = cursor.lastrowid

        cursor.execute(
            "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (conversation_id,)
        )
        conn.commit()

        cursor.execute(
            "SELECT id, conversation_id, role, content, created_at FROM messages WHERE id = %s",
            (assistant_msg_id,)
        )
        assistant_msg = cursor.fetchone()
        assistant_msg_serialized = serialize_message(assistant_msg)
        assistant_msg_serialized["claims"] = []

        return jsonify({
            "success": True,
            "conversation_id": conversation_id,
            "user_message": user_msg_serialized,
            "assistant_message": assistant_msg_serialized
        }), 200

    except mysql.connector.Error as err:
        logger.error(f"Database error saving assistant message in /api/chat: {err}")
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": "Failed to save assistant response due to a database error."}), 500
    except Exception as err:
        logger.error(f"Unexpected error saving assistant message in /api/chat: {err}")
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": "An internal server error occurred."}), 500
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass


# =====================================================================
# VERITAS AI: Exa Search Test Endpoint
# =====================================================================

@app.route("/api/search-test", methods=["POST"])
def search_test():
    """
    Test endpoint for Exa web search.
    Expects JSON: {"query": "..."}
    Returns JSON: {"success": true, "results": [...]}
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"success": False, "error": "Request body must be valid JSON."}), 400

    query = data.get("query")
    if query is None or not isinstance(query, str) or not query.strip():
        return jsonify({"success": False, "error": "Query must be a non-empty text string."}), 400

    query = query.strip()
    max_query_length = 1000
    if len(query) > max_query_length:
        return jsonify({
            "success": False,
            "error": f"Query exceeds maximum allowed length of {max_query_length} characters."
        }), 400

    try:
        results = search_web(query)
        return jsonify({
            "success": True,
            "query": query,
            "results": results,
            "count": len(results)
        }), 200

    except ExaConfigError:
        return jsonify({
            "success": False,
            "error": "Search service is not configured. Missing EXA_API_KEY in environment."
        }), 500

    except ExaAPIError as exa_err:
        return jsonify({
            "success": False,
            "error": str(exa_err) or "Failed to communicate with the search service. Please try again shortly."
        }), 502

    except ValueError as val_err:
        return jsonify({
            "success": False,
            "error": str(val_err)
        }), 400

    except Exception as err:
        logger.error(f"Unexpected error in /api/search-test: {err}")
        return jsonify({
            "success": False,
            "error": "An internal server error occurred while processing the search request."
        }), 500


# =====================================================================
# VERITAS AI: Fact Verification Endpoint
# =====================================================================

@app.route("/api/fact-check", methods=["POST"])
def fact_check():
    """
    Fact verification endpoint.
    Expects JSON: {"conversation_id": int, "article_text": str}
    Returns structured JSON with claims, verdicts, explanations, confidence scores and sources.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"success": False, "error": "Request body must be valid JSON."}), 400

    # Validate conversation_id
    raw_cid = data.get("conversation_id")
    if raw_cid is None:
        return jsonify({"success": False, "error": "Missing conversation_id."}), 400
    try:
        conversation_id = int(raw_cid)
        if conversation_id <= 0:
            raise ValueError()
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "conversation_id must be a positive integer."}), 400

    # Validate article_text
    article_text = data.get("article_text")
    if article_text is None or not isinstance(article_text, str) or not article_text.strip():
        return jsonify({"success": False, "error": "article_text must be a non-empty text string."}), 400
    article_text = article_text.strip()
    max_article_length = 20000
    if len(article_text) > max_article_length:
        return jsonify({
            "success": False,
            "error": f"Article text exceeds maximum allowed length of {max_article_length} characters."
        }), 400

    conn = None
    cursor = None

    # Step 1: Verify conversation exists and is in fact_check mode
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, title, mode FROM conversations WHERE id = %s",
            (conversation_id,)
        )
        conv = cursor.fetchone()
        if not conv:
            return jsonify({"success": False, "error": "Conversation not found."}), 404
        if conv.get("mode") != "fact_check":
            return jsonify({
                "success": False,
                "error": f"Conversation is in '{conv.get('mode')}' mode. /api/fact-check requires 'fact_check' mode."
            }), 400
    except mysql.connector.Error as err:
        logger.error(f"Database error verifying conversation in /api/fact-check: {err}")
        return jsonify({"success": False, "error": "Database error verifying conversation."}), 500
    except Exception as err:
        logger.error(f"Unexpected error verifying conversation in /api/fact-check: {err}")
        return jsonify({"success": False, "error": "Internal server error."}), 500
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass

    # Step 2: Save user message (article) in its own transaction
    user_msg_id = None
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (%s, %s, %s)",
            (conversation_id, "user", article_text)
        )
        user_msg_id = cursor.lastrowid
        cursor.execute(
            "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (conversation_id,)
        )
        conn.commit()
    except mysql.connector.Error as err:
        logger.error(f"Database error saving user message in /api/fact-check: {err}")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return jsonify({"success": False, "error": "Failed to save article due to database error."}), 500
    except Exception as err:
        logger.error(f"Unexpected error saving user message in /api/fact-check: {err}")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return jsonify({"success": False, "error": "Internal server error."}), 500
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass

    # Step 3: Run fact-check pipeline (AI + search, no DB writes here)
    try:
        result = verify_article(article_text)
    except FactCheckError as err:
        return jsonify({"success": False, "error": str(err)}), 502
    except GeminiConfigError:
        return jsonify({
            "success": False,
            "error": "AI service is not configured. Missing GEMINI_API_KEY in environment."
        }), 500
    except ExaConfigError:
        return jsonify({
            "success": False,
            "error": "Search service is not configured. Missing EXA_API_KEY in environment."
        }), 500
    except ValueError as val_err:
        return jsonify({"success": False, "error": str(val_err)}), 400
    except Exception as err:
        logger.error(f"Unexpected error in fact-check pipeline: {err}")
        return jsonify({"success": False, "error": "Fact-check pipeline failed."}), 500

    # Step 4: Save assistant message + claims + evidence in a single atomic transaction
    assistant_msg_id = None
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # Build assistant summary content
        stats = result.get("stats", {})
        summary_content = (
            f"Fact-Check Summary\n\n"
            f"{result.get('summary', '')}\n\n"
            f"Statistics: {stats.get('supported', 0)} supported, "
            f"{stats.get('contradicted', 0)} contradicted, "
            f"{stats.get('unverified', 0)} unverified out of {stats.get('total', 0)} claims."
        )

        # Insert assistant message
        cursor.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (%s, %s, %s)",
            (conversation_id, "assistant", summary_content)
        )
        assistant_msg_id = cursor.lastrowid

        # Insert claims and evidence (atomic with assistant message)
        for claim_data in result.get("claims", []):
            cursor.execute(
                """INSERT INTO claims (message_id, claim_text, verdict, confidence, explanation)
                   VALUES (%s, %s, %s, %s, %s)""",
                (
                    assistant_msg_id,
                    claim_data.get("claim_text", ""),
                    claim_data.get("verdict", "unverified"),
                    claim_data.get("confidence", 0.00),
                    claim_data.get("explanation", ""),
                )
            )
            claim_id = cursor.lastrowid

            for evidence_data in claim_data.get("evidence", []):
                cursor.execute(
                    """INSERT INTO evidence (claim_id, source_title, source_url, evidence_snippet, evidence_stance)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (
                        claim_id,
                        evidence_data.get("source_title", ""),
                        evidence_data.get("source_url", ""),
                        evidence_data.get("evidence_snippet", ""),
                        evidence_data.get("evidence_stance", "context"),
                    )
                )

        # Update conversation timestamp
        cursor.execute(
            "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (conversation_id,)
        )

        conn.commit()

    except mysql.connector.Error as err:
        logger.error(f"Database error saving fact-check results: {err}")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return jsonify({"success": False, "error": "Failed to save fact-check results due to database error."}), 500
    except Exception as err:
        logger.error(f"Unexpected error saving fact-check results: {err}")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return jsonify({"success": False, "error": "Internal server error saving results."}), 500
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass

    # Step 5: Build and return structured response
    response_claims = []
    for claim_data in result.get("claims", []):
        response_claims.append({
            "claim_text": claim_data.get("claim_text", ""),
            "verdict": claim_data.get("verdict", "unverified"),
            "confidence": claim_data.get("confidence", 0.00),
            "explanation": claim_data.get("explanation", ""),
            "evidence": [
                {
                    "source_title": ev.get("source_title", ""),
                    "source_url": ev.get("source_url", ""),
                    "evidence_snippet": ev.get("evidence_snippet", ""),
                    "evidence_stance": ev.get("evidence_stance", "context"),
                }
                for ev in claim_data.get("evidence", [])
            ],
        })

    return jsonify({
        "success": True,
        "conversation_id": conversation_id,
        "user_message_id": user_msg_id,
        "assistant_message_id": assistant_msg_id,
        "claims": response_claims,
        "summary": result.get("summary", ""),
        "stats": result.get("stats", {}),
    }), 200


if __name__ == "__main__":
    app.run(debug=True)
