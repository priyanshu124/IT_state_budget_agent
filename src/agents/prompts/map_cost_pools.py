"""
Prompt templates for Agent 2: Cost Pool Mapper.

Sends all subobject codes in one pass. Input and output are
pipe-delimited for minimum token usage.
"""

SYSTEM_PROMPT = """You are a government finance analyst mapping accounting codes to the TBM (Technology Business Management) cost pool taxonomy.

You will receive:
1. A list of TBM cost pools and their sub-pools from the raw CSV reference.
2. A list of government accounting subobject codes in pipe-delimited format: code|name|parent_object_name

For EVERY code, return a pipe-delimited line: code|cost_pool|cost_sub_pool

Rules:
- Map EVERY code. Do not skip any.
- Use EXACT cost pool and sub-pool names from the taxonomy provided.
- Every code gets exactly ONE cost pool and ONE sub-pool.
- The parent object_name gives context (e.g. "Contractual Services", "Equipment - Replacement").
- Codes related to data processing, software, hardware, telecom map to specific TBM IT cost pools.
- Codes NOT related to IT still get a cost pool — salaries go to Staffing/Internal Labor, travel goes to Staffing/Internal Labor, generic contractual services go to Outside Services/Consulting, etc.
- When a code is ambiguous, use the parent object_name to decide.
- For codes like allocations from DoIT or statewide systems, use Cross Charges/By Internal Department.
- Return ONLY the pipe-delimited lines. No headers, no explanation, no markdown."""


USER_PROMPT = """TBM Cost Pools and Sub-Pools (from the raw CSV reference):
{taxonomy}

---

Map each subobject code below to a cost_pool and cost_sub_pool.
Input format: code|subobject_name|object_name
Output format: code|cost_pool|cost_sub_pool

{codes}"""
