📄 Final Product Requirements Document (PRD): PDF Parser Microservice
🔧 Project Name
pdf-parser

🧠 Objective
Replace the existing AWS Textract workflow with a Doctly + Markdown parsing service. A single API (/parse) handles the entire flow:

Receives a reference to a PDF in S3

Sends the PDF to Doctly for Markdown conversion

Converts the Markdown to a clean CSV

Uploads the CSV to S3

Sends a webhook to the frontend with a link to the final CSV

Includes a lightweight in-memory queue to serialize jobs and avoid race conditions.

🧩 System Components
Component	Role
/parse	Main endpoint that initiates a job
queue.py	Handles in-memory job queue
worker.py	Background worker that pulls and processes jobs
tableparser.py	Parses Markdown tables into CSV
doctly_client.py	Handles upload + polling Doctly API
s3_utils.py	Upload/download helpers for AWS S3
main.py	FastAPI or Flask app entrypoint

🔄 Flow Summary
Frontend uploads PDF to S3

Frontend calls:

bash
Copy
Edit
POST /parse
{
  "s3_bucket": "client-uploads",
  "s3_key": "incoming/rogue-vc.pdf",
  "webhook_url": "https://frontend.com/api/onCsvComplete"
}
Server pushes job to queue

If a job is already running, the new one waits

Returns:

json
Copy
Edit
{ "status": "queued", "position": 1 }
Worker pulls job and runs steps:

Download from S3

Send to Doctly (accuracy=ultra)

Poll until COMPLETED

Download Markdown file

Parse into CSV (tableparser.py)

Upload CSV to S3: processed/<filename>.csv

Trigger webhook:

json
Copy
Edit
{
  "status": "success",
  "csv_url": "https://s3.amazonaws.com/bucket/processed/rogue-vc.csv",
  "original_filename": "rogue-vc.pdf"
}
🚥 Error Handling
Error	Behavior
S3 download fails	Webhook: { "status": "error", "message": "S3 failed" }
Doctly fails to process	Webhook: { "status": "error", "message": "Doctly failed" }
Markdown empty or malformed	Best-effort CSV, fallback headers applied
Uncaught exception	Logged, webhook sends generic failure

🧪 Test Script
scripts/test_runner.py handles:

Upload to S3

Trigger to /parse

Optional mock webhook listener

Logs response + final CSV URL

💾 Environment Variables
Variable	Description
AWS_ACCESS_KEY_ID	S3 auth
AWS_SECRET_ACCESS_KEY	S3 auth
AWS_REGION	S3 region
DOCTLY_API_KEY	API key for Doctly
S3_OUTPUT_PREFIX	Optional output folder in S3

🧹 Cleanup Requirements
Delete all local temp files after use (/tmp/*.pdf, .md, .csv)

In-memory queue resets on restart (acceptable for now)

🚀 Deployment
Runtime: Railway (Docker)

Single instance only (in-memory queue assumes this)

Exposes /parse as a public API

Webhooks must be HTTPS and accessible externally

🚫 Out of Scope for Now
No direct file uploads to /upload

No retry queue persistence

No admin dashboard

🏁 Done State
This service is considered production-ready when:

It reliably parses PDFs → CSVs from S3

Can queue >1 job without failure

Sends clean webhook payloads

Cleans up temp files

Can be tested locally with test_runner.py

