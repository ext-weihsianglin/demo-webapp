"""Conservative complete-request token preflight for the served model catalog."""
import json

CONTEXT_TOKENS = 128000
OVERHEAD_RESERVE = 2048
PROFILE = {'context_tokens':CONTEXT_TOKENS,'overhead_reserve':OVERHEAD_RESERVE,
           'policy':'complete_input_schema_and_output_reserve_v1'}


def input_tokens(instructions, payload, schema, encoding):
    return len(encoding.encode(instructions + payload + json.dumps(schema))) + OVERHEAD_RESERVE
