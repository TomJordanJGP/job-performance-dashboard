#!/bin/bash

# Job Performance Dashboard Launcher
# Quick start script for the dashboard

echo "🚀 Job Performance Dashboard"
echo "=============================="
echo ""

# Check if service account credentials exist
if [ ! -f "service_account.json" ]; then
    echo "❌ Error: service_account.json not found"
    echo ""
    echo "Please follow these steps:"
    echo "1. Create a Google Cloud Service Account"
    echo "2. Download the JSON credentials"
    echo "3. Save it as 'service_account.json' in this directory"
    echo ""
    echo "See SETUP_GUIDE.md for detailed instructions"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "❌ Failed to create virtual environment"
        exit 1
    fi
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install/update dependencies
echo "📥 Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

if [ $? -ne 0 ]; then
    echo "❌ Failed to install dependencies"
    exit 1
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "🌐 Starting dashboard..."
echo "   The dashboard will open at: http://localhost:8501"
echo ""
echo "   Press Ctrl+C to stop the server"
echo ""

# Run Streamlit (skip email prompt with headless mode)
export STREAMLIT_EMAIL_ADDRESS=""
streamlit run app.py --browser.gatherUsageStats false
