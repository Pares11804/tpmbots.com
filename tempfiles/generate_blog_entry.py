import os

from dotenv import load_dotenv
from mistralai.client import Mistral

load_dotenv()
api_key = os.getenv("MISTRAL_API_KEY")
model = "mistral-large-latest"

client = Mistral(api_key=api_key)

# Your Oracle Script
oracle_script = """
Cset lines 120 pages 200

prompt 'process started at 9:14AM on 3/18'
col sofar_gb format 9999999
col avg_gb_copy_per_min format 999999

SELECT name, value/(1024*1024*1024) sofar_GB,
       value/(1024*1024*1024) / ((sysdate - to_date('18-MAR-2026:09:14','DD-MON-RRRR:HH24:MI'))*(24*60)) avg_gb_copy_per_min
FROM v$sysstat
WHERE name IN ('physical write total bytes', 'physical write bytes');
"""


response = client.chat.complete(
    model=model,
    messages=[
        {"role": "system", "content": "You are a technical writer specializing in Oracle Databases."},
        {"role": "user", "content": f"Turn this Oracle script into a blog post: {oracle_script}"},
    ],
)

print(response.choices[0].message.content)
