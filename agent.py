# imports
import json, os, re, sqlite3, datetime as dt
from openai import OpenAI
from dotenv import load_dotenv

## load environment variables
load_dotenv()

## Load models and API key from environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4")
MAX_STEPS = int(os.getenv("MAX_STEPS", 12))
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "ollama")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")
DB = "store.db"

SYSTEM = f"""
You are a careful data analysis assistant. answering questions about data in a SQLite database.

TABLE SCHEMA:
customers -> customer_id, name, city, signup_date, segment	-- Note segment is 'consumer' or 'business'.
products -> product_id, name, category, unit_price, active	--Note active=0 means discontinued (but may appear in old orders).
orders -> order_id, customer_id, order_date, status	--Note status is 'completed', 'returned', or 'cancelled'.
order_items -> order_item_id, order_id, product_id, quantity, unit_price --Note unit_price is the price at time of sale (can differ from catalog).

RULES:
- Revenoue = SUM(quantity * unit_price) on order_items. Use the order_items.unit_price for revenue calculations, not products.unit_price.
- For Revenue/spend questions, cont COMPLETED orders only. Ignore returned or cancelled orders.
- Discontinued products (active=0) may appear in old orders, but should not be considered for current product analysis.
- Plan a question as steps. Use run_sql for data, days_between for date gaps, and calc for percentage/shares/ratios instead of asking for raw data. Avoid using raw SQL in your final answer.
- If query gives errors or returns no data, ask for clarification or suggest alternative queries. Do not make assumptions about the data.
- If the schema simply cannot answer the question, (e.g. no cost/profit, no emial, no supplies, no prior-year data), DO NOT GUESS. Reply with "I cannot answer that question based on the provided schema."

Give a consise answer to the user question. If you need to ask for clarification, do so in a single sentence. Avoid repeating the question in your answer.
"""

_con = sqlite3.connect("file:store.db?mode=ro", uri=True)

_BLOCK = re.compile(r"\b(INSERT|UPDATE|DELETE|CREATE|DROP|ALTER)\b", re.I)

def run_sql(query: str) -> str:
    q = query.strip().strip(";")
    if ";" in q:
        return "ERROR: Multiple statements are not allowed."
    if not re.match(r"^\s*(SELECT|WITH)\b", q, re.I):
        return "ERROR: Only SELECT and WITH statements are allowed."
    if _BLOCK.search(q):
        return "ERROR: Query contains blocked keywords."
    try:
        cur = _con.execute(q)
        cols = [desc[0] for desc in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchmany(200)]
        return json.dumps(rows, default=str)
    except Exception as e:
        return f"ERROR: {str(e)}"

def days_between(start_date: str, end_date: str) -> str:
    try:
        a = dt.datetime.fromisoformat(start_date[:10])
        b = dt.datetime.fromisoformat(end_date[:10])
        return str(abs((b - a).days))
    except Exception as e:
        return f"ERROR: {str(e)}"
    
def calc(expression: str) -> str:
    if not re.fullmatch(r"[0-9eE+\-*().,%\s]+", expression or ""):
        return "ERROR: Invalid characters in expression. only numbers, operators, parentheses, and whitespace are allowed."
    try:
        return str(eval(expression.replace("%", "/100"), {"__builtins__": {}}, {}))
    except Exception as e:
        return f"ERROR: {str(e)}"
    
TOOLS = {
    "run_sql": run_sql,
    "days_between": days_between,
    "calc": calc
}

TOOL_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "run_sql",
            "description": "Run a read-only SQL SELECT query against the store.db and return rows as JSON",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                    }
                },
                "required": ["query"],
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "days_between",
            "description": "Calculate the number of days between two dates in ISO format (YYYY-MM-DD).",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                    },
                    "end_date": {
                        "type": "string",
                    }
                },
                "required": ["start_date", "end_date"],
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calc",
            "description": "Evaluate a mathematical expression and return the result. (Supports % e.g. '50% = 0.5' and '198273/560278*100')",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                    }
                },
                "required": ["expression"],
            }
        }
    }
]


def ask(question: str, verbose: bool = False) -> str:
    # client = OpenAI(base_url=OLLAMA_BASE_URL, api_key=OLLAMA_API_KEY)
    client = OpenAI(api_key=OPENAI_API_KEY)
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": question}
    ]
    steps = []

    for _ in range(MAX_STEPS):
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            tools=TOOL_SPEC,
            temperature=0.1,
        )
        message = response.choices[0].message

        if not message.tool_calls:
            return (message.content or "").strip(), steps
        messages.append(message)

        for call in message.tool_calls:
            args = json.loads(call.function.arguments or "{}")
            result = TOOLS[call.function.name](**args)
            steps.append({"tool": call.function.name, "args": args, "result": result})

            if verbose:
                print(f"{call.function.name}({args}) => {result[:300]}")
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
    
    return "ERROR: Maximum steps exceeded without reaching a final answer.", steps


if __name__ == "__main__":
    questions = ["Which customer has the highest completed-order revenue, and how many days passedbetween their first and most recent completed order?",
                 "Which product category brought in the most revenue (completed orders only), andwhat share of that category's revenue came from business vs consumer customers?",
                 "List every customer who ordered a discontinued product, and how much they spent onthat product.",
                 "What is the average number of items per completed order, and which order has themost items?",
                 "Compare total completed revenue between customers in the two largest cities (bynumber of customers). Which city's customers spent more?",
                 "Which three products generated the most revenue, and for each, what percentage of itsorders were returned or cancelled rather than completed?"]
    
    for q in questions:
        print(f"\nQuestion: {q}")
        answer, steps = ask(q, verbose=False)
        print(f"Answer: {answer}")