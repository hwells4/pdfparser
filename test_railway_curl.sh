#!/bin/bash

# Railway PDF Parser Test Script
# Quick test using curl commands

echo "🧪 Railway PDF Parser - Curl Test"
echo "=================================="

# Configuration - UPDATE THESE VALUES
read -p "Enter your Railway app URL (e.g., https://your-app.railway.app): " RAILWAY_URL
read -p "Enter S3 key of your PDF (e.g., documents/sample.pdf): " S3_KEY
read -p "Enter webhook URL (or press Enter for webhook.site): " WEBHOOK_URL

# Remove trailing slash from Railway URL
RAILWAY_URL=${RAILWAY_URL%/}

# Generate webhook.site URL if none provided
if [ -z "$WEBHOOK_URL" ]; then
    WEBHOOK_ID=$(uuidgen | cut -c1-8 | tr '[:upper:]' '[:lower:]')
    WEBHOOK_URL="https://webhook.site/$WEBHOOK_ID"
    echo "📡 Generated webhook URL: $WEBHOOK_URL"
    echo "   Visit this URL in your browser to see webhook notifications!"
fi

echo ""
echo "🏥 Step 1: Health Check"
echo "======================="
curl -s "$RAILWAY_URL/health" | jq '.' || echo "❌ Health check failed"

echo ""
echo "🚀 Step 2: Trigger Parse Job"
echo "============================"

# Create JSON payload
PAYLOAD=$(cat <<EOF
{
  "s3_bucket": "converseinsurance",
  "s3_key": "$S3_KEY",
  "webhook_url": "$WEBHOOK_URL"
}
EOF
)

echo "Payload:"
echo "$PAYLOAD" | jq '.'

echo ""
echo "Sending request..."
curl -X POST "$RAILWAY_URL/parse" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" | jq '.'

echo ""
echo "📋 What happens next:"
echo "===================="
echo "1. 📥 Railway downloads PDF from s3://converseinsurance/$S3_KEY"
echo "2. 🔄 Sends PDF to Doctly for processing"
echo "3. ⏳ Waits for Doctly to convert PDF to Markdown"
echo "4. 📊 Converts Markdown tables to CSV"
echo "5. 📤 Uploads CSV to s3://converseinsurance/processed/${S3_KEY%.pdf}.csv"
echo "6. 📡 Sends webhook notification"

echo ""
echo "🔍 Monitor webhook: $WEBHOOK_URL"
echo "📁 Expected CSV: s3://converseinsurance/processed/${S3_KEY%.pdf}.csv"
echo ""
echo "✅ Test completed! Check your webhook URL for results." 