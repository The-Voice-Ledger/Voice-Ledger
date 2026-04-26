"""
Agent Executor

The core agent loop that replaces the NLU → switch/case pipeline.

Flow:
  1. Receive transcript (from ASR)
  2. Build messages: system prompt + conversation history + user message
  3. Call GPT-4o with tools
  4. If model returns tool_calls → execute tools → feed results back → loop
  5. If model returns text → that's the user-facing response
  6. Return AgentResult with response + any tool results

The executor supports multi-turn conversation via Redis-backed history,
and handles both English and Amharic (via translation before/after).
"""

import os
import json
import time
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from openai import OpenAI
from dotenv import load_dotenv
from voice.providers.llm_fallback import chat_completion_with_fallback

load_dotenv()
logger = logging.getLogger(__name__)

# Agent model - GPT-4o for best tool-calling accuracy
AGENT_MODEL = os.getenv("AGENT_MODEL", "gpt-4o")
AGENT_MAX_TURNS = int(os.getenv("AGENT_MAX_TURNS", "6"))
AGENT_TEMPERATURE = float(os.getenv("AGENT_TEMPERATURE", "0.2"))

# Initialize OpenAI client with explicit timeout (prevents indefinite hangs)
_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    timeout=45.0,       # 45s per request (Railway allows 60s)
    max_retries=2,       # Retry on transient 429 / 5xx errors
)

# Addis AI configuration for Amharic translation
ADDIS_AI_API_KEY = os.getenv("ADDIS_AI_API_KEY")
ADDIS_TRANSLATE_URL = "https://api.addisassistant.com/api/v1/translate"


# ---------------------------------------------------------------------------
# Language Helpers
# ---------------------------------------------------------------------------

def translate_text(text: str, source_lang: str, target_lang: str) -> str:
    """
    Translate text between English and Amharic.

    Strategy:
    1. Try Addis AI Translation API (best for Amharic)
    2. Fall back to GPT-4o translation
    3. Return original text if both fail
    """
    if not text or not text.strip():
        return text

    # Try Addis AI first (preferred for Amharic quality)
    if ADDIS_AI_API_KEY:
        try:
            import httpx
            resp = httpx.post(
                ADDIS_TRANSLATE_URL,
                headers={
                    "X-API-Key": ADDIS_AI_API_KEY,
                    "Content-Type": "application/json",
                },
                json={
                    "text": text,
                    "source_language": source_lang,
                    "target_language": target_lang,
                },
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()
            translated = (
                data.get("data", {}).get("translated_text")
                or data.get("translated_text")
                or data.get("translation")
            )
            if translated and translated.strip():
                logger.info(f"Addis AI translated {source_lang}→{target_lang} ({len(text)} chars)")
                return translated.strip()
        except Exception as e:
            logger.warning(f"Addis AI translation failed, trying GPT fallback: {e}")

    # Fallback: GPT-4o translation
    try:
        lang_names = {"en": "English", "am": "Amharic"}
        src_name = lang_names.get(source_lang, source_lang)
        tgt_name = lang_names.get(target_lang, target_lang)
        resp, provider_used = chat_completion_with_fallback(
            primary_client=_client,
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"Translate the following {src_name} text to {tgt_name}. "
                        "Return ONLY the translation, nothing else."
                    ),
                },
                {"role": "user", "content": text},
            ],
            temperature=0.2,
            max_tokens=1000,
        )
        translated = resp.choices[0].message.content.strip()
        if translated:
            logger.info(
                f"Translated {source_lang}→{target_lang} via {provider_used} ({len(text)} chars)"
            )
            return translated
    except Exception as e:
        logger.warning(f"GPT translation also failed: {e}")

    return text  # Return original as last resort


# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------

AGENT_SYSTEM_PROMPT = """You are Voice Ledger - an AI assistant for coffee supply chain actors (farmers, cooperatives, exporters, buyers).

You help users manage coffee from harvest to export through natural voice conversation.

YOUR CAPABILITIES (use the tools provided):
• Create new coffee batches (record_commission)
• Ship batches (record_shipment) 
• Receive batches (record_receipt)
• Process coffee - roasting, milling, drying (record_transformation)
• Pack batches into containers (pack_batches)
• Unpack containers (unpack_batches)
• Split batches into portions (split_batch)
• Look up batches and data (query_batches)
• Search documentation and guides (search_knowledge)

MARKETPLACE:
• Create a Request for Quote to buy coffee (create_rfq) - buyers only
• Browse open marketplace requests (browse_rfqs)
• Submit an offer on an RFQ (submit_offer) - cooperative managers only
• Accept a cooperative's offer (accept_offer) - buyers only
• View your submitted offers (list_my_offers) - cooperative managers only

CONTAINER MARKETPLACE:
• Browse available containers for fractional purchase (browse_containers)
• Purchase a partial quantity from a container (purchase_container) - buyers only

CONTAINER POOLS (shared buying for SME roasters):
• Browse active container pools and fill progress (browse_pools)
• Commit a fractional quantity to a shared pool (commit_to_pool) - buyers only
• View your pool commitments (list_my_commitments) - buyers only

COMPLIANCE:
• Check EUDR compliance for batches (check_eudr_compliance)
• Validate mass balance for splits/transformations (check_mass_balance)

DIGITAL PRODUCT PASSPORT (DPP):
• Get the Digital Product Passport for a batch (get_dpp)
• Get aggregated container passport (get_container_dpp)
• Trace full supply chain lineage (trace_lineage)
• Validate DPP completeness (validate_dpp)

VERIFICATION:
• List batches waiting for verification (list_pending_verifications)
• Verify a batch and issue credential (verify_batch) - cooperative managers only

BLOCKCHAIN:
• Check if a batch is anchored on-chain (check_blockchain_anchor)
• Look up batch token metadata (get_token_info)
• Verify batch data integrity against blockchain (verify_batch_hash)

CHAINLINK DON ATTESTATION:
• Request Chainlink DON deforestation verification for a farm (request_don_attestation)
• Read DON-attested compliance result from blockchain (check_don_attestation)
• Get DON-attested supply chain metrics from blockchain (get_don_provenance_metrics)

SETTLEMENT / PAYMENTS:
• Confirm a bank transfer payment for an acceptance or commitment (confirm_payment) - buyers only
• Check the payment/settlement status of an acceptance or commitment (check_payment_status)
• Record that the cooperative has received and forwarded payment to farmers (record_cooperative_payout) - cooperative managers only
• Confirm receipt of a cooperative payout (confirm_payment_received) - cooperative managers only
DeFi FINANCING (USDC advances against confirmed orders):
• Check financing pool status and available liquidity (check_financing_pool)
• Request a USDC advance against a shipped container (request_financing_advance) - cooperatives only
• Check the status of a financed trade / advance (check_trade_financing)
CONVERSATION RULES:
1. Be warm, clear, and concise - users are often speaking via voice
2. When a user gives all needed info in one message, call the tool immediately
3. When info is missing, ask for it naturally - ONE question at a time
4. After executing a tool, summarize the result clearly
5. You can call MULTIPLE tools in one turn if the user asks for multiple things
6. If a tool call fails, explain the error and suggest how to fix it
7. For quantities in "bags", convert to kg (1 bag = 60 kg) before calling tools
8. Users may reference batches by ID, GTIN, or description - be flexible

RESPONSE STYLE:
- Use emoji sparingly for key status indicators (✅ success, ❌ error, 📦 batch)
- Keep responses SHORT for voice - 2-3 sentences max for simple confirmations
- For data queries, format results as clean lists
- Never mention technical internals (EPCIS, GS1, blockchain) unless user asks
- Never cite documentation sources - just state the information confidently

LANGUAGE:
- Respond in the same language the user speaks
- If the user speaks Amharic, respond in Amharic
- If the user speaks English, respond in English

SAFETY:
- For write operations (create, ship, transform, pack, split), confirm the action BEFORE executing IF the details seem ambiguous
- For read operations (query, search), execute immediately
- Never fabricate batch IDs or data - always query first if unsure
"""


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class ToolCall:
    """Record of a single tool call made by the agent."""
    tool_name: str
    arguments: Dict[str, Any]
    result_message: str
    result_data: Dict[str, Any]
    success: bool
    duration_ms: float = 0.0


@dataclass
class AgentResult:
    """Complete result from an agent turn."""
    # The text response to send to the user
    response: str
    # Spoken version (may differ - no URLs, no emoji)
    response_spoken: Optional[str] = None
    # Tool calls that were executed
    tool_calls: List[ToolCall] = field(default_factory=list)
    # Whether a write operation was performed
    performed_write: bool = False
    # Whether the conversation is ongoing (needs more turns)
    needs_followup: bool = False
    # The final intent (for backward compatibility with old pipeline)
    intent: Optional[str] = None
    # Collected entities (for backward compatibility)
    entities: Dict[str, Any] = field(default_factory=dict)
    # Token usage
    total_tokens: int = 0
    # Total wall-clock time
    duration_ms: float = 0.0
    # Error if agent loop failed entirely
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Conversation History (Redis-backed)
# ---------------------------------------------------------------------------

def _get_redis():
    """Get Redis client for conversation history."""
    try:
        import redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        return redis.from_url(redis_url)
    except Exception:
        return None


def get_conversation_history(user_id: int, max_messages: int = 20) -> List[Dict[str, str]]:
    """
    Retrieve conversation history from Redis.
    
    Stored as JSON list under key: agent:history:{user_id}
    TTL: 10 minutes (longer than old 5-minute state machine)
    """
    r = _get_redis()
    if not r:
        return []
    
    try:
        key = f"agent:history:{user_id}"
        data = r.get(key)
        if not data:
            return []
        messages = json.loads(data)
        # Only return last N messages to stay within context window
        messages = messages[-max_messages:]

        # ── Sanitize: strip any leading tool / assistant(tool_calls) messages ──
        # These are orphaned when the slice cuts between an assistant(tool_calls)
        # and its paired tool result, which causes OpenAI 400 errors.
        while messages and messages[0].get("role") in ("tool",) or (
            messages
            and messages[0].get("role") == "assistant"
            and messages[0].get("tool_calls")
        ):
            messages.pop(0)

        return messages
    except Exception as e:
        logger.warning(f"Failed to load history for user {user_id}: {e}")
        return []


def save_conversation_history(user_id: int, messages: List[Dict[str, str]], ttl: int = 600):
    """
    Save conversation history to Redis with TTL.

    Only clean user/assistant text turns are persisted. Tool call scaffolding
    (assistant with tool_calls, role=tool messages) is ephemeral per-turn and
    must NOT be saved - partial saves cause orphaned tool messages that make
    OpenAI return 400 on the next request.
    """
    r = _get_redis()
    if not r:
        return
    
    try:
        key = f"agent:history:{user_id}"
        serializable = []
        for msg in messages:
            role = msg.get("role")
            # Only keep plain user and assistant text messages
            if role not in ("user", "assistant"):
                continue
            # Skip assistant messages that contain tool_calls (ephemeral scaffolding)
            if role == "assistant" and msg.get("tool_calls"):
                continue
            content = msg.get("content") or ""
            if content.strip():
                serializable.append({"role": role, "content": content})
        
        r.setex(key, ttl, json.dumps(serializable))
    except Exception as e:
        logger.warning(f"Failed to save history for user {user_id}: {e}")


def clear_conversation_history(user_id: int):
    """Clear conversation history after task completion or timeout."""
    r = _get_redis()
    if not r:
        return
    try:
        r.delete(f"agent:history:{user_id}")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Agent Executor
# ---------------------------------------------------------------------------

class AgentExecutor:
    """
    Tool-calling agent that replaces the NLU → command_integration pipeline.
    
    Usage:
        executor = AgentExecutor()
        result = executor.run(
            transcript="Record 50 bags of Sidama from Abebe farm",
            user_id=42,
            user_did="did:key:z6Mk..."
        )
        print(result.response)       # "✅ Batch created: ABEBE_SIDAMA_20260213..."
        print(result.tool_calls)     # [ToolCall(name="record_commission", ...)]
    """
    
    def __init__(
        self,
        model: str = None,
        tools: List[Dict] = None,
        system_prompt: str = None,
        max_turns: int = None,
    ):
        from .tools import SUPPLY_CHAIN_TOOLS
        from .registry import get_tool_registry
        
        self.model = model or AGENT_MODEL
        self.tools = tools or SUPPLY_CHAIN_TOOLS
        self.system_prompt = system_prompt or AGENT_SYSTEM_PROMPT
        self.max_turns = max_turns or AGENT_MAX_TURNS
        self.registry = get_tool_registry()
    
    def run(
        self,
        transcript: str,
        user_id: int,
        user_did: str = None,
        language: str = "en",
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResult:
        """
        Run the agent on a user transcript.
        
        Args:
            transcript: Transcribed text from ASR
            user_id: User database ID (for batch ownership, history)
            user_did: User DID (for credential issuance)
            language: User's preferred language (en/am)
            context: Optional app context (visible batches, current view, etc.)
            
        Returns:
            AgentResult with response and tool call records
        """
        start_time = time.time()
        total_tokens = 0
        all_tool_calls: List[ToolCall] = []
        performed_write = False
        last_intent = None
        last_entities = {}
        is_amharic = language == "am"
        original_transcript = transcript
        
        # -----------------------------------------------------------
        # Amharic handling: translate user input → English for the
        # agent's reasoning, then translate response back → Amharic.
        # The agent always reasons & calls tools in English (where
        # GPT-4o's tool-calling is strongest), but the user sees
        # their preferred language.
        # -----------------------------------------------------------
        if is_amharic:
            logger.info(f"Translating Amharic input for agent (user {user_id})")
            transcript = translate_text(transcript, "am", "en")
            logger.info(f"Translated input: {transcript[:80]}...")
        
        # Build initial messages
        system_msg = self._build_system_message(user_id, language, context)
        
        # Load conversation history
        history = get_conversation_history(user_id)
        
        messages = [{"role": "system", "content": system_msg}]
        messages.extend(history)
        messages.append({"role": "user", "content": transcript})
        
        try:
            # Agent loop - max N turns of tool calling
            for turn in range(self.max_turns):
                logger.info(
                    f"Agent turn {turn + 1}/{self.max_turns} for user {user_id} "
                    f"(model={self.model}, messages={len(messages)})"
                )
                
                # Call the model
                response, provider_used = chat_completion_with_fallback(
                    primary_client=_client,
                    model=self.model,
                    messages=messages,
                    tools=self.tools,
                    tool_choice="auto",
                    temperature=AGENT_TEMPERATURE,
                    max_tokens=1000,
                )
                logger.info(f"Agent LLM provider: {provider_used}")
                
                total_tokens += response.usage.total_tokens if response.usage else 0
                choice = response.choices[0]
                msg = choice.message
                
                # Case 1: Model wants to call tools
                if msg.tool_calls:
                    # Append assistant message with tool_calls
                    messages.append({
                        "role": "assistant",
                        "content": msg.content or "",
                        "tool_calls": msg.tool_calls,
                    })
                    
                    # Execute each tool call
                    for tc in msg.tool_calls:
                        tool_name = tc.function.name
                        try:
                            tool_args = json.loads(tc.function.arguments)
                        except json.JSONDecodeError:
                            tool_args = {}
                        
                        logger.info(f"Agent calling tool: {tool_name}({tool_args})")
                        
                        tc_start = time.time()
                        tool_result = self._execute_tool(
                            tool_name, tool_args,
                            user_id=user_id, user_did=user_did
                        )
                        tc_duration = (time.time() - tc_start) * 1000
                        
                        tool_call_record = ToolCall(
                            tool_name=tool_name,
                            arguments=tool_args,
                            result_message=tool_result["message"],
                            result_data=tool_result.get("data", {}),
                            success=tool_result["success"],
                            duration_ms=tc_duration,
                        )
                        all_tool_calls.append(tool_call_record)
                        
                        # Track write operations
                        if tool_result["success"] and tool_name not in (
                            "query_batches", "search_knowledge",
                            "browse_rfqs", "list_my_offers",
                            "check_eudr_compliance", "check_mass_balance",
                            "get_dpp", "get_container_dpp",
                            "trace_lineage", "validate_dpp",
                            "list_pending_verifications",
                            "check_blockchain_anchor", "get_token_info",
                            "verify_batch_hash",
                            "check_don_attestation", "get_don_provenance_metrics",
                            "browse_pools", "list_my_commitments",
                            "browse_containers", "check_payment_status",
                        ):
                            performed_write = True
                            last_intent = tool_name
                            last_entities = tool_args
                        
                        # Append tool result as message
                        result_content = json.dumps({
                            "success": tool_result["success"],
                            "message": tool_result["message"],
                            "data": tool_result.get("data", {}),
                        }, default=str)
                        
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "name": tool_name,
                            "content": result_content,
                        })
                    
                    # Continue loop - model may want to call more tools or respond
                    continue
                
                # Case 2: Model returns text response (no more tool calls)
                response_text = msg.content or ""
                
                # Translate response to Amharic if user speaks Amharic
                if is_amharic and response_text:
                    logger.info(f"Translating agent response → Amharic for user {user_id}")
                    response_text = translate_text(response_text, "en", "am")
                
                # Save updated history (exclude system prompt)
                messages_to_save = messages[1:]  # Skip system prompt
                messages_to_save.append({"role": "assistant", "content": response_text})
                save_conversation_history(user_id, messages_to_save)
                
                # If a write was performed, clear history after response
                # (fresh start for next interaction)
                if performed_write:
                    clear_conversation_history(user_id)
                
                duration = (time.time() - start_time) * 1000
                
                return AgentResult(
                    response=response_text,
                    response_spoken=self._strip_for_speech(response_text),
                    tool_calls=all_tool_calls,
                    performed_write=performed_write,
                    needs_followup=not performed_write and len(all_tool_calls) == 0,
                    intent=last_intent,
                    entities=last_entities,
                    total_tokens=total_tokens,
                    duration_ms=duration,
                )
            
            # Exhausted max turns
            logger.warning(f"Agent exhausted {self.max_turns} turns for user {user_id}")
            duration = (time.time() - start_time) * 1000
            return AgentResult(
                response="I'm having trouble completing this request. Could you try rephrasing?",
                tool_calls=all_tool_calls,
                performed_write=performed_write,
                intent=last_intent,
                entities=last_entities,
                total_tokens=total_tokens,
                duration_ms=duration,
                error="max_turns_exhausted",
            )
        
        except Exception as e:
            logger.error(f"Agent error for user {user_id}: {e}", exc_info=True)
            # Re-raise so callers can detect failure and trigger their
            # fallback path with proper observability (banner / response_source).
            raise
    
    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    
    def _build_system_message(
        self, user_id: int, language: str, context: Optional[Dict[str, Any]]
    ) -> str:
        """Build the system prompt with optional context."""
        prompt = self.system_prompt

        # Add anonymous user context
        if user_id == 0 or user_id is None:
            prompt += (
                "\n\nAUTHENTICATION STATUS: The user is ANONYMOUS (not signed in).\n"
                "- They CAN use read-only tools: browse RFQs, query batches, check compliance, view DPPs, etc.\n"
                "- They CANNOT use write tools: creating batches, RFQs, offers, purchases, commitments, payments, etc.\n"
                "- When they ask for a write action, DO NOT call the tool. Instead, politely explain they need to "
                "sign in first and give them two options:\n"
                "  1. Click 'Sign In' in the navigation bar\n"
                "  2. Register via Telegram: https://t.me/voice_ledger_bot\n"
                "- After explaining, ask if there's anything read-only you can help with.\n"
            )

        # Add language context
        if language == "am":
            prompt += (
                "\n\nLANGUAGE NOTE: The user speaks Amharic. Their message has been "
                "translated to English for you. You should RESPOND IN ENGLISH - the "
                "system will translate your response back to Amharic automatically. "
                "Keep your responses simple and clear so they translate well. "
                "Avoid idioms, wordplay, or complex sentence structures. "
                "Use short sentences. Local names, coffee varieties (Sidama, "
                "Yirgacheffe, Guji, Gedeo, Harrar), and locations should stay as-is."
            )
        
        # Add app context if available
        if context:
            prompt += "\n\nCURRENT CONTEXT:\n"
            if context.get("app"):
                prompt += f"App: {context['app']}\n"
            if context.get("user_role"):
                prompt += f"User role: {context['user_role']}\n"
            if context.get("visible_batches"):
                prompt += "Visible batches:\n"
                for b in context["visible_batches"][:5]:
                    prompt += (
                        f"  - {b.get('batch_id', b.get('id'))}: "
                        f"{b.get('origin', '?')} {b.get('quantity_kg', 0)}kg "
                        f"({b.get('status', '?')})\n"
                    )
            prompt += (
                "\nUse this context to resolve references like "
                "'this batch', 'the first one', 'my latest'.\n"
            )
        
        return prompt
    
    # Tools that anonymous (user_id=0) guests are allowed to call
    READ_ONLY_TOOLS = {
        "query_batches", "search_knowledge",
        "browse_rfqs", "list_my_offers",
        "check_eudr_compliance", "check_mass_balance",
        "get_dpp", "get_container_dpp",
        "trace_lineage", "validate_dpp",
        "list_pending_verifications",
        "check_blockchain_anchor", "get_token_info",
        "verify_batch_hash",
        "check_don_attestation", "get_don_provenance_metrics",
        "browse_containers", "browse_pools",
        "list_my_commitments", "check_payment_status",
        "check_financing_pool", "check_trade_financing",
    }

    def _execute_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
        user_id: int = None,
        user_did: str = None,
    ) -> Dict[str, Any]:
        """
        Execute a tool by name, with database session management.
        
        Returns:
            {"success": bool, "message": str, "data": dict}
        """
        # --- Anonymous user guard ---
        if (user_id is None or user_id == 0) and tool_name not in self.READ_ONLY_TOOLS:
            return {
                "success": False,
                "message": (
                    f"This action ({tool_name.replace('_', ' ')}) requires a registered account. "
                    "Please sign in or register via Telegram at https://t.me/voice_ledger_bot"
                ),
                "data": {"needs_auth": True},
            }

        handler = self.registry.get(tool_name)
        if not handler:
            return {
                "success": False,
                "message": f"Unknown tool: {tool_name}",
                "data": {},
            }
        
        from database.connection import get_db
        from voice.command_integration import VoiceCommandError
        
        try:
            with get_db() as db:
                message, data = handler(
                    db, args, user_id=user_id, user_did=user_did
                )
                return {
                    "success": True,
                    "message": message,
                    "data": data,
                }
        except VoiceCommandError as e:
            logger.warning(f"Tool {tool_name} validation error: {e}")
            return {
                "success": False,
                "message": str(e),
                "data": {},
            }
        except Exception as e:
            logger.error(f"Tool {tool_name} failed: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Operation failed: {str(e)}",
                "data": {},
            }
    
    @staticmethod
    def _strip_for_speech(text: str) -> str:
        """
        Strip URLs, emoji, and markdown from text for TTS.
        Keeps the text natural for spoken output.
        """
        import re
        
        # Remove URLs
        text = re.sub(r"https?://\S+", "", text)
        # Remove markdown bold/italic
        text = re.sub(r"\*+([^*]+)\*+", r"\1", text)
        text = re.sub(r"_+([^_]+)_+", r"\1", text)
        # Remove markdown headers
        text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
        # Remove bullet points
        text = re.sub(r"^[•\-]\s*", "", text, flags=re.MULTILINE)
        # Remove emoji (basic range)
        text = re.sub(
            r"[\U0001F300-\U0001F9FF\U00002700-\U000027BF\U0000FE00-\U0000FE0F"
            r"\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002600-\U000026FF]",
            "",
            text,
        )
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()
        
        return text
