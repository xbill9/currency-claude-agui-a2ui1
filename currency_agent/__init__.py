import socket

# Force IPv4-only to avoid connection hangs on IPv6 in sandbox environments
if not hasattr(socket, "_original_getaddrinfo"):
    socket._original_getaddrinfo = socket.getaddrinfo

    def _ipv4_only_getaddrinfo(*args, **kwargs):
        return [
            r
            for r in socket._original_getaddrinfo(*args, **kwargs)
            if r[0] == socket.AF_INET
        ]

    socket.getaddrinfo = _ipv4_only_getaddrinfo

# Monkeypatch to fix ImportError: cannot import name 'GEN_AI_INPUT_MESSAGES' from 'opentelemetry'
try:
    import opentelemetry.semconv._incubating.attributes.gen_ai_attributes as gen_ai_attr

    if not hasattr(gen_ai_attr, "GEN_AI_INPUT_MESSAGES"):
        setattr(gen_ai_attr, "GEN_AI_INPUT_MESSAGES", "gen_ai.input.messages")
    if not hasattr(gen_ai_attr, "GEN_AI_OUTPUT_MESSAGES"):
        setattr(gen_ai_attr, "GEN_AI_OUTPUT_MESSAGES", "gen_ai.output.messages")
    if not hasattr(gen_ai_attr, "GEN_AI_RESPONSE_FINISH_REASONS"):
        setattr(
            gen_ai_attr,
            "GEN_AI_RESPONSE_FINISH_REASONS",
            "gen_ai.response.finish_reasons",
        )
    if not hasattr(gen_ai_attr, "GEN_AI_SYSTEM_INSTRUCTIONS"):
        setattr(gen_ai_attr, "GEN_AI_SYSTEM_INSTRUCTIONS", "gen_ai.system.instructions")
    if not hasattr(gen_ai_attr, "GEN_AI_USAGE_INPUT_TOKENS"):
        setattr(gen_ai_attr, "GEN_AI_USAGE_INPUT_TOKENS", "gen_ai.usage.input_tokens")
    if not hasattr(gen_ai_attr, "GEN_AI_USAGE_OUTPUT_TOKENS"):
        setattr(gen_ai_attr, "GEN_AI_USAGE_OUTPUT_TOKENS", "gen_ai.usage.output_tokens")
except ImportError:
    pass

# Monkeypatch to fix ImportError: cannot import name 'SamplingCapability' from 'mcp'
try:
    import mcp
    import mcp.types

    if not hasattr(mcp, "SamplingCapability"):
        setattr(mcp, "SamplingCapability", mcp.types.SamplingCapability)
except ImportError:
    pass

# Monkeypatch to fix TypeError: ClientSession.__init__() got an unexpected keyword argument 'sampling_capabilities'
try:
    import mcp

    if not hasattr(mcp.ClientSession, "_original_init"):
        mcp.ClientSession._original_init = mcp.ClientSession.__init__

        def _patched_client_session_init(self, *args, **kwargs):
            import inspect

            sig = inspect.signature(mcp.ClientSession._original_init)
            if "sampling_capabilities" not in sig.parameters:
                kwargs.pop("sampling_capabilities", None)
            return mcp.ClientSession._original_init(self, *args, **kwargs)

        mcp.ClientSession.__init__ = _patched_client_session_init
except Exception:
    pass

# Monkeypatch to fix TypeError: ClientSession.call_tool() got an unexpected keyword argument 'meta'
try:
    import mcp

    if not hasattr(mcp.ClientSession, "_original_call_tool"):
        mcp.ClientSession._original_call_tool = mcp.ClientSession.call_tool

        def _patched_client_session_call_tool(self, *args, **kwargs):
            import inspect

            sig = inspect.signature(mcp.ClientSession._original_call_tool)
            if "meta" not in sig.parameters:
                kwargs.pop("meta", None)
            return mcp.ClientSession._original_call_tool(self, *args, **kwargs)

        mcp.ClientSession.call_tool = _patched_client_session_call_tool
except Exception:
    pass

# Monkeypatch to prevent ADK from treating A2UI template expressions (e.g., {expression}) as state variables
try:
    import google.adk.utils.instructions_utils as inst_utils

    inst_utils._is_valid_state_name = lambda var_name: False
except Exception:
    pass

from . import agent as agent
