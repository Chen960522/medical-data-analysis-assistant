/**
 * Chat (conversational analysis) TypeScript types.
 *
 * Mirror the backend schemas in `backend/app/schemas/chat.py` for the
 * Agent-driven conversation API (create session, send message, fetch history,
 * fetch conversation context). These power the persistent Chat_Interface that
 * sits alongside the analysis view (Req 9.1-9.4, 9.10-9.13, 9.17-9.18).
 */
/** Maximum number of conversation turns per analysis session (Req 9.17). */
export const MAX_CONVERSATION_TURNS = 50;
